from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Text, Numeric
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Medicamento(Base):
    """Cadastro de medicamentos disponíveis na propriedade (estoque)."""
    __tablename__ = "medicamentos"

    id                  = Column(Integer, primary_key=True, index=True)
    usuario_id          = Column(Integer, ForeignKey("usuarios.id"), nullable=False)

    nome                = Column(String(120), nullable=False)
    principio_ativo     = Column(String(120))
    fabricante          = Column(String(100))
    dias_carencia       = Column(Integer, default=0)  # dias que o leite fica descartado após aplicação
    estoque_atual       = Column(Numeric(8, 2), default=0)   # quantidade em estoque (doses/ml/g)
    estoque_minimo      = Column(Numeric(8, 2), default=0)   # alerta quando abaixo desse valor
    unidade             = Column(String(20), default="dose")  # dose, ml, g, comprimido
    observacao          = Column(Text)

    criado_em           = Column(DateTime, server_default=func.now())
    atualizado_em       = Column(DateTime, server_default=func.now(), onupdate=func.now())

    usuario             = relationship("Usuario", back_populates="medicamentos")
    aplicacoes          = relationship("AplicacaoMedicamento", back_populates="medicamento")


class AplicacaoMedicamento(Base):
    """Registro de cada aplicação de medicamento em um animal."""
    __tablename__ = "aplicacoes_medicamento"

    id                      = Column(Integer, primary_key=True, index=True)
    animal_id               = Column(Integer, ForeignKey("animais.id"), nullable=False)
    medicamento_id          = Column(Integer, ForeignKey("medicamentos.id"), nullable=False)

    data_aplicacao          = Column(Date, nullable=False)
    dose_aplicada           = Column(Numeric(8, 2), nullable=False)
    motivo                  = Column(String(200))
    dias_carencia           = Column(Integer, default=0)   # copiado do medicamento no momento da aplicação
    carencia_encerra_em     = Column(Date)                 # calculado automaticamente
    observacao              = Column(Text)

    criado_em               = Column(DateTime, server_default=func.now())

    animal                  = relationship("Animal", back_populates="medicamentos")
    medicamento             = relationship("Medicamento", back_populates="aplicacoes")