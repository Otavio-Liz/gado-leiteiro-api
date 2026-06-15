from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Vacina(Base):
    __tablename__ = "vacinas"

    id                  = Column(Integer, primary_key=True, index=True)
    animal_id           = Column(Integer, ForeignKey("animais.id"), nullable=False, index=True)

    nome_vacina         = Column(String(120), nullable=False)
    doenca_alvo         = Column(String(120))
    data_aplicacao      = Column(Date, nullable=False, index=True)
    proxima_dose        = Column(Date, index=True)
    lote                = Column(String(60))
    validade_vacina     = Column(Date)
    dose_aplicada       = Column(String(50))
    via_aplicacao       = Column(String(50))
    responsavel         = Column(String(100))
    observacao          = Column(Text)

    criado_em           = Column(DateTime, server_default=func.now())
    atualizado_em       = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relacionamento sem cascade — histórico sanitário e legal preservado
    animal              = relationship("Animal", back_populates="vacinas")