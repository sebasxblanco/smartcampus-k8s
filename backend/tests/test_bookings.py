"""Tests de integración de /bookings: peticiones HTTP reales contra la app."""

import pytest

pytestmark = pytest.mark.integration

AULA = {"nombre": "Laboratorio A", "edificio": "Edificio A", "capacidad": 30}


@pytest.fixture
def aula_id(client):
    return client.post("/rooms", json=AULA).json()["id"]


def reserva(aula_id, inicio="10:00", fin="12:00"):
    return {
        "aula_id": aula_id,
        "usuario": "sebastian",
        "fecha": "2026-11-02",
        "hora_inicio": inicio,
        "hora_fin": fin,
    }


def test_listar_reservas_vacio(client):
    response = client.get("/bookings")
    assert response.status_code == 200
    assert response.json() == []


def test_crear_reserva(client, aula_id):
    response = client.post("/bookings", json=reserva(aula_id))
    assert response.status_code == 201
    cuerpo = response.json()
    assert cuerpo["id"] == 1
    assert cuerpo["hora_inicio"] == "10:00:00"


def test_listar_reservas(client, aula_id):
    client.post("/bookings", json=reserva(aula_id))
    assert len(client.get("/bookings").json()) == 1


def test_reserva_aula_inexistente(client):
    assert client.post("/bookings", json=reserva(999)).status_code == 404


def test_reserva_hora_incorrecta(client, aula_id):
    response = client.post("/bookings", json=reserva(aula_id, "12:00", "10:00"))
    assert response.status_code == 400


def test_reserva_solapada(client, aula_id):
    client.post("/bookings", json=reserva(aula_id, "10:00", "12:00"))
    response = client.post("/bookings", json=reserva(aula_id, "11:00", "13:00"))
    assert response.status_code == 409


def test_eliminar_reserva(client, aula_id):
    reserva_id = client.post("/bookings", json=reserva(aula_id)).json()["id"]
    assert client.delete(f"/bookings/{reserva_id}").status_code == 204
    assert client.get("/bookings").json() == []


def test_eliminar_reserva_inexistente(client):
    assert client.delete("/bookings/999").status_code == 404
