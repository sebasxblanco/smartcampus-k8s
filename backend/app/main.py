from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app import schemas, services
from app.config import APP_ENV
from app.database import Base, engine, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(title="SmartCampus")


# Cada error de negocio se traduce a su código HTTP en un solo sitio.
@app.exception_handler(services.NotFoundError)
def _not_found(request: Request, exc: services.NotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(services.InvalidDataError)
def _invalid(request: Request, exc: services.InvalidDataError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(services.ConflictError)
def _conflict(request: Request, exc: services.ConflictError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/info")
def info():
    """Configuración no sensible: en Kubernetes APP_ENV llega desde el ConfigMap."""
    return {"env": APP_ENV}


# --- Aulas --------------------------------------------------------------------


@app.get("/rooms", response_model=list[schemas.Room])
def listar_aulas(db: Session = Depends(get_db)):
    return services.listar_aulas(db)


@app.get("/rooms/{aula_id}", response_model=schemas.Room)
def obtener_aula(aula_id: int, db: Session = Depends(get_db)):
    return services.obtener_aula(db, aula_id)


@app.post("/rooms", response_model=schemas.Room, status_code=status.HTTP_201_CREATED)
def crear_aula(datos: schemas.RoomCreate, db: Session = Depends(get_db)):
    return services.crear_aula(db, datos)


@app.delete("/rooms/{aula_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_aula(aula_id: int, db: Session = Depends(get_db)):
    services.eliminar_aula(db, aula_id)


# --- Reservas -----------------------------------------------------------------


@app.get("/bookings", response_model=list[schemas.Booking])
def listar_reservas(db: Session = Depends(get_db)):
    return services.listar_reservas(db)


@app.post(
    "/bookings", response_model=schemas.Booking, status_code=status.HTTP_201_CREATED
)
def crear_reserva(datos: schemas.BookingCreate, db: Session = Depends(get_db)):
    return services.crear_reserva(db, datos)


@app.delete("/bookings/{reserva_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_reserva(reserva_id: int, db: Session = Depends(get_db)):
    services.eliminar_reserva(db, reserva_id)
