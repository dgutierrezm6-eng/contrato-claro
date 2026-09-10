import os
import sqlite3
from flask import Flask, request, jsonify
from flask_cors import CORS
import bcrypt
import jwt
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
# Permitir peticiones CORS desde cualquier origen (Vercel)
CORS(app, resources={r"/api/*": {"origins": "*"}})

JWT_SECRET = os.environ.get('JWT_SECRET', 'clave_secreta_contrato_claro_2026')
DB_PATH = os.environ.get('DB_PATH', 'database.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            correo TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contratos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            tipo TEXT,
            titulo TEXT,
            cliente_nombre TEXT,
            cliente_identificacion TEXT,
            freelancer_nombre TEXT,
            freelancer_identificacion TEXT,
            objeto TEXT,
            valor REAL,
            forma_pago TEXT,
            fecha_inicio TEXT,
            fecha_fin TEXT,
            clausula_alcance INTEGER,
            clausula_pi INTEGER,
            clausula_confidencialidad INTEGER,
            texto_contrato TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
    ''')
    conn.commit()
    conn.close()

# Inicializar DB al arrancar la app
init_db()

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({'error': 'Acceso no autorizado. Inicia sesión.'}), 401
        try:
            token = auth_header.split(' ')[1]
            data = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            request.usuario = data
        except Exception:
            return jsonify({'error': 'Sesión expirada o inválida.'}), 401
        return f(*args, **kwargs)
    return decorated

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    nombre = data.get('nombre')
    correo = data.get('correo')
    password = data.get('password')
    rol = data.get('rol', 'freelancer')

    if not nombre or not correo or not password:
        return jsonify({'error': 'Completa todos los campos requeridos.'}), 400

    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO usuarios (nombre, correo, password, rol) VALUES (?, ?, ?, ?)',
            (nombre, correo, hashed, rol)
        )
        conn.commit()
        user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Este correo ya está registrado.'}), 400

    conn.close()
    token = jwt.encode({
        'id': user_id,
        'correo': correo,
        'exp': datetime.utcnow() + timedelta(days=7)
    }, JWT_SECRET, algorithm='HS256')

    return jsonify({'token': token, 'usuario': {'id': user_id, 'nombre': nombre, 'correo': correo, 'rol': rol}})

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    correo = data.get('correo')
    password = data.get('password')

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM usuarios WHERE correo = ?', (correo,))
    user = cursor.fetchone()
    conn.close()

    if not user or not bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
        return jsonify({'error': 'Correo o contraseña incorrectos.'}), 401

    token = jwt.encode({
        'id': user['id'],
        'correo': user['correo'],
        'exp': datetime.utcnow() + timedelta(days=7)
    }, JWT_SECRET, algorithm='HS256')

    return jsonify({
        'token': token,
        'usuario': {'id': user['id'], 'nombre': user['nombre'], 'correo': user['correo'], 'rol': user['rol']}
    })

@app.route('/api/contracts', methods=['GET'])
@token_required
def get_contracts():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM contratos WHERE usuario_id = ? ORDER BY id DESC', (request.usuario['id'],))
    rows = cursor.fetchall()
    conn.close()
    return jsonify({'contratos': [dict(r) for r in rows]})

@app.route('/api/contracts/<int:contract_id>', methods=['GET'])
@token_required
def get_contract(contract_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM contratos WHERE id = ? AND usuario_id = ?', (contract_id, request.usuario['id']))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'Contrato no encontrado.'}), 404
    return jsonify({'contrato': dict(row)})

@app.route('/api/contracts', methods=['POST'])
@token_required
def create_contract():
    b = request.get_json() or {}
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO contratos (
            usuario_id, tipo, titulo, cliente_nombre, cliente_identificacion,
            freelancer_nombre, freelancer_identificacion, objeto, valor, forma_pago,
            fecha_inicio, fecha_fin, clausula_alcance, clausula_pi, clausula_confidencialidad, texto_contrato
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        request.usuario['id'],
        b.get('tipo'),
        b.get('titulo'),
        b.get('clienteNombre'),
        b.get('clienteIdentificacion'),
        b.get('freelancerNombre'),
        b.get('freelancerIdentificacion'),
        b.get('objeto'),
        b.get('valor'),
        b.get('formaPago'),
        b.get('fechaInicio'),
        b.get('fechaFin'),
        1 if b.get('clausulaAlcance') else 0,
        1 if b.get('clausulaPI') else 0,
        1 if b.get('clausulaConfidencialidad') else 0,
        b.get('textoContrato')
    ))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return jsonify({'success': True, 'id': new_id})

@app.route('/api/contracts/<int:contract_id>', methods=['DELETE'])
@token_required
def delete_contract(contract_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM contratos WHERE id = ? AND usuario_id = ?', (contract_id, request.usuario['id']))
    conn.commit()
    deleted = cursor.rowcount
    conn.close()
    if deleted == 0:
        return jsonify({'error': 'Contrato no encontrado.'}), 404
    return jsonify({'message': 'Contrato eliminado.'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)