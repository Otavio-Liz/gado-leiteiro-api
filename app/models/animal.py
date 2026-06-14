from sqlalchemy import Column, Integer, String, Date, Enum, DateTime
from sqlalchemy.sql import func
from app.database import Base
from sqlalchemy.orm import relationship

class Animal(Base):
    __tablename__ = "animais"

    id          = Column(Integer, primary_key=True, index=True)
    usuario_id  = Column(Integer, nullable=False)
    nome        = Column(String(100), nullable=False)
    brinco      = Column(String(50), nullable=False)
    raca        = Column(String(80))
    nascimento  = Column(Date)
    sexo        = Column(Enum("F", "M"), nullable=False, default="F")
    status      = Column(Enum("ativo", "inativo", "vendido", "morto"), nullable=False, default="ativo")
    criado_em   = Column(DateTime, server_default=func.now())
    producoes = relationship("Producao", back_populates="animal")
    partos = relationship("Parto", back_populates="animal")
    medicamentos = relationship("Medicamento", back_populates="animal")
    vacinas = relationship("Vacina", back_populates="animal")