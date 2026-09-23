import os
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from supabase import create_client, Client
from dotenv import load_dotenv

# Cargar variables de entorno (.env)
load_dotenv()

app = Flask(__name__)
CORS(app)  # Permite peticiones desde el frontend

# ==============================================================================
# CONFIGURACIÓN SUPABASE (BACKEND)
# IMPORTANTE: El backend usa la 'SERVICE_ROLE_KEY', no la ANON_KEY del frontend.
# Esto le da permisos de administrador para mover fondos en Escrow y resolver disputas.
# ==============================================================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") 

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Faltan credenciales de Supabase en las variables de entorno.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==============================================================================
# 1. SERVIR EL FRONTEND (Tu HTML)
# ==============================================================================
@app.route('/')
def index():
    """Sirve el archivo index-limpio.html cuando entran a la raíz de la app"""
    return send_file('index-limpio.html')

# ==============================================================================
# 2. LÓGICA CRÍTICA: GESTIÓN DE ESCROW (CUSTODIA)
# ==============================================================================
@app.route('/api/escrow/depositar', methods=['POST'])
def depositar_escrow():
    """
    Simula o conecta con pasarela de pagos (ej. Stripe/Wompi).
    Congela el dinero y registra la custodia en la base de datos.
    """
    data = request.json
    contrato_id = data.get('contrato_id')
    monto = data.get('monto')
    
    if not contrato_id or not monto:
        return jsonify({"error": "Datos incompletos (contrato_id, monto)"}), 400

    try:
        # 1. Aquí iría la lógica de cobro con tarjeta (Stripe/MercadoPago)
        referencia = f"TXN-{contrato_id}-DEP"

        # 2. Registrar el Escrow en Supabase
        escrow_data = {
            "contrato_id": contrato_id,
            "monto": monto,
            "estado": "En Custodia",
            "referencia_pago": referencia
        }
        
        # Insertar en tabla CUSTODIA_ESCROW
        res_escrow = supabase.table('CUSTODIA_ESCROW').insert(escrow_data).execute()
        
        # 3. Actualizar estado del contrato
        supabase.table('CONTRATOS').update({"estado": "Activo (Fondeado)"}).eq("id", contrato_id).execute()

        return jsonify({"message": "Fondos asegurados en Escrow", "data": res_escrow.data}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/escrow/liberar', methods=['POST'])
def liberar_escrow():
    """
    Libera los fondos al Freelancer una vez se aprueba el hito o el contrato finaliza.
    """
    data = request.json
    escrow_id = data.get('escrow_id')
    
    try:
        # Aquí iría la lógica de transferencia real a la cuenta bancaria del Freelancer
        
        # Actualizar base de datos
        res = supabase.table('CUSTODIA_ESCROW').update({"estado": "Liberado"}).eq("id", escrow_id).execute()
        
        return jsonify({"message": "Fondos transferidos al contratista exitosamente", "data": res.data}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==============================================================================
# 3. LÓGICA CRÍTICA: RESOLUCIÓN DE DISPUTAS (ADMINISTRADOR)
# ==============================================================================
@app.route('/api/disputas/resolver', methods=['POST'])
def resolver_disputa():
    """
    Permite a un Administrador dictaminar hacia dónde va el dinero de un contrato congelado.
    """
    data = request.json
    disputa_id = data.get('disputa_id')
    resolucion_texto = data.get('resolucion')
    accion_fondos = data.get('accion_fondos') # 'devolver_cliente' o 'pagar_freelancer'

    try:
        # 1. Actualizar la disputa
        res_disputa = supabase.table('DISPUTAS').update({
            "estado": "Resuelta",
            "resolucion": resolucion_texto
        }).eq("id", disputa_id).execute()

        contrato_id = res_disputa.data[0]['contrato_id']

        # 2. Mover los fondos según la decisión
        if accion_fondos == 'devolver_cliente':
            estado_escrow = 'Reembolsado por Disputa'
        else:
            estado_escrow = 'Liberado por Arbitraje'

        supabase.table('CUSTODIA_ESCROW').update({"estado": estado_escrow}).eq("contrato_id", contrato_id).execute()
        supabase.table('CONTRATOS').update({"estado": "Finalizado con Disputa"}).eq("id", contrato_id).execute()

        return jsonify({"message": "Disputa resuelta de manera oficial."}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Ejecuta el servidor en el puerto 5000 (o el asignado por Render/Heroku)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
