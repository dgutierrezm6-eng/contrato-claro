import os
import sys

sys.path.insert(0, os.getcwd())

from tests.conftest import FakeSupabase
from backend import app as backend_module

db = FakeSupabase()
backend_module.supabase = db

if __name__ == "__main__":
    backend_module.app.run(host="127.0.0.1", port=5003, debug=False, threaded=True)
