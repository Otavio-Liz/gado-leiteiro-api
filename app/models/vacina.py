from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Vacina(Base):
    __tablename__ = "vacinas"

    id                  = Column(Integer, primary_key=True, index=True)
    animal_id           = Column(Integer, ForeignKey("animais.id"), nullable=False)

    nome_vacina         = Column(String(120), nullable=False)
    doenca_alvo         = Column(String(120))   # ex: Febre Aftosa, Brucelose, Raiva
    data_aplicacao      = Column(Date, nullable=False)
    proxima_dose        = Column(Date)
    lote                = Column(String(60))    # lote da vacina
    validade_vacina     = Column(Date)          # validade do frasco
    dose_aplicada       = Column(String(50))    # ex: "2ml", "1 dose"
    via_aplicacao       = Column(String(50))    # ex: subcutânea, intramuscular
    responsavel         = Column(String(100))   # veterinário ou aplicador
    observacao          = Column(Text)

    criado_em           = Column(DateTime, server_default=func.now())
    atualizado_em       = Column(DateTime, server_default=func.now(), onupdate=func.now())

    animal              = relationship("Animal", back_populates="vacinas")