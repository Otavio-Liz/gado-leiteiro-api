from sqlalchemy import Column, Integer, String, Date, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base

class Parto(Base):
    __tablename__ = "partos"

    id          = Column(Integer, primary_key=True, index=True)
    animal_id   = Column(Integer, ForeignKey("animais.id"), nullable=False)
    data_parto  = Column(Date, nullable=False)
    status_cria = Column(Enum("vivo", "morto", "natimorto"), nullable=False, default="vivo")
    sexo_cria   = Column(Enum("F", "M"))
    observacao  = Column(String(255))
    criado_em   = Column(DateTime, server_default=func.now())

    animal = relationship("Animal", back_populates="partos")