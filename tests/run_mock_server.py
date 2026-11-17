import os
import sys

sys.path.insert(0, os.getcwd())

from tests.conftest import FakeSupabase
from backend import app as backend_module

db = FakeSupabase()
db.tables["disputas"].append({
    "id": 1,
    "contrato_id": 1,
    "estado": "ABIERTA",
})
backend_module.supabase = db

if __name__ == "__main__":
    print("Servidor de pruebas Contrato Claro activo en http://127.0.0.1:5001")
    backend_module.app.run(host="127.0.0.1", port=5001, debug=False)
