"""Reglas de negocio. No saben nada de HTTP: reciben datos y lanzan errores propios.

Así se pueden probar con tests unitarios sin levantar la API, y main.py solo
traduce cada error a su código HTTP.
"""

from datetime import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas


class NotFoundError(Exception):
    """El aula o la reserva no existe (404)."""


class InvalidDataError(Exception):
    """Los datos rompen una regla de negocio (400)."""


class ConflictError(Exception):
    """La reserva choca con otra ya existente (409)."""


# --- Validaciones puras -------------------------------------------------------


def validar_capacidad(capacidad: int) -> None:
    if capacidad <= 0:
        raise InvalidDataError("La capacidad tiene que ser mayor que 0")


def validar_horas(hora_inicio: time, hora_fin: time) -> None:
    if hora_inicio >= hora_fin:
        raise InvalidDataError("hora_inicio tiene que ser anterior a hora_fin")


def se_solapan(inicio_a: time, fin_a: time, inicio_b: time, fin_b: time) -> bool:
    """Dos franjas se solapan si cada una empieza antes de que acabe la otra.

    Que una acabe justo cuando empieza la otra (10-12 y 12-13) no es solape.
    """
    return inicio_a < fin_b and inicio_b < fin_a


# --- Aulas --------------------------------------------------------------------


def listar_aulas(db: Session) -> list[models.Room]:
    return list(db.scalars(select(models.Room)))


def obtener_aula(db: Session, aula_id: int) -> models.Room:
    aula = db.get(models.Room, aula_id)
    if aula is None:
        raise NotFoundError(f"El aula {aula_id} no existe")
    return aula


def crear_aula(db: Session, datos: schemas.RoomCreate) -> models.Room:
    validar_capacidad(datos.capacidad)
    aula = models.Room(**datos.model_dump())
    db.add(aula)
    db.commit()
    db.refresh(aula)
    return aula


def eliminar_aula(db: Session, aula_id: int) -> None:
    aula = obtener_aula(db, aula_id)
    db.delete(aula)
    db.commit()


# --- Reservas -----------------------------------------------------------------


def listar_reservas(db: Session) -> list[models.Booking]:
    return list(db.scalars(select(models.Booking)))


def crear_reserva(db: Session, datos: schemas.BookingCreate) -> models.Booking:
    obtener_aula(db, datos.aula_id)
    validar_horas(datos.hora_inicio, datos.hora_fin)

    mismas_aula_y_fecha = db.scalars(
        select(models.Booking).where(
            models.Booking.aula_id == datos.aula_id,
            models.Booking.fecha == datos.fecha,
        )
    )
    for existente in mismas_aula_y_fecha:
        if se_solapan(
            datos.hora_inicio, datos.hora_fin, existente.hora_inicio, existente.hora_fin
        ):
            raise ConflictError(
                f"El aula {datos.aula_id} ya está reservada de "
                f"{existente.hora_inicio:%H:%M} a {existente.hora_fin:%H:%M}"
            )

    reserva = models.Booking(**datos.model_dump())
    db.add(reserva)
    db.commit()
    db.refresh(reserva)
    return reserva


def eliminar_reserva(db: Session, reserva_id: int) -> None:
    reserva = db.get(models.Booking, reserva_id)
    if reserva is None:
        raise NotFoundError(f"La reserva {reserva_id} no existe")
    db.delete(reserva)
    db.commit()
