import os


def test_no_hay_service_role_key_expuesta_en_repositorio():
    """Verifica que la llave privilegiada service_role no esté escrita en backend ni frontend."""
    archivos_revisar = ["backend/app.py", "index.html", "admin.html"]
    for ruta in archivos_revisar:
        if os.path.exists(ruta):
            with open(ruta, "r", encoding="utf-8") as f:
                contenido = f.read().lower()
            assert "service_role" not in contenido or "os.getenv" in contenido, (
                f"Posible exposición de service_role en {ruta}"
            )


def test_resiliencia_ante_payloads_xss_y_sqli(client, fake_db):
    """Verifica que entradas con scripts XSS o inyección SQL no rompan el backend ni filtren trazas."""
    payload_malicioso = {
        "titulo": "<script>alert('XSS')</script>'; DROP TABLE contratos;--",
        "tipo": "' OR '1'='1",
        "objeto": "<img src=x onerror=alert(1)>",
        "monto_total": 500000,
        "creador_id": "user-freelancer-1",
        "contraparte_email": "atacante@evil.com' OR 1=1--",
        "hitos": [{"titulo": "Hito <script>evil()</script>", "monto": 500000}],
    }
    resp = client.post("/api/contratos/crear", json=payload_malicioso)
    assert resp.status_code == 201
    cuerpo = resp.get_text() if hasattr(resp, "get_text") else resp.data.decode("utf-8")
    assert "Traceback" not in cuerpo
    assert "/Users/" not in cuerpo


def test_rechazo_json_invalido_sin_fuga_de_stacktrace(client):
    """Verifica que enviar texto corrupto como JSON no exponga errores internos del servidor."""
    resp = client.post(
        "/api/contratos/crear",
        data="{json_corrupto: sin_comillas",
        content_type="application/json",
    )
    assert resp.status_code in (400, 500)
    texto = resp.data.decode("utf-8")
    assert "Traceback (most recent call last)" not in texto


def test_cabeceras_cors_habilitadas(client):
    """Verifica que la API incluya cabeceras CORS configuradas."""
    resp = client.options("/api/contratos/crear", headers={"Origin": "https://contratoclaro.vercel.app"})
    assert resp.status_code in (200, 204)
    assert "Access-Control-Allow-Origin" in resp.headers
