import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from database import Base, SessionLocal, engine, get_db
from models import Laptop


class LaptopCreate(BaseModel):
    marca: str
    modelo: str
    ram_gb: int


class LaptopResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    marca: str
    modelo: str
    ram_gb: int
    disponible: bool


LAPTOPS_INICIALES = [
    {"marca": "Dell", "modelo": "Latitude 5440", "ram_gb": 16, "disponible": True},
    {"marca": "Lenovo", "modelo": "ThinkPad E14", "ram_gb": 8, "disponible": False},
    {"marca": "HP", "modelo": "ProBook 450", "ram_gb": 16, "disponible": True},
]


def crear_tablas_con_reintentos(intentos: int = 30, espera: int = 2):
    """MySQL puede tardar en aceptar conexiones; reintentamos."""
    for intento in range(1, intentos + 1):
        try:
            Base.metadata.create_all(bind=engine)
            return
        except OperationalError:
            print(f"MySQL no está listo (intento {intento}/{intentos}), esperando...")
            time.sleep(espera)
    raise RuntimeError("No se pudo conectar a MySQL")


def cargar_datos_iniciales():
    db = SessionLocal()
    try:
        if db.query(Laptop).count() == 0:
            for datos in LAPTOPS_INICIALES:
                db.add(Laptop(**datos))
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    crear_tablas_con_reintentos()
    cargar_datos_iniciales()
    yield


app = FastAPI(title="Laboratorio de cómputo", lifespan=lifespan)


@app.get("/")
def raiz():
    return {"mensaje": "API del laboratorio de cómputo"}


@app.get("/laptops", response_model=list[LaptopResponse])
def listar_laptops(db: Session = Depends(get_db)):
    return db.query(Laptop).order_by(Laptop.id).all()


# Debe ir ANTES de /laptops/{laptop_id}
@app.get("/laptops/disponibles", response_model=list[LaptopResponse])
def listar_disponibles(db: Session = Depends(get_db)):
    return (
        db.query(Laptop)
        .filter(Laptop.disponible == True)  # noqa: E712
        .order_by(Laptop.id)
        .all()
    )


@app.get("/laptops/{laptop_id}", response_model=LaptopResponse)
def obtener_laptop(laptop_id: int, db: Session = Depends(get_db)):
    laptop = db.get(Laptop, laptop_id)
    if laptop is None:
        raise HTTPException(status_code=404, detail="Laptop no encontrada")
    return laptop


@app.post("/laptops", response_model=LaptopResponse, status_code=201)
def crear_laptop(datos: LaptopCreate, db: Session = Depends(get_db)):
    laptop = Laptop(
        marca=datos.marca,
        modelo=datos.modelo,
        ram_gb=datos.ram_gb,
        disponible=True,
    )
    db.add(laptop)
    db.commit()
    db.refresh(laptop)
    return laptop
