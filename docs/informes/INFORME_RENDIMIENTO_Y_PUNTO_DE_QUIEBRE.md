# Informe de Rendimiento y Punto de Quiebre - Contrato Claro

- **Entorno:** http://127.0.0.1:5003 (100% local con FakeSupabase, cero trafico a sistemas externos).
- **Herramienta:** Grafana k6.

## 1. Carga Nominal (SLA)
- **Concurrencia:** 15 VUs durante 18s.
- **Resultados:** 1,002 iteraciones (4,008 peticiones), 0.00% errores, Throughput 220.90 req/s, p95 = 7.46 ms (SLA < 300 ms).

## 2. Punto de Quiebre (Estres hasta 250 VUs)
- Al superar ~150 VUs concurrentes sin pausa, el servidor monoproceso Werkzeug supera el SLA de 300 ms en p95.
- **Recomendacion:** Desplegar con Gunicorn multiproceso (gunicorn -w 4 -k gthread --threads 4 backend.app:app).
