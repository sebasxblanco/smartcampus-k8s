from datetime import date, time

from sqlalchemy import JSON, Date, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Room(Base):
    """Tabla de aulas en la base de datos."""

    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100))
    edificio: Mapped[str] = mapped_column(String(100))
    capacidad: Mapped[int] = mapped_column(Integer)
    equipamiento: Mapped[list[str]] = mapped_column(JSON)

    # Al borrar un aula se borran también sus reservas.
    reservas: Mapped[list["Booking"]] = relationship(
        back_populates="aula", cascade="all, delete-orphan"
    )


class Booking(Base):
    """Tabla de reservas de aulas."""

    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    aula_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"))
    usuario: Mapped[str] = mapped_column(String(100))
    fecha: Mapped[date] = mapped_column(Date)
    hora_inicio: Mapped[time] = mapped_column(Time)
    hora_fin: Mapped[time] = mapped_column(Time)

    aula: Mapped[Room] = relationship(back_populates="reservas")
