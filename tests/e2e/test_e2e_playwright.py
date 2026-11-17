import threading
import pytest
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright

from tests.conftest import FakeSupabase
from backend import app as backend_module


@pytest.fixture(scope="module")
def live_server():
    db = FakeSupabase()
    backend_module.supabase = db
    backend_module.app.config["TESTING"] = True

    server = make_server("127.0.0.1", 5002, backend_module.app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:5002", db
    server.shutdown()


def test_e2e_renderizado_frontend_principal(live_server):
    base_url, _ = live_server
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        errores_js = []
        page.on("pageerror", lambda err: errores_js.append(str(err)))

        resp = page.goto(f"{base_url}/", wait_until="domcontentloaded")
        assert resp.status == 200
        assert len(page.title().strip()) > 0
        assert page.locator("body").inner_text().strip() != ""
        assert page.locator("button, input, select, a").count() > 0
        assert errores_js == [], f"Errores JS detectados en index.html: {errores_js}"
        browser.close()


def test_e2e_renderizado_panel_admin(live_server):
    base_url, _ = live_server
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        errores_js = []
        page.on("pageerror", lambda err: errores_js.append(str(err)))

        resp = page.goto(f"{base_url}/admin.html", wait_until="domcontentloaded")
        assert resp.status == 200
        assert page.locator("body").inner_text().strip() != ""
        assert page.locator("button, input, table, div").count() > 0
        assert errores_js == [], f"Errores JS detectados en admin.html: {errores_js}"
        browser.close()


def test_e2e_flujo_navegador_a_backend_contrato_y_escrow(live_server):
    base_url, db = live_server
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(f"{base_url}/", wait_until="domcontentloaded")

        resultado = page.evaluate("""async () => {
            const crearRes = await fetch('/api/contratos/crear', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    titulo: 'Contrato E2E Playwright',
                    tipo: 'Servicios',
                    objeto: 'Prueba integral desde Chromium',
                    monto_total: 900000,
                    creador_id: 'user-freelancer-1',
                    contraparte_email: 'cliente@contratoclaro.co',
                    hitos: [{ titulo: 'Hito Único E2E', monto: 900000 }]
                })
            });
            const creado = await crearRes.json();

            const depRes = await fetch('/api/escrow/depositar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    contrato_id: creado.contrato_id,
                    monto: 100000
                })
            });

            const libRes = await fetch('/api/escrow/liberar', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    contrato_id: creado.contrato_id,
                    hito_id: creado.hitos[0].id
                })
            });

            return {
                crearStatus: crearRes.status,
                depStatus: depRes.status,
                libStatus: libRes.status,
                contratoId: creado.contrato_id
            };
        }""")

        assert resultado["crearStatus"] == 201
        assert resultado["depStatus"] == 201
        assert resultado["libStatus"] == 200
        contrato = next(c for c in db.tables["contratos"] if c["id"] == resultado["contratoId"])
        assert contrato["estado"] == "Finalizado"
        browser.close()
