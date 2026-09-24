import os
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from supabase import create_client, Client
from dotenv import load_dotenv

# Cargar variables de entorno (.env)
load_dotenv()

app = Flask(__name__)
CORS(app)  # Permite peticiones desde el frontend en Vercel

# ==============================================================================
# CONFIGURACIÓN SUPABASE (BACKEND)
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
    """Sirve el archivo HTML principal"""
    return send_file('index.html')

# ==============================================================================
# 2. GESTIÓN DE ESCROW (CUSTODIA)
# ==============================================================================
@app.route('/api/escrow/depositar', methods=['POST'])
def depositar_escrow():
    """
    Registra el depósito inicial de fondos para un contrato.
    """
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
        
        # Guardar en la tabla 'custodia_escrow' (en minúsculas)
        res_escrow = supabase.table('custodia_escrow').insert(escrow_data).execute()
        
        # Actualizar estado en la tabla 'contratos'
        supabase.table('contratos').update({"estado": "Activo (Fondeado)"}).eq("id", contrato_id).execute()

        return jsonify({"message": "Fondos asegurados en Escrow", "data": res_escrow.data}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/escrow/liberar', methods=['POST'])
def liberar_escrow():
    """
    Libera los fondos del contrato al freelancer.
    Acepta tanto 'contrato_id' (enviado desde el frontend) como 'escrow_id'.
    """
    data = request.json or {}
    contrato_id = data.get('contrato_id')
    escrow_id = data.get('escrow_id')
    
    if not contrato_id and not escrow_id:
        return jsonify({"error": "Se requiere contrato_id o escrow_id"}), 400

    try:
        if contrato_id:
            # Actualiza el registro de custodia filtrando por contrato_id
            res = supabase.table('custodia_escrow').update({"estado": "Liberado"}).eq("contrato_id", contrato_id).execute()
            # Actualiza el estado del contrato a Finalizado
            supabase.table('contratos').update({"estado": "Finalizado"}).eq("id", contrato_id).execute()
        else:
            # Actualiza por la ID del registro de custodia
            res = supabase.table('custodia_escrow').update({"estado": "Liberado"}).eq("id", escrow_id).execute()

        return jsonify({"message": "Fondos transferidos exitosamente", "data": res.data}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==============================================================================
# 3. RESOLUCIÓN DE DISPUTAS
# ==============================================================================
@app.route('/api/disputas/resolver', methods=['POST'])
def resolver_disputa():
    """
    Permite dictaminar hacia dónde van los fondos retenidos.
    """
    data = request.json or {}
    disputa_id = data.get('disputa_id')
    resolucion_texto = data.get('resolucion')
    accion_fondos = data.get('accion_fondos')  # 'devolver_cliente' o 'pagar_freelancer'

    if not disputa_id:
        return jsonify({"error": "Falta disputa_id"}), 400

    try:
        # 1. Actualizar la disputa
        res_disputa = supabase.table('disputas').update({
            "estado": "Resuelta",
            "resolucion": resolucion_texto
        }).eq("id", disputa_id).execute()

        if not res_disputa.data:
            return jsonify({"error": "No se encontró la disputa especificada"}), 44

        contrato_id = res_disputa.data[0]['contrato_id']

        # 2. Mover los fondos según la decisión
        estado_escrow = 'Reembolsado por Disputa' if accion_fondos == 'devolver_cliente' else 'Liberado por Arbitraje'

        supabase.table('custodia_escrow').update({"estado": estado_escrow}).eq("contrato_id", contrato_id).execute()
        supabase.table('contratos').update({"estado": "Finalizado con Disputa"}).eq("id", contrato_id).execute()

        return jsonify({"message": "Disputa resuelta de manera oficial."}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
