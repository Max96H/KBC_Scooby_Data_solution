import os
import sys
import tempfile
from pathlib import Path

import pytest

# Base de test isolée, configurée AVANT tout import de l'application
_TMP = Path(tempfile.mkdtemp(prefix="moments-test-"))
os.environ["DB_PATH"] = str(_TMP / "test.db")
os.environ["DEMO_PASSWORD"] = "Test-Password-123"
os.environ["SECRET_KEY"] = "test-secret-key-for-pytest-only-0123456789"
os.environ["GEMINI_API_KEY"] = ""
os.environ["ELEVENLABS_API_KEY"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import get_conn  # noqa: E402
from app.main import app  # noqa: E402
from app.security import login_limiter  # noqa: E402
from data import generate  # noqa: E402

PASSWORD = os.environ["DEMO_PASSWORD"]
_BUILT = generate.build()


@pytest.fixture()
def fresh_db():
    generate.write(_BUILT, settings.db_path)
    login_limiter._hits.clear()
    yield settings.db_path


@pytest.fixture()
def client(fresh_db):
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def conn(fresh_db):
    with get_conn() as c:
        yield c


def login(client, username):
    r = client.post("/api/auth/login", json={"username": username, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}
