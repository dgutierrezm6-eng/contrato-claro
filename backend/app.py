import os
import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from flask_cors import CORS
import jwt
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Habilitar CORS para permitir peticiones desde el navegador/frontend
CORS(app)

DATABASE_URL = os.environ.get("DATABASE_URL")
SECRET_KEY = os.environ.get("JWT_SECRET", "clave_secreta_contrato_claro_2026")

def get_db():
    # Conexión obligatoria con SSL para Supabase
    return psycopg2.connect(DATABASE_URL, sslmode='require', cursor_factory=RealDictCursor)

def init_db():
    if not DATABASE_URL:
        print("DATABASE_URL no configurada.")
        return
    try:
        conn = get_db()
        cur = conn.cursor()
        
        # Tabla de usuarios
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255),
                identification VARCHAR(100),
                email VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                role VARCHAR(50) DEFAULT 'Freelancer',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Tabla de contratos
        cur.execute("""
            CREATE TABLE IF NOT EXISTS contracts (
                id SERIAL PRIMARY KEY,
                user_id INT REFERENCES users(id) ON DELETE CASCADE,
                title VARCHAR(255) NOT NULL,
                client VARCHAR(255) NOT NULL,
                amount NUMERIC(12, 2) NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        conn.commit()
        cur.close()
        conn.close()
        print("Base de datos inicializada correctamente.")
    except Exception as e:
        print(f"Aviso al inicializar BD: {e}")

# Crear las tablas al iniciar la aplicación
init_db()

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "ok", "message": "Backend de Contrato Claro funcionando"}), 200

# Endpoint de Registro
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    name = data.get("name")
    identification = data.get("identification")
    email = data.get("email")
    password = data.get("password")
    role = data.get("role", "Freelancer")

    if not email or not password:
        return jsonify({"error": "Correo y contraseña son requeridos"}), 400

    hashed_pw = generate_password_hash(password)

    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("SELECT id FROM users WHERE email = %s;", (email,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return jsonify({"error": "El correo ya está registrado"}), 400

        cur.execute(
            "INSERT INTO users (name, identification, email, password, role) VALUES (%s, %s, %s, %s, %s) RETURNING id;",
            (name, identification, email, hashed_pw, role)
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"message": "Usuario registrado exitosamente"}), 201
    except Exception as e:
        return jsonify({"error": f"Error en la base de datos: {str(e)}"}), 500

# Endpoint de Login
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Campos incompletos"}), 400

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s;", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if not user or not check_password_hash(user["password"], password):
            return jsonify({"error": "Credenciales inválidas"}), 401

        token = jwt.encode({
            "user_id": user["id"],
            "email": user["email"],
            "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7)
        }, SECRET_KEY, algorithm="HS256")

        return jsonify({
            "token": token,
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"],
                "role": user["role"]
            }
        }), 200
    except Exception as e:
        return jsonify({"error": f"Error en la autenticación: {str(e)}"}), 500

# Endpoint de Contratos (Obtener y Crear)
@app.route("/api/contracts", methods=["GET", "POST"])
def contracts():
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Token de autenticación faltante"}), 401

    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload["user_id"]
    except Exception:
        return jsonify({"error": "Sesión inválida o expirada"}), 401

    try:
        conn = get_db()
        cur = conn.cursor()

        if request.method == "POST":
            data = request.get_json() or {}
            title = data.get("title")
            client = data.get("client")
            amount = data.get("amount")
            description = data.get("description")

            cur.execute(
                "INSERT INTO contracts (user_id, title, client, amount, description) VALUES (%s, %s, %s, %s, %s) RETURNING id;",
                (user_id, title, client, amount, description)
            )
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({"message": "Contrato creado exitosamente"}), 201

        else:  # GET
            cur.execute("SELECT * FROM contracts WHERE user_id = %s ORDER BY created_at DESC;", (user_id,))
            contracts_list = cur.fetchall()
            cur.close()
            conn.close()
            return jsonify(contracts_list), 200

    except Exception as e:
        return jsonify({"error": f"Error procesando solicitud: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
