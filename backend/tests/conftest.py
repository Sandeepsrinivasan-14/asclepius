import pytest
from fastapi.testclient import TestClient

from asclepius.config import Settings
from asclepius.main import create_app


@pytest.fixture(scope="module")
def app():
    return create_app(Settings(db_path=":memory:", seed=2026, n_patients=64))


@pytest.fixture(scope="module")
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def login(client):
    cache: dict[str, dict[str, str]] = {}

    def _login(user: str) -> dict[str, str]:
        if user not in cache:
            r = client.post("/api/auth/login", json={"username": user})
            assert r.status_code == 200
            cache[user] = {"Authorization": "Bearer " + r.json()["token"]}
        return cache[user]

    return _login


@pytest.fixture(scope="module")
def rao(login):
    return login("dr.rao")
