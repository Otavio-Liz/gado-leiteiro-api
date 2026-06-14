from sqlalchemy import Column, Integer, String, Date, DateTime, Enum, ForeignKey, Text, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Parto(Base):
    __tablename__ = "partos"

    id                      = Column(Integer, primary_key=True, index=True)
    animal_id               = Column(Integer, ForeignKey("animais.id"), nullable=False)

    data_parto              = Column(Date, nullable=False)
    tipo_parto              = Column(Enum("normal", "cesariana", "distocico"), nullable=False, default="normal")

    # Cria
    status_cria             = Column(Enum("vivo", "morto", "natimorto"), nullable=False, default="vivo")
    sexo_cria               = Column(Enum("F", "M"))
    nome_cria               = Column(String(100))  # se a cria for registrada como animal
    peso_cria_kg            = Column(Integer)

    # Carência pós-parto (colostro)
    dias_carencia_colostro  = Column(Integer, default=7)  # padrão 7 dias sem contar leite
    carencia_encerra_em     = Column(Date)                # calculado automaticamente

    # Período seco anterior ao parto
    data_inicio_periodo_seco = Column(Date)               # quando a vaca parou de ser ordenhada

    observacao              = Column(Text)
    criado_em               = Column(DateTime, server_default=func.now())
    atualizado_em           = Column(DateTime, server_default=func.now(), onupdate=func.now())

    animal                  = relationship("Animal", back_populates="partos")