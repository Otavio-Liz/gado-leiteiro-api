from sqlalchemy import Column, Integer, String, Date, DateTime, Numeric, ForeignKey, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base

class Producao(Base):
    __tablename__ = "producoes"

    id                = Column(Integer, primary_key=True, index=True)
    animal_id         = Column(Integer, ForeignKey("animais.id"), nullable=False)
    data              = Column(Date, nullable=False)
    quantidade_litros = Column(Numeric(6, 2), nullable=False)
    turno             = Column(Enum("manha", "tarde", "noite"), nullable=False, default="manha")
    observacao        = Column(String(255))
    criado_em         = Column(DateTime, server_default=func.now())

    animal = relationship("Animal", back_populates="producoes")