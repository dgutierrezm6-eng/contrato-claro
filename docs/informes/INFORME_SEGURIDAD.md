# Informe de Seguridad - Contrato Claro

- **Aislamiento etico:** Ejecutado exclusivamente en 127.0.0.1 y entorno mock local (sin escaneos a dominios ajenos).

## 1. Analisis Estatico SAST (Bandit)
- **DEF-002 [B201 - HIGH]:** debug=True fijo -> remediado con FLASK_DEBUG=False.
- **DEF-003 [B104 - MEDIUM]:** host 0.0.0.0 fijo -> remediado con HOST=127.0.0.1.
- **Verificacion final:** bandit -r backend/ -> 0 vulnerabilidades.

## 2. Dependencias (pip-audit)
- backend/requirements.txt -> 0 CVEs conocidos.

## 3. Seguridad Dinamica API (pytest)
- 4 pruebas aprobadas: ausencia de Service Role Key, resiliencia XSS/SQLi, manejo seguro de JSON invalido y cabeceras CORS.
