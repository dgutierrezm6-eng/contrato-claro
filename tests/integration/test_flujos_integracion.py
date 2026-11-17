def test_flujo_completo_contrato_multihito_y_cierre_escrow(client, fake_db):
    """
    Flujo integral a nivel de API + estado relacional:
    1. Crear contrato con 2 hitos y fondeo inicial.
    2. Realizar un depósito adicional en Escrow.
    3. Liberar el primer hito (el contrato debe seguir Activo).
    4. Liberar el segundo hito (el contrato y el Escrow deben cerrarse automáticamente).
    """
    resp_crear = client.post("/api/contratos/crear", json={
        "titulo": "Plataforma E-Commerce",
        "tipo": "Desarrollo Software",
        "objeto": "Tienda online con pasarela de pagos",
        "monto_total": 2000000,
        "creador_id": "user-freelancer-1",
        "contraparte_email": "cliente@contratoclaro.co",
        "hitos": [
            {"titulo": "Hito 1: Catálogo y Carrito", "monto": 1000000},
            {"titulo": "Hito 2: Checkout y Producción", "monto": 1000000},
        ],
    })
    assert resp_crear.status_code == 201
    contrato_id = resp_crear.get_json()["contrato_id"]
    hitos_creados = resp_crear.get_json()["hitos"]

    resp_dep = client.post("/api/escrow/depositar", json={
        "contrato_id": contrato_id,
        "monto": 500000,
    })
    assert resp_dep.status_code == 201
    assert len(fake_db.tables["custodia_escrow"]) == 2

    resp_lib_1 = client.post("/api/escrow/liberar", json={
        "contrato_id": contrato_id,
        "hito_id": hitos_creados[0]["id"],
    })
    assert resp_lib_1.status_code == 200
    assert fake_db.tables["contratos"][0]["estado"] == "Activo (Fondeado)"
    assert all(e["estado"] == "En Custodia" for e in fake_db.tables["custodia_escrow"])

    resp_lib_2 = client.post("/api/escrow/liberar", json={
        "contrato_id": contrato_id,
        "hito_id": hitos_creados[1]["id"],
    })
    assert resp_lib_2.status_code == 200
    assert fake_db.tables["contratos"][0]["estado"] == "Finalizado"
    assert all(e["estado"] == "Liberado" for e in fake_db.tables["custodia_escrow"])


def test_flujo_integracion_contrato_a_disputa_y_reembolso(client, fake_db):
    """
    Verifica la consistencia entre creación de contrato, apertura de disputa
    y dictamen final con reembolso al cliente.
    """
    resp_crear = client.post("/api/contratos/crear", json={
        "titulo": "Auditoría SEO",
        "monto_total": 600000,
        "creador_id": "user-freelancer-1",
    })
    contrato_id = resp_crear.get_json()["contrato_id"]

    fake_db.tables["disputas"].append({
        "id": 10,
        "contrato_id": contrato_id,
        "estado": "ABIERTA",
    })

    resp_res = client.post("/api/disputas/resolver", json={
        "disputa_id": 10,
        "resolucion": "Retraso injustificado en entregables",
        "accion_fondos": "devolver_cliente",
    })
    assert resp_res.status_code == 200
    assert fake_db.tables["disputas"][0]["estado"] == "RESUELTA"
    assert fake_db.tables["custodia_escrow"][0]["estado"] == "Reembolsado por Disputa"
    assert fake_db.tables["contratos"][0]["estado"] == "Cancelado con Reembolso"


def test_integracion_entrega_archivos_frontend_reales(client):
    """Verifica que Flask sirva los archivos estáticos reales index.html y admin.html."""
    resp_index = client.get("/index.html")
    resp_admin = client.get("/admin.html")
    assert resp_index.status_code == 200
    assert b"<html" in resp_index.data.lower()
    assert resp_admin.status_code == 200
    assert b"<html" in resp_admin.data.lower()


def test_resiliencia_ante_caida_supabase_en_escrow_y_disputas(client, fake_db):
    """Verifica que todos los endpoints capturen excepciones de red/BD sin colapsar."""
    fake_db.force_error = True

    r1 = client.post("/api/escrow/depositar", json={"contrato_id": 1, "monto": 100})
    r2 = client.post("/api/escrow/liberar", json={"contrato_id": 1})
    r3 = client.post("/api/disputas/resolver", json={"disputa_id": 1})

    assert r1.status_code == 500
    assert r2.status_code == 500
    assert r3.status_code == 500
