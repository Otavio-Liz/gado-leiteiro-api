from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base

class Medicamento(Base):
    __tablename__ = "medicamentos"

    id          = Column(Integer, primary_key=True, index=True)
    animal_id   = Column(Integer, ForeignKey("animais.id"), nullable=False)
    nome        = Column(String(120), nullable=False)
    motivo      = Column(String(200))
    data_inicio = Column(Date, nullable=False)
    data_fim    = Column(Date)
    observacao  = Column(String(255))
    criado_em   = Column(DateTime, server_default=func.now())

    animal = relationship("Animal", back_populates="medicamentos")