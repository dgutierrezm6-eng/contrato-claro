import os
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder='..', static_url_path='')
CORS(app)  # Permite peticiones desde el frontend (Vercel, local, etc.)

# ==============================================================================
# CONFIGURACIÓN SUPABASE
# ==============================================================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Faltan credenciales de Supabase en las variables de entorno.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==============================================================================
# 1. SERVIR EL FRONTEND
# ==============================================================================
@app.route('/')
def index():
    """Sirve el archivo HTML principal desde la raíz o directorio local"""
    if os.path.exists('index.html'):
        return send_file('index.html')
    elif os.path.exists('../index.html'):
        return send_file('../index.html')
    return jsonify({"status": "API Contrato Claro en ejecución"}), 200

# ==============================================================================
# 2. CREACIÓN DE CONTRATO
# ==============================================================================
@app.route('/api/contratos/crear', methods=['POST'])
def crear_contrato():
    """
    Crea un contrato, vincula partes y guarda hitos en 'hitos_contrato'.
    """
    data = request.json or {}
    titulo = data.get('titulo')
    tipo = data.get('tipo', 'General')
    objeto = data.get('objeto', '')
    monto_total = data.get('monto_total', 0)
    hitos = data.get('hitos', [])
    creador_id = data.get('creador_id')
    contraparte_email = data.get('contraparte_email')

    if not titulo or not creador_id:
        return jsonify({"error": "Faltan datos obligatorios (titulo, creador_id)"}), 400

    try:
        # 1. Insertar el contrato
        res_contrato = supabase.table('contratos').insert({
            "titulo": titulo,
            "tipo": tipo,
            "objeto": objeto,
            "valor": monto_total,
            "forma_pago": "Por Hitos",
            "estado": "Activo (Fondeado)"
        }).execute()

        if not res_contrato.data:
            return jsonify({"error": "No se pudo registrar el contrato en la base de datos"}), 500

        contrato_id = res_contrato.data[0]['id']

        # 2. Registrar vinculación de partes
        res_perfil = supabase.table('perfiles_usuario').select('rol').eq('id', creador_id).single().execute()
        mi_rol = res_perfil.data.get('rol', 'Freelancer') if res_perfil.data else 'Freelancer'

        supabase.table('partes_contrato').insert({
            "contrato_id": contrato_id,
            "perfil_id": creador_id,
            "rol_en_contrato": mi_rol
        }).execute()

        if contraparte_email:
            res_cp = supabase.table('perfiles_usuario').select('id, rol').eq('correo', contraparte_email.lower()).maybe_single().execute()
            if res_cp.data:
                rol_cp = res_cp.data.get('rol', 'Cliente o Contratante')
                supabase.table('partes_contrato').insert({
                    "contrato_id": contrato_id,
                    "perfil_id": res_cp.data['id'],
                    "rol_en_contrato": rol_cp
                }).execute()

        # 3. Guardar Hitos en 'hitos_contrato'
        hitos_guardados = []
        if hitos:
            payload_hitos = [
                {
                    "contrato_id": contrato_id,
                    "titulo": h.get('titulo'),
                    "monto": h.get('monto', 0),
                    "estado": h.get('estado', 'Pendiente')
                }
                for h in hitos
            ]
            res_hitos = supabase.table('hitos_contrato').insert(payload_hitos).execute()
            hitos_guardados = res_hitos.data

        # 4. Registrar Custodia Escrow Inicial
        if monto_total > 0:
            supabase.table('custodia_escrow').insert({
                "contrato_id": contrato_id,
                "monto": monto_total,
                "estado": "En Custodia",
                "referencia_pago": f"TXN-{contrato_id}-INIT"
            }).execute()

        return jsonify({
            "message": "Contrato, hitos y partes registrados exitosamente",
            "contrato_id": contrato_id,
            "hitos": hitos_guardados
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==============================================================================
# 3. GESTIÓN DE ESCROW (CUSTODIA)
# ==============================================================================
@app.route('/api/escrow/depositar', methods=['POST'])
def depositar_escrow():
    """Registra el depósito de fondos para un contrato."""
    data = request.json or {}
    contrato_id = data.get('contrato_id')
    monto = data.get('monto')

    if not contrato_id or not monto:
        return jsonify({"error": "Datos incompletos (contrato_id, monto)"}), 400

    try:
        referencia = f"TXN-{contrato_id}-DEP"
        escrow_data = {
            "contrato_id": contrato_id,
            "monto": monto,
            "estado": "En Custodia",
            "referencia_pago": referencia
        }

        res_escrow = supabase.table('custodia_escrow').insert(escrow_data).execute()
        supabase.table('contratos').update({"estado": "Activo (Fondeado)"}).eq("id", contrato_id).execute()

        return jsonify({"message": "Fondos asegurados en Escrow", "data": res_escrow.data}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/escrow/liberar', methods=['POST'])
def liberar_escrow():
    """Libera los fondos del contrato o hito específico."""
    data = request.json or {}
    contrato_id = data.get('contrato_id')
    hito_id = data.get('hito_id')
    escrow_id = data.get('escrow_id')

    if not contrato_id and not hito_id and not escrow_id:
        return jsonify({"error": "Se requiere contrato_id, hito_id o escrow_id"}), 400

    try:
        if hito_id:
            supabase.table('hitos_contrato').update({"estado": "Liberado"}).eq("id", hito_id).execute()

        if contrato_id:
            res_hitos = supabase.table('hitos_contrato').select('estado').eq('contrato_id', contrato_id).execute()
            hitos = res_hitos.data or []
            todos_liberados = len(hitos) > 0 and all(h.get('estado') == 'Liberado' for h in hitos)

            if todos_liberados:
                supabase.table('custodia_escrow').update({"estado": "Liberado"}).eq("contrato_id", contrato_id).execute()
                supabase.table('contratos').update({"estado": "Finalizado"}).eq("id", contrato_id).execute()

        elif escrow_id:
            supabase.table('custodia_escrow').update({"estado": "Liberado"}).eq("id", escrow_id).execute()

        return jsonify({"message": "Fondos transferidos exitosamente"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==============================================================================
# 4. RESOLUCIÓN DE DISPUTAS
# ==============================================================================
@app.route('/api/disputas/resolver', methods=['POST'])
def resolver_disputa():
    """Dictamina el destino de los fondos retenidos."""
    data = request.json or {}
    disputa_id = data.get('disputa_id')
    resolucion_texto = data.get('resolucion', 'Resuelta por acuerdo mutuo')
    accion_fondos = data.get('accion_fondos')  # 'devolver_cliente' o 'pagar_freelancer'

    if not disputa_id:
        return jsonify({"error": "Falta disputa_id"}), 400

    try:
        res_disputa = supabase.table('disputas').update({
            "estado": "RESUELTA",
            "resolucion": resolucion_texto,
            "aceptado_por_contraparte": True
        }).eq("id", disputa_id).execute()

        if not res_disputa.data:
            return jsonify({"error": "No se encontró la disputa especificada"}), 404

        contrato_id = res_disputa.data[0]['contrato_id']
        estado_escrow = 'Reembolsado por Disputa' if accion_fondos == 'devolver_cliente' else 'Liberado por Arbitraje'

        supabase.table('custodia_escrow').update({"estado": estado_escrow}).eq("contrato_id", contrato_id).execute()

        if accion_fondos == 'devolver_cliente':
            supabase.table('contratos').update({"estado": "Cancelado con Reembolso"}).eq("id", contrato_id).execute()
        else:
            supabase.table('contratos').update({"estado": "Finalizado con Disputa"}).eq("id", contrato_id).execute()

        return jsonify({"message": "Disputa resuelta de manera oficial."}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
