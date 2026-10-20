"""Tests de integración de /rooms: peticiones HTTP reales contra la app."""

import pytest

pytestmark = pytest.mark.integration

AULA = {
    "nombre": "Laboratorio de Robótica",
    "edificio": "Edificio A",
    "capacidad": 30,
    "equipamiento": ["ordenadores", "robots", "impresora 3D"],
}


def test_listar_aulas_vacio(client):
    response = client.get("/rooms")
    assert response.status_code == 200
    assert response.json() == []


def test_crear_aula(client):
    response = client.post("/rooms", json=AULA)
    assert response.status_code == 201
    assert response.json() == {"id": 1, **AULA}


def test_crear_aula_sin_equipamiento(client):
    datos = {k: v for k, v in AULA.items() if k != "equipamiento"}
    response = client.post("/rooms", json=datos)
    assert response.status_code == 201
    assert response.json()["equipamiento"] == []


@pytest.mark.parametrize("capacidad", [0, -1])
def test_crear_aula_capacidad_invalida(client, capacidad):
    response = client.post("/rooms", json={**AULA, "capacidad": capacidad})
    assert response.status_code == 422


def test_obtener_aula(client):
    aula_id = client.post("/rooms", json=AULA).json()["id"]
    response = client.get(f"/rooms/{aula_id}")
    assert response.status_code == 200
    assert response.json()["nombre"] == AULA["nombre"]


def test_obtener_aula_inexistente(client):
    assert client.get("/rooms/999").status_code == 404


def test_listar_aulas(client):
    client.post("/rooms", json=AULA)
    client.post("/rooms", json={**AULA, "nombre": "Aula 2.1"})
    assert len(client.get("/rooms").json()) == 2


def test_eliminar_aula(client):
    aula_id = client.post("/rooms", json=AULA).json()["id"]
    assert client.delete(f"/rooms/{aula_id}").status_code == 204
    assert client.get(f"/rooms/{aula_id}").status_code == 404


def test_eliminar_aula_inexistente(client):
    assert client.delete("/rooms/999").status_code == 404
