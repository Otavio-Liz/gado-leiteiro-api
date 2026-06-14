from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Numeric, Enum, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Producao(Base):
    """
    Registro de produção de leite por animal por dia.
    O produtor informa a quantidade total diária — o sistema calcula semana e mês.
    """
    __tablename__ = "producoes"

    id                  = Column(Integer, primary_key=True, index=True)
    animal_id           = Column(Integer, ForeignKey("animais.id"), nullable=False)

    data                = Column(Date, nullable=False)
    quantidade_litros   = Column(Numeric(6, 2), nullable=False)

    # Controle de descarte (carência pós-parto ou medicamento)
    status              = Column(Enum("aproveitado", "descartado"), nullable=False, default="aproveitado")
    motivo_descarte     = Column(String(200))  # ex: "Carência medicamento X" ou "Colostro pós-parto"

    observacao          = Column(Text)
    criado_em           = Column(DateTime, server_default=func.now())
    atualizado_em       = Column(DateTime, server_default=func.now(), onupdate=func.now())

    animal              = relationship("Animal", back_populates="producoes")


class PrecoLeite(Base):
    """Histórico de preços do leite definidos pelo usuário."""
    __tablename__ = "precos_leite"

    id              = Column(Integer, primary_key=True, index=True)
    usuario_id      = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    preco_litro     = Column(Numeric(8, 4), nullable=False)  # ex: 2.5000
    vigente_a_partir = Column(Date, nullable=False)          # a partir de quando vale esse preço
    observacao      = Column(String(255))
    criado_em       = Column(DateTime, server_default=func.now())

    usuario         = relationship("Usuario", back_populates="precos_leite")