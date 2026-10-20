import pytest


@pytest.mark.integration
def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.integration
def test_info_devuelve_el_entorno(client):
    response = client.get("/info")
    assert response.status_code == 200
    assert "env" in response.json()
