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

    server = make_server("127.0.0.1", 5004, backend_module.app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:5004"
    server.shutdown()


def _auditar_pagina_axe(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded")
        page.add_script_tag(url="https://unpkg.com/axe-core@4.10.2/axe.min.js")
        resultados = page.evaluate("async () => await axe.run()")
        browser.close()
        return resultados


@pytest.mark.parametrize("ruta,nombre", [("/", "index.html"), ("/admin.html", "admin.html")])
def test_accesibilidad_wcag_aa(live_server, ruta, nombre):
    resultados = _auditar_pagina_axe(f"{live_server}{ruta}")
    violaciones = resultados.get("violations", [])

    criticas_o_serias = [
        v for v in violaciones if v.get("impact") in ("critical", "serious")
    ]
    menores_o_moderadas = [
        v for v in violaciones if v.get("impact") not in ("critical", "serious")
    ]

    print(
        f"\n[axe-core] {nombre}: {len(resultados.get('passes', []))} reglas aprobadas, "
        f"{len(criticas_o_serias)} críticas/serias, {len(menores_o_moderadas)} moderadas/menores."
    )

    for v in violaciones:
        print(f"  - [{v['impact'].upper()}] {v['id']}: {v['help']} ({len(v['nodes'])} nodos)")

    assert len(criticas_o_serias) == 0, (
        f"Se encontraron {len(criticas_o_serias)} violaciones críticas/serias en {nombre}: "
        + ", ".join(v["id"] for v in criticas_o_serias)
    )
