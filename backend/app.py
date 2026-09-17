import os
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS
import bcrypt
import jwt

# Intentar importar psycopg2 para PostgreSQL (Supabase)
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Configuración de base de datos
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

JWT_SECRET = os.environ.get('JWT_SECRET', 'clave_secreta_contrato_claro_2026')
DB_PATH = os.environ.get('DB_PATH', 'database.db')

IS_POSTGRES = bool(DATABASE_URL and PSYCOPG2_AVAILABLE)
IntegrityErrors = (sqlite3.IntegrityError, psycopg2.IntegrityError) if PSYCOPG2_AVAILABLE else sqlite3.IntegrityError


def get_db():
    if IS_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def execute_query(cursor, query, params=()):
    if IS_POSTGRES:
        query = query.replace('?', '%s')
    cursor.execute(query, params)


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    if IS_POSTGRES:
        # 1. PERFILES_USUARIO
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS perfiles_usuario (
                id SERIAL PRIMARY KEY,
                nombre TEXT NOT NULL,
                identificacion TEXT,
                rol TEXT NOT NULL,
                estado_identidad TEXT DEFAULT 'pendiente',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        # 2. USUARIOS
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                perfil_id INTEGER UNIQUE NOT NULL REFERENCES perfiles_usuario(id) ON DELETE CASCADE,
                correo TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        # 3. CONTRATOS
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contratos (
                id SERIAL PRIMARY KEY,
                tipo TEXT,
                titulo TEXT,
                objeto TEXT,
                valor REAL,
                forma_pago TEXT,
                fecha_inicio TEXT,
                fecha_fin TEXT,
                estado TEXT DEFAULT 'borrador',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        # 4. PARTES_CONTRATO (N:M)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS partes_contrato (
                contrato_id INTEGER REFERENCES contratos(id) ON DELETE CASCADE,
                perfil_id INTEGER REFERENCES perfiles_usuario(id) ON DELETE CASCADE,
                rol_en_contrato TEXT,
                PRIMARY KEY (contrato_id, perfil_id)
            );
        ''')
        # 5. CLAUSULAS
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clausulas (
                id SERIAL PRIMARY KEY,
                codigo TEXT UNIQUE NOT NULL,
                nombre TEXT NOT NULL
            );
        ''')
        # 6. CONTRATOS_CLAUSULAS (N:M)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contratos_clausulas (
                contrato_id INTEGER REFERENCES contratos(id) ON DELETE CASCADE,
                clausula_id INTEGER REFERENCES clausulas(id) ON DELETE CASCADE,
                PRIMARY KEY (contrato_id, clausula_id)
            );
        ''')
        # 7. HITOS
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hitos (
                id SERIAL PRIMARY KEY,
                contrato_id INTEGER REFERENCES contratos(id) ON DELETE CASCADE,
                titulo TEXT NOT NULL,
                monto REAL NOT NULL,
                estado TEXT DEFAULT 'pendiente',
                archivo_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        # 8. CUSTODIA_ESCROW
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS custodia_escrow (
                id SERIAL PRIMARY KEY,
                contrato_id INTEGER REFERENCES contratos(id) ON DELETE CASCADE,
                monto REAL NOT NULL,
                estado TEXT DEFAULT 'en_custodia',
                referencia_pago TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        # 9. HITOS_CUSTODIA
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hitos_custodia (
                id SERIAL PRIMARY KEY,
                hito_id INTEGER REFERENCES hitos(id) ON DELETE CASCADE,
                custodia_id INTEGER REFERENCES custodia_escrow(id) ON DELETE CASCADE,
                estado_transaccion TEXT DEFAULT 'pendiente',
                fecha_liberacion TIMESTAMP
            );
        ''')
        # 10. DISPUTAS
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS disputas (
                id SERIAL PRIMARY KEY,
                contrato_id INTEGER REFERENCES contratos(id) ON DELETE CASCADE,
                solicitante_perfil_id INTEGER REFERENCES perfiles_usuario(id) ON DELETE CASCADE,
                motivo TEXT NOT NULL,
                estado TEXT DEFAULT 'abierta',
                resolucion TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
    else:
        # Estructura compatible para SQLite local
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS perfiles_usuario (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                identificacion TEXT,
                rol TEXT NOT NULL,
                estado_identidad TEXT DEFAULT 'pendiente',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                perfil_id INTEGER UNIQUE NOT NULL,
                correo TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (perfil_id) REFERENCES perfiles_usuario(id) ON DELETE CASCADE
            );
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contratos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT,
                titulo TEXT,
                objeto TEXT,
                valor REAL,
                forma_pago TEXT,
                fecha_inicio TEXT,
                fecha_fin TEXT,
                estado TEXT DEFAULT 'borrador',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS partes_contrato (
                contrato_id INTEGER NOT NULL,
                perfil_id INTEGER NOT NULL,
                rol_en_contrato TEXT,
                PRIMARY KEY (contrato_id, perfil_id),
                FOREIGN KEY (contrato_id) REFERENCES contratos(id) ON DELETE CASCADE,
                FOREIGN KEY (perfil_id) REFERENCES perfiles_usuario(id) ON DELETE CASCADE
            );
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clausulas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE NOT NULL,
                nombre TEXT NOT NULL
            );
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contratos_clausulas (
                contrato_id INTEGER NOT NULL,
                clausula_id INTEGER NOT NULL,
                PRIMARY KEY (contrato_id, clausula_id),
                FOREIGN KEY (contrato_id) REFERENCES contratos(id) ON DELETE CASCADE,
                FOREIGN KEY (clausula_id) REFERENCES clausulas(id) ON DELETE CASCADE
            );
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hitos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contrato_id INTEGER NOT NULL,
                titulo TEXT NOT NULL,
                monto REAL NOT NULL,
                estado TEXT DEFAULT 'pendiente',
                archivo_url TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (contrato_id) REFERENCES contratos(id) ON DELETE CASCADE
            );
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS custodia_escrow (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contrato_id INTEGER NOT NULL,
                monto REAL NOT NULL,
                estado TEXT DEFAULT 'en_custodia',
                referencia_pago TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (contrato_id) REFERENCES contratos(id) ON DELETE CASCADE
            );
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hitos_custodia (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hito_id INTEGER NOT NULL,
                custodia_id INTEGER NOT NULL,
                estado_transaccion TEXT DEFAULT 'pendiente',
                fecha_liberacion DATETIME,
                FOREIGN KEY (hito_id) REFERENCES hitos(id) ON DELETE CASCADE,
                FOREIGN KEY (custodia_id) REFERENCES custodia_escrow(id) ON DELETE CASCADE
            );
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS disputas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contrato_id INTEGER NOT NULL,
                solicitante_perfil_id INTEGER NOT NULL,
                motivo TEXT NOT NULL,
                estado TEXT DEFAULT 'abierta',
                resolucion TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (contrato_id) REFERENCES contratos(id) ON DELETE CASCADE,
                FOREIGN KEY (solicitante_perfil_id) REFERENCES perfiles_usuario(id) ON DELETE CASCADE
            );
        ''')

    # Insertar cláusulas estándar por defecto si la tabla está vacía
    clausulas_base = [
        ('ALCANCE', 'Cláusula de Control de Alcance y Adendas'),
        ('PI', 'Cláusula de Cesión de Propiedad Intelectual'),
        ('CONFIDENCIALIDAD', 'Cláusula de Confidencialidad y No Divulgación')
    ]
    for codigo, nombre in clausulas_base:
        try:
            if IS_POSTGRES:
                cursor.execute('INSERT INTO clausulas (codigo, nombre) VALUES (%s, %s) ON CONFLICT DO NOTHING', (codigo, nombre))
            else:
                cursor.execute('INSERT OR IGNORE INTO clausulas (codigo, nombre) VALUES (?, ?)', (codigo, nombre))
        except Exception:
            pass

    conn.commit()
    conn.close()


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
    identificacion = data.get('identificacion', '')

    if not nombre or not correo or not password:
        return jsonify({'error': 'Completa todos los campos requeridos.'}), 400

    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    conn = get_db()
    cursor = conn.cursor()
    try:
        # 1. Crear Perfil en PERFILES_USUARIO
        if IS_POSTGRES:
            cursor.execute(
                'INSERT INTO perfiles_usuario (nombre, identificacion, rol) VALUES (%s, %s, %s) RETURNING id',
                (nombre, identificacion, rol)
            )
            perfil_id = cursor.fetchone()['id']
            # 2. Crear Usuario en USUARIOS
            cursor.execute(
                'INSERT INTO usuarios (perfil_id, correo, password) VALUES (%s, %s, %s) RETURNING id',
                (perfil_id, correo, hashed)
            )
            user_id = cursor.fetchone()['id']
        else:
            cursor.execute(
                'INSERT INTO perfiles_usuario (nombre, identificacion, rol) VALUES (?, ?, ?)',
                (nombre, identificacion, rol)
            )
            perfil_id = cursor.lastrowid
            cursor.execute(
                'INSERT INTO usuarios (perfil_id, correo, password) VALUES (?, ?, ?)',
                (perfil_id, correo, hashed)
            )
            user_id = cursor.lastrowid

        conn.commit()
    except IntegrityErrors:
        conn.close()
        return jsonify({'error': 'Este correo ya está registrado.'}), 400

    conn.close()
    
    token = jwt.encode({
        'id': user_id,
        'perfil_id': perfil_id,
        'correo': correo,
        'rol': rol,
        'exp': datetime.utcnow() + timedelta(days=7)
    }, JWT_SECRET, algorithm='HS256')

    return jsonify({
        'token': token,
        'usuario': {'id': user_id, 'perfil_id': perfil_id, 'nombre': nombre, 'correo': correo, 'rol': rol}
    })


@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    correo = data.get('correo')
    password = data.get('password')

    conn = get_db()
    cursor = conn.cursor()
    query = '''
        SELECT u.id, u.perfil_id, u.correo, u.password, p.nombre, p.rol 
        FROM usuarios u
        JOIN perfiles_usuario p ON u.perfil_id = p.id
        WHERE u.correo = ?
    '''
    execute_query(cursor, query, (correo,))
    user = cursor.fetchone()
    conn.close()

    if not user or not bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
        return jsonify({'error': 'Correo o contraseña incorrectos.'}), 401

    token = jwt.encode({
        'id': user['id'],
        'perfil_id': user['perfil_id'],
        'correo': user['correo'],
        'rol': user['rol'],
        'exp': datetime.utcnow() + timedelta(days=7)
    }, JWT_SECRET, algorithm='HS256')

    return jsonify({
        'token': token,
        'usuario': {
            'id': user['id'],
            'perfil_id': user['perfil_id'],
            'nombre': user['nombre'],
            'correo': user['correo'],
            'rol': user['rol']
        }
    })


@app.route('/api/contracts', methods=['GET'])
@token_required
def get_contracts():
    conn = get_db()
    cursor = conn.cursor()
    query = '''
        SELECT c.*, pc.rol_en_contrato 
        FROM contratos c
        JOIN partes_contrato pc ON c.id = pc.contrato_id
        WHERE pc.perfil_id = ?
        ORDER BY c.id DESC
    '''
    execute_query(cursor, query, (request.usuario['perfil_id'],))
    rows = cursor.fetchall()
    conn.close()
    return jsonify({'contratos': [dict(r) for r in rows]})


@app.route('/api/contracts/<int:contract_id>', methods=['GET'])
@token_required
def get_contract(contract_id):
    conn = get_db()
    cursor = conn.cursor()
    query = '''
        SELECT c.*, pc.rol_en_contrato 
        FROM contratos c
        JOIN partes_contrato pc ON c.id = pc.contrato_id
        WHERE c.id = ? AND pc.perfil_id = ?
    '''
    execute_query(cursor, query, (contract_id, request.usuario['perfil_id']))
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

    # 1. Insertar el contrato en CONTRATOS
    query_pg = '''
        INSERT INTO contratos (tipo, titulo, objeto, valor, forma_pago, fecha_inicio, fecha_fin, estado)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
    '''
    query_sqlite = '''
        INSERT INTO contratos (tipo, titulo, objeto, valor, forma_pago, fecha_inicio, fecha_fin, estado)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    '''
    params = (
        b.get('tipo'),
        b.get('titulo'),
        b.get('objeto'),
        b.get('valor'),
        b.get('formaPago'),
        b.get('fechaInicio'),
        b.get('fechaFin'),
        'borrador'
    )

    if IS_POSTGRES:
        cursor.execute(query_pg, params)
        contract_id = cursor.fetchone()['id']
    else:
        cursor.execute(query_sqlite, params)
        contract_id = cursor.lastrowid

    # 2. Asociar al usuario actual en PARTES_CONTRATO
    rol_en_contrato = request.usuario.get('rol', 'freelancer')
    query_partes = 'INSERT INTO partes_contrato (contrato_id, perfil_id, rol_en_contrato) VALUES (?, ?, ?)'
    execute_query(cursor, query_partes, (contract_id, request.usuario['perfil_id'], rol_en_contrato))

    # 3. Asociar Cláusulas activadas en CONTRATOS_CLAUSULAS
    clausulas_map = {
        'clausulaAlcance': 'ALCANCE',
        'clausulaPI': 'PI',
        'clausulaConfidencialidad': 'CONFIDENCIALIDAD'
    }
    for flag, codigo in clausulas_map.items():
        if b.get(flag):
            execute_query(cursor, 'SELECT id FROM clausulas WHERE codigo = ?', (codigo,))
            c_row = cursor.fetchone()
            if c_row:
                execute_query(
                    cursor,
                    'INSERT INTO contratos_clausulas (contrato_id, clausula_id) VALUES (?, ?)',
                    (contract_id, c_row['id'])
                )

    conn.commit()
    conn.close()
    return jsonify({'success': True, 'id': contract_id})


@app.route('/api/contracts/<int:contract_id>', methods=['DELETE'])
@token_required
def delete_contract(contract_id):
    conn = get_db()
    cursor = conn.cursor()
    # Verifica que el usuario pertenezca al contrato antes de eliminarlo
    query_check = 'SELECT contrato_id FROM partes_contrato WHERE contrato_id = ? AND perfil_id = ?'
    execute_query(cursor, query_check, (contract_id, request.usuario['perfil_id']))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Contrato no encontrado o no autorizado.'}), 404

    execute_query(cursor, 'DELETE FROM contratos WHERE id = ?', (contract_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Contrato eliminado con éxito.'})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
