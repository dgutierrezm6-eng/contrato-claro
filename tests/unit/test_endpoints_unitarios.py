import os
from backend import app as backend_module


def test_index_sirve_html_local(client, monkeypatch):
    monkeypatch.setattr(os.path, "exists", lambda p: p == "index.html")
    monkeypatch.setattr(backend_module, "send_file", lambda p: f"HTML:{p}")
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"index.html" in resp.data


def test_index_sirve_html_padre(client, monkeypatch):
    monkeypatch.setattr(os.path, "exists", lambda p: p == "../index.html")
    monkeypatch.setattr(backend_module, "send_file", lambda p: f"HTML:{p}")
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"index.html" in resp.data


def test_index_fallback_json(client, monkeypatch):
    monkeypatch.setattr(os.path, "exists", lambda _p: False)
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "API Contrato Claro en ejecución"


def test_crear_contrato_exitoso_con_hitos_y_escrow(client, fake_db):
    payload = {
        "titulo": "Desarrollo Web Corporativo",
        "tipo": "Servicios",
        "objeto": "Entrega de sitio web institucional",
        "monto_total": 1500000,
        "creador_id": "user-freelancer-1",
        "contraparte_email": "CLIENTE@contratoclaro.co",
        "hitos": [
            {"titulo": "Diseño UI", "monto": 500000},
            {"titulo": "Despliegue Final", "monto": 1000000},
        ],
    }
    resp = client.post("/api/contratos/crear", json=payload)
    data = resp.get_json()

    assert resp.status_code == 201
    assert data["contrato_id"] == 1
    assert len(data["hitos"]) == 2
    assert len(fake_db.tables["partes_contrato"]) == 2
    assert fake_db.tables["custodia_escrow"][0]["referencia_pago"] == "TXN-1-INIT"


def test_crear_contrato_rechaza_datos_obligatorios_faltantes(client):
    resp = client.post("/api/contratos/crear", json={"titulo": "Sin creador"})
    assert resp.status_code == 400
    assert "Faltan datos obligatorios" in resp.get_json()["error"]


def test_crear_contrato_falla_si_db_no_retorna_registro(client, fake_db):
    fake_db.force_empty_insert = True
    resp = client.post("/api/contratos/crear", json={"titulo": "Test", "creador_id": "user-freelancer-1"})
    assert resp.status_code == 500
    assert "No se pudo registrar" in resp.get_json()["error"]


def test_crear_contrato_maneja_excepcion_db(client, fake_db):
    fake_db.force_error = True
    resp = client.post("/api/contratos/crear", json={"titulo": "Test", "creador_id": "user-freelancer-1"})
    assert resp.status_code == 500


def test_depositar_escrow_exitoso(client, fake_db):
    fake_db.tables["contratos"].append({"id": 10, "titulo": "App Móvil", "estado": "Pendiente"})
    resp = client.post("/api/escrow/depositar", json={"contrato_id": 10, "monto": 800000})
    assert resp.status_code == 201
    assert fake_db.tables["contratos"][0]["estado"] == "Activo (Fondeado)"
    assert fake_db.tables["custodia_escrow"][0]["referencia_pago"] == "TXN-10-DEP"


def test_depositar_escrow_datos_incompletos(client):
    resp = client.post("/api/escrow/depositar", json={"contrato_id": 10})
    assert resp.status_code == 400


def test_liberar_escrow_por_hito_y_cierre_automatico_contrato(client, fake_db):
    fake_db.tables["contratos"].append({"id": 5, "estado": "Activo (Fondeado)"})
    fake_db.tables["hitos_contrato"].append({"id": 50, "contrato_id": 5, "estado": "Pendiente"})
    fake_db.tables["custodia_escrow"].append({"id": 90, "contrato_id": 5, "estado": "En Custodia"})

    resp = client.post("/api/escrow/liberar", json={"contrato_id": 5, "hito_id": 50})
    assert resp.status_code == 200
    assert fake_db.tables["hitos_contrato"][0]["estado"] == "Liberado"
    assert fake_db.tables["custodia_escrow"][0]["estado"] == "Liberado"
    assert fake_db.tables["contratos"][0]["estado"] == "Finalizado"


def test_liberar_escrow_directo_por_escrow_id(client, fake_db):
    fake_db.tables["custodia_escrow"].append({"id": 77, "contrato_id": 8, "estado": "En Custodia"})
    resp = client.post("/api/escrow/liberar", json={"escrow_id": 77})
    assert resp.status_code == 200
    assert fake_db.tables["custodia_escrow"][0]["estado"] == "Liberado"


def test_liberar_escrow_sin_identificadores(client):
    resp = client.post("/api/escrow/liberar", json={})
    assert resp.status_code == 400


def test_resolver_disputa_devolver_cliente(client, fake_db):
    fake_db.tables["contratos"].append({"id": 3, "estado": "En Disputa"})
    fake_db.tables["custodia_escrow"].append({"id": 30, "contrato_id": 3, "estado": "En Custodia"})
    fake_db.tables["disputas"].append({"id": 100, "contrato_id": 3, "estado": "ABIERTA"})

    resp = client.post("/api/disputas/resolver", json={
        "disputa_id": 100,
        "resolucion": "Incumplimiento comprobado",
        "accion_fondos": "devolver_cliente",
    })
    assert resp.status_code == 200
    assert fake_db.tables["custodia_escrow"][0]["estado"] == "Reembolsado por Disputa"
    assert fake_db.tables["contratos"][0]["estado"] == "Cancelado con Reembolso"


def test_resolver_disputa_pagar_freelancer(client, fake_db):
    fake_db.tables["contratos"].append({"id": 4, "estado": "En Disputa"})
    fake_db.tables["custodia_escrow"].append({"id": 40, "contrato_id": 4, "estado": "En Custodia"})
    fake_db.tables["disputas"].append({"id": 101, "contrato_id": 4, "estado": "ABIERTA"})

    resp = client.post("/api/disputas/resolver", json={
        "disputa_id": 101,
        "accion_fondos": "pagar_freelancer",
    })
    assert resp.status_code == 200
    assert fake_db.tables["custodia_escrow"][0]["estado"] == "Liberado por Arbitraje"
    assert fake_db.tables["contratos"][0]["estado"] == "Finalizado con Disputa"


def test_resolver_disputa_no_encontrada_y_sin_id(client):
    assert client.post("/api/disputas/resolver", json={}).status_code == 400
    assert client.post("/api/disputas/resolver", json={"disputa_id": 999}).status_code == 404
