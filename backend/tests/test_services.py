"""Tests unitarios: reglas de negocio llamadas directamente, sin pasar por HTTP."""

from datetime import date, time

import pytest

from app import schemas, services

pytestmark = pytest.mark.unit

FECHA = date(2026, 11, 2)


def aula(capacidad=30):
    return schemas.RoomCreate.model_construct(
        nombre="Laboratorio de Robótica",
        edificio="Edificio A",
        capacidad=capacidad,
        equipamiento=["ordenadores", "robots"],
    )


def reserva(aula_id, inicio, fin):
    return schemas.BookingCreate(
        aula_id=aula_id,
        usuario="sebastian",
        fecha=FECHA,
        hora_inicio=inicio,
        hora_fin=fin,
    )


# --- Validaciones puras -------------------------------------------------------


def test_capacidad_valida():
    services.validar_capacidad(1)


@pytest.mark.parametrize("capacidad", [0, -5])
def test_capacidad_invalida(capacidad):
    with pytest.raises(services.InvalidDataError):
        services.validar_capacidad(capacidad)


def test_horas_validas():
    services.validar_horas(time(10), time(12))


@pytest.mark.parametrize("inicio, fin", [(time(12), time(10)), (time(10), time(10))])
def test_horas_invalidas(inicio, fin):
    with pytest.raises(services.InvalidDataError):
        services.validar_horas(inicio, fin)


@pytest.mark.parametrize(
    "a, b, esperado",
    [
        ((10, 12), (11, 13), True),  # se pisan por el final
        ((10, 12), (9, 11), True),  # se pisan por el principio
        ((10, 12), (10, 12), True),  # idénticas
        ((10, 14), (11, 12), True),  # una dentro de otra
        ((10, 12), (12, 13), False),  # contiguas: no es solape
        ((10, 12), (13, 14), False),  # separadas
    ],
)
def test_se_solapan(a, b, esperado):
    assert services.se_solapan(time(a[0]), time(a[1]), time(b[0]), time(b[1])) is (
        esperado
    )


# --- Aulas --------------------------------------------------------------------


def test_crear_aula(db):
    creada = services.crear_aula(db, aula())
    assert creada.id is not None
    assert creada.equipamiento == ["ordenadores", "robots"]


def test_crear_aula_capacidad_invalida(db):
    with pytest.raises(services.InvalidDataError):
        services.crear_aula(db, aula(capacidad=0))


def test_eliminar_aula(db):
    creada = services.crear_aula(db, aula())
    services.eliminar_aula(db, creada.id)
    assert services.listar_aulas(db) == []


def test_eliminar_aula_inexistente(db):
    with pytest.raises(services.NotFoundError):
        services.eliminar_aula(db, 999)


def test_eliminar_aula_borra_sus_reservas(db):
    creada = services.crear_aula(db, aula())
    services.crear_reserva(db, reserva(creada.id, time(10), time(12)))
    services.eliminar_aula(db, creada.id)
    assert services.listar_reservas(db) == []


# --- Reservas -----------------------------------------------------------------


def test_crear_reserva(db):
    creada = services.crear_aula(db, aula())
    r = services.crear_reserva(db, reserva(creada.id, time(10), time(12)))
    assert r.id is not None


def test_reserva_aula_inexistente(db):
    with pytest.raises(services.NotFoundError):
        services.crear_reserva(db, reserva(999, time(10), time(12)))


def test_reserva_hora_incorrecta(db):
    creada = services.crear_aula(db, aula())
    with pytest.raises(services.InvalidDataError):
        services.crear_reserva(db, reserva(creada.id, time(12), time(10)))


def test_reserva_solapada(db):
    creada = services.crear_aula(db, aula())
    services.crear_reserva(db, reserva(creada.id, time(10), time(12)))
    with pytest.raises(services.ConflictError):
        services.crear_reserva(db, reserva(creada.id, time(11), time(13)))


def test_reserva_contigua_permitida(db):
    creada = services.crear_aula(db, aula())
    services.crear_reserva(db, reserva(creada.id, time(10), time(12)))
    services.crear_reserva(db, reserva(creada.id, time(12), time(13)))
    assert len(services.listar_reservas(db)) == 2


def test_misma_hora_en_otra_aula_permitida(db):
    a1 = services.crear_aula(db, aula())
    a2 = services.crear_aula(db, aula())
    services.crear_reserva(db, reserva(a1.id, time(10), time(12)))
    services.crear_reserva(db, reserva(a2.id, time(10), time(12)))
    assert len(services.listar_reservas(db)) == 2


def test_eliminar_reserva_inexistente(db):
    with pytest.raises(services.NotFoundError):
        services.eliminar_reserva(db, 999)
