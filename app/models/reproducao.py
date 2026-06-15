from sqlalchemy import Column, Integer, String, Date, DateTime, Enum, ForeignKey, Text, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Reproducao(Base):
    """Controle reprodutivo: cio, inseminação, diagnóstico de gestação."""
    __tablename__ = "reproducoes"

    id                      = Column(Integer, primary_key=True, index=True)
    animal_id               = Column(Integer, ForeignKey("animais.id"), nullable=False, index=True)

    data_cio                = Column(Date)
    tipo_cobertura          = Column(Enum("inseminacao_artificial", "monta_natural", "transferencia_embriao"))
    data_cobertura          = Column(Date, index=True)
    touro_reprodutor        = Column(String(100))
    partida_semen           = Column(String(60))

    data_diagnostico        = Column(Date)
    resultado_diagnostico   = Column(Enum("positivo", "negativo", "inconclusivo"))
    metodo_diagnostico      = Column(String(80))

    data_prevista_parto     = Column(Date)
    data_inicio_periodo_seco = Column(Date)

    observacao              = Column(Text)
    criado_em               = Column(DateTime, server_default=func.now())
    atualizado_em           = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relacionamento sem cascade — histórico reprodutivo preservado
    animal                  = relationship("Animal", back_populates="reproducoes")


class Ocorrencia(Base):
    """Registro de doenças, exames e ocorrências sanitárias do animal."""
    __tablename__ = "ocorrencias"

    id                  = Column(Integer, primary_key=True, index=True)
    animal_id           = Column(Integer, ForeignKey("animais.id"), nullable=False, index=True)

    tipo                = Column(Enum("doenca", "exame", "acidente", "outro"), nullable=False, default="outro")
    descricao           = Column(String(200), nullable=False)
    data_ocorrencia     = Column(Date, nullable=False, index=True)
    data_resolucao      = Column(Date, index=True)

    resultado_exame     = Column(String(255))
    afeta_producao      = Column(Boolean, default=False)
    dias_afastamento    = Column(Integer, default=0)
    responsavel         = Column(String(100))
    observacao          = Column(Text)

    criado_em           = Column(DateTime, server_default=func.now())
    atualizado_em       = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relacionamento sem cascade — histórico clínico preservado
    animal              = relationship("Animal", back_populates="ocorrencias")