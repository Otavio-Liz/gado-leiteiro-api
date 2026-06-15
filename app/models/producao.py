from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Numeric, Enum, Text, Index, UniqueConstraint
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
    animal_id           = Column(Integer, ForeignKey("animais.id"), nullable=False, index=True)

    data                = Column(Date, nullable=False, index=True)
    quantidade_litros   = Column(Numeric(6, 2), nullable=False)

    status              = Column(Enum("aproveitado", "descartado"), nullable=False, default="aproveitado")
    motivo_descarte     = Column(String(200))

    observacao          = Column(Text)
    criado_em           = Column(DateTime, server_default=func.now())
    atualizado_em       = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Índice composto — um registro por animal por dia + unicidade garantida no banco
    __table_args__ = (
        UniqueConstraint("animal_id", "data", name="uq_producao_animal_data"),
    )

    # Relacionamento sem cascade — histórico financeiro preservado
    animal              = relationship("Animal", back_populates="producoes")


class PrecoLeite(Base):
    """Histórico de preços do leite definidos pelo usuário."""
    __tablename__ = "precos_leite"

    id               = Column(Integer, primary_key=True, index=True)
    usuario_id       = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    preco_litro      = Column(Numeric(8, 4), nullable=False)
    vigente_a_partir = Column(Date, nullable=False, index=True)
    observacao       = Column(String(255))
    criado_em        = Column(DateTime, server_default=func.now())

    # Relacionamento sem cascade — histórico financeiro preservado
    usuario          = relationship("Usuario", back_populates="precos_leite")