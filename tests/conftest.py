import os
import copy
import pytest

# Variables ficticias para permitir importar backend.app sin tocar Supabase real
os.environ.setdefault("SUPABASE_URL", "https://mock-proyecto.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "mock-service-role-key")

from backend import app as backend_module


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, storage, table_name):
        self.storage = storage
        self.table_name = table_name
        self._op = "select"
        self._payload = None
        self._filters = []
        self._single = False
        self._maybe_single = False

    def insert(self, payload):
        self._op = "insert"
        self._payload = payload
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = payload
        return self

    def select(self, _cols="*"):
        self._op = "select"
        return self

    def eq(self, col, val):
        self._filters.append((col, val))
        return self

    def single(self):
        self._single = True
        return self

    def maybe_single(self):
        self._maybe_single = True
        return self

    def execute(self):
        if self.storage.force_error:
            raise RuntimeError("Fallo simulado de conexión con Supabase")

        rows = self.storage.tables.setdefault(self.table_name, [])

        if self._op == "insert":
            if self.storage.force_empty_insert:
                return FakeResponse([])
            items = self._payload if isinstance(self._payload, list) else [self._payload]
            inserted = []
            for item in items:
                record = copy.deepcopy(item)
                if "id" not in record:
                    record["id"] = len(rows) + 1
                rows.append(record)
                inserted.append(copy.deepcopy(record))
            return FakeResponse(inserted)

        matched = [
            r for r in rows
            if all(r.get(col) == val for col, val in self._filters)
        ]

        if self._op == "update":
            updated = []
            for r in matched:
                r.update(copy.deepcopy(self._payload))
                updated.append(copy.deepcopy(r))
            return FakeResponse(updated)

        if self._single or self._maybe_single:
            return FakeResponse(copy.deepcopy(matched[0]) if matched else None)

        return FakeResponse(copy.deepcopy(matched))


class FakeSupabase:
    def __init__(self):
        self.tables = {
            "contratos": [],
            "perfiles_usuario": [
                {"id": "user-freelancer-1", "correo": "freelancer@contratoclaro.co", "rol": "Freelancer"},
                {"id": "user-cliente-2", "correo": "cliente@contratoclaro.co", "rol": "Cliente o Contratante"},
            ],
            "partes_contrato": [],
            "hitos_contrato": [],
            "custodia_escrow": [],
            "disputas": [],
        }
        self.force_error = False
        self.force_empty_insert = False

    def table(self, name):
        return FakeQuery(self, name)


@pytest.fixture
def fake_db(monkeypatch):
    db = FakeSupabase()
    monkeypatch.setattr(backend_module, "supabase", db)
    return db


@pytest.fixture
def client(fake_db):
    backend_module.app.config["TESTING"] = True
    with backend_module.app.test_client() as test_client:
        yield test_client
