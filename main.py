import os
from datetime import date, datetime
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

load_dotenv()
engine = create_engine(os.getenv("DB_URL"), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


# ---------- Modelos (tablas) ----------
class Medico(Base):
    __tablename__ = "medicos"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(100), nullable=False)
    especialidad = Column(String(100), nullable=False)


class Paciente(Base):
    __tablename__ = "pacientes"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(100), nullable=False)
    fecha_nacimiento = Column(Date, nullable=False)
    telefono = Column(String(20))


class Cita(Base):
    __tablename__ = "citas"
    id = Column(Integer, primary_key=True)
    paciente_id = Column(Integer, ForeignKey("pacientes.id"), nullable=False)
    medico_id = Column(Integer, ForeignKey("medicos.id"), nullable=False)
    fecha = Column(DateTime, nullable=False)
    motivo = Column(String(255))


# ---------- Schemas (validación) ----------
class MedicoIn(BaseModel):
    nombre: str = Field(example="Dr. Juan Pérez")
    especialidad: str = Field(example="Cardiología")


class MedicoOut(MedicoIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class PacienteIn(BaseModel):
    nombre: str = Field(example="María López")
    fecha_nacimiento: date = Field(example="1990-05-20")
    telefono: Optional[str] = Field(default=None, example="7711234567")


class PacienteOut(PacienteIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class CitaIn(BaseModel):
    paciente_id: int = Field(example=1)
    medico_id: int = Field(example=1)
    fecha: datetime = Field(example="2026-12-01T10:30:00")
    motivo: Optional[str] = Field(default=None, example="Revisión general")


class CitaOut(CitaIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---------- App ----------
app = FastAPI(
    title="API Hospital",
    version="1.0",
    description="CRUD de médicos, pacientes y citas conectado a MySQL en AWS RDS",
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- Generador de CRUD ----------
def crear_crud(prefix, tag, Model, SchemaIn, SchemaOut, validar=None):
    router = APIRouter(prefix=prefix, tags=[tag])

    @router.post("", response_model=SchemaOut, status_code=201,
                 summary=f"Crear {tag.lower()}")
    def crear(data: SchemaIn, db: Session = Depends(get_db)):
        if validar:
            validar(data, db)
        obj = Model(**data.model_dump())
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    @router.get("", response_model=List[SchemaOut],
                summary=f"Listar {tag.lower()}")
    def listar(db: Session = Depends(get_db)):
        return db.query(Model).all()

    @router.get("/{id}", response_model=SchemaOut,
                summary=f"Obtener {tag.lower()} por id")
    def obtener(id: int, db: Session = Depends(get_db)):
        obj = db.get(Model, id)
        if not obj:
            raise HTTPException(404, "No encontrado")
        return obj

    @router.put("/{id}", response_model=SchemaOut,
                summary=f"Actualizar {tag.lower()}")
    def actualizar(id: int, data: SchemaIn, db: Session = Depends(get_db)):
        obj = db.get(Model, id)
        if not obj:
            raise HTTPException(404, "No encontrado")
        if validar:
            validar(data, db)
        for k, v in data.model_dump().items():
            setattr(obj, k, v)
        db.commit()
        db.refresh(obj)
        return obj

    @router.delete("/{id}", status_code=204, summary=f"Eliminar {tag.lower()}")
    def eliminar(id: int, db: Session = Depends(get_db)):
        obj = db.get(Model, id)
        if not obj:
            raise HTTPException(404, "No encontrado")
        try:
            db.delete(obj)
            db.commit()
        except Exception:
            db.rollback()
            raise HTTPException(409, "No se puede eliminar: tiene registros relacionados")

    return router


def validar_cita(data: CitaIn, db: Session):
    if not db.get(Paciente, data.paciente_id):
        raise HTTPException(404, "El paciente no existe")
    if not db.get(Medico, data.medico_id):
        raise HTTPException(404, "El médico no existe")


app.include_router(crear_crud("/medicos", "Médicos", Medico, MedicoIn, MedicoOut))
app.include_router(crear_crud("/pacientes", "Pacientes", Paciente, PacienteIn, PacienteOut))
app.include_router(crear_crud("/citas", "Citas", Cita, CitaIn, CitaOut, validar_cita))