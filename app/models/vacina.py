from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base

class Vacina(Base):
    __tablename__ = "vacinas"

    id             = Column(Integer, primary_key=True, index=True)
    animal_id      = Column(Integer, ForeignKey("animais.id"), nullable=False)
    nome_vacina    = Column(String(120), nullable=False)
    data_aplicacao = Column(Date, nullable=False)
    proxima_dose   = Column(Date)
    observacao     = Column(String(255))
    criado_em      = Column(DateTime, server_default=func.now())

    animal = relationship("Animal", back_populates="vacinas")