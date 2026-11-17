import os
import sys

sys.path.insert(0, os.getcwd())

from behave import given, when, then
from tests.conftest import FakeSupabase
from backend import app as backend_module


def _inicializar_entorno(context):
    context.db = FakeSupabase()
    backend_module.supabase = context.db
    backend_module.app.config["TESTING"] = True
    context.client = backend_module.app.test_client()


@given("que el sistema Contrato Claro está inicializado con usuarios registrados")
def step_init_sistema(context):
    _inicializar_entorno(context)


@when('el freelancer "{creador_id}" crea el contrato "{titulo}" por {monto:d} pesos con {num_hitos:d} hitos')
def step_crear_contrato(context, creador_id, titulo, monto, num_hitos):
    monto_hito = monto // num_hitos
    hitos = [
        {"titulo": f"Hito {i + 1}", "monto": monto_hito}
        for i in range(num_hitos)
    ]
    resp = context.client.post("/api/contratos/crear", json={
        "titulo": titulo,
        "tipo": "Servicios Profesionales",
        "objeto": "Entregables acordados por hitos",
        "monto_total": monto,
        "creador_id": creador_id,
        "contraparte_email": "cliente@contratoclaro.co",
        "hitos": hitos,
    })
    assert resp.status_code == 201
    context.contrato_data = resp.get_json()


@then('el contrato queda registrado en estado "{estado}" con {monto:d} pesos en custodia')
def step_verificar_contrato_y_escrow(context, estado, monto):
    contrato = context.db.tables["contratos"][0]
    escrow = context.db.tables["custodia_escrow"][0]
    assert contrato["estado"] == estado
    assert escrow["monto"] == monto
    assert escrow["estado"] == "En Custodia"


@when("se liberan los {num_hitos:d} hitos del contrato")
def step_liberar_hitos(context, num_hitos):
    hitos = context.contrato_data["hitos"]
    assert len(hitos) == num_hitos
    contrato_id = context.contrato_data["contrato_id"]
    for h in hitos:
        resp = context.client.post("/api/escrow/liberar", json={
            "contrato_id": contrato_id,
            "hito_id": h["id"],
        })
        assert resp.status_code == 200


@then('el estado final del contrato pasa a "{estado_contrato}" y el saldo en custodia queda "{estado_escrow}"')
def step_verificar_cierre_total(context, estado_contrato, estado_escrow):
    assert context.db.tables["contratos"][0]["estado"] == estado_contrato
    assert context.db.tables["custodia_escrow"][0]["estado"] == estado_escrow


@given("que existe un contrato activo por {monto:d} pesos con una disputa abierta")
def step_contrato_con_disputa(context, monto):
    _inicializar_entorno(context)
    resp = context.client.post("/api/contratos/crear", json={
        "titulo": "Consultoría Técnica",
        "monto_total": monto,
        "creador_id": "user-freelancer-1",
    })
    assert resp.status_code == 201
    contrato_id = resp.get_json()["contrato_id"]
    context.db.tables["disputas"].append({
        "id": 50,
        "contrato_id": contrato_id,
        "estado": "ABIERTA",
    })
    context.disputa_id = 50


@when('el árbitro resuelve la disputa con la acción "{accion}"')
def step_resolver_disputa(context, accion):
    resp = context.client.post("/api/disputas/resolver", json={
        "disputa_id": context.disputa_id,
        "resolucion": "Dictamen oficial emitido",
        "accion_fondos": accion,
    })
    assert resp.status_code == 200


@then('el contrato pasa a estado "{estado_contrato}" y el Escrow queda en "{estado_escrow}"')
def step_verificar_reembolso_disputa(context, estado_contrato, estado_escrow):
    assert context.db.tables["contratos"][0]["estado"] == estado_contrato
    assert context.db.tables["custodia_escrow"][0]["estado"] == estado_escrow
