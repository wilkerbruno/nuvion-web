from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint_responds():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert "status" in body
    assert body["status"] in {"ok", "degraded"}


def test_auth_login_route_exists_and_validates_body():
    # Login já é implementação real desde a Fase 1 (ver tests/test_auth.py
    # para o fluxo completo) — aqui só confirmamos que a rota existe e
    # rejeita corpo vazio (422), em vez de 404.
    response = client.post("/auth/login")
    assert response.status_code == 422
