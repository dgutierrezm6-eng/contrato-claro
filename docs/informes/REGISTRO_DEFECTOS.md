# Registro de Defectos Reproducibles - Contrato Claro

| ID | Severidad | Componente | Descripcion | Estado |
| :--- | :--- | :--- | :--- | :--- |
| DEF-001 | Alta | backend/app.py | Falla de ruta relativa en send_file | Cerrado |
| DEF-002 | Alta | backend/app.py | debug=True expuesto (Bandit B201) | Cerrado |
| DEF-003 | Media | backend/app.py | host 0.0.0.0 fijo (Bandit B104) | Cerrado |
| DEF-004 | Media | index.html, admin.html | Contraste insuficiente #627d98 (4.28:1) | Cerrado |
| DEF-005 | Media | index.html, admin.html | Contraste insuficiente #00a6a6 (2.99:1) | Cerrado |

## Pasos Reproducibles

### DEF-001 - Ruta relativa en send_file
- **Pasos:** Iniciar servidor desde raiz y ejecutar GET / o GET /admin.html.
- **Esperado vs Obtenido:** HTTP 200 con HTML vs FileNotFoundError.
- **Solucion:** os.path.abspath() en backend/app.py.

### DEF-002 - Modo debug=True (B201)
- **Pasos:** Ejecutar bandit -r backend/.
- **Esperado vs Obtenido:** debug=False por defecto vs High [B201].
- **Solucion:** FLASK_DEBUG=False por defecto.

### DEF-003 - Interfaz abierta 0.0.0.0 (B104)
- **Pasos:** Ejecutar bandit -r backend/.
- **Esperado vs Obtenido:** HOST=127.0.0.1 vs Medium [B104].
- **Solucion:** HOST=127.0.0.1 por defecto.

### DEF-004 - Contraste textos #627d98
- **Pasos:** Auditar / y /admin.html con axe-core.
- **Esperado vs Obtenido:** Ratio >= 4.5:1 vs 4.28:1 y 3.87:1.
- **Solucion:** Reemplazo por #486581 (6.08:1).

### DEF-005 - Contraste botones #00a6a6
- **Pasos:** Auditar .btn-primary con axe-core.
- **Esperado vs Obtenido:** Ratio >= 4.5:1 vs 2.99:1.
- **Solucion:** Reemplazo por #007a7a (5.17:1).
