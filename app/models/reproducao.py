from sqlalchemy import Column, Integer, String, Date, DateTime, Enum, ForeignKey, Text, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Reproducao(Base):
    """Controle reprodutivo: cio, inseminação, diagnóstico de gestação."""
    __tablename__ = "reproducoes"

    id                      = Column(Integer, primary_key=True, index=True)
    animal_id               = Column(Integer, ForeignKey("animais.id"), nullable=False)

    # Detecção de cio
    data_cio                = Column(Date)

    # Inseminação / Monta
    tipo_cobertura          = Column(Enum("inseminacao_artificial", "monta_natural", "transferencia_embriao"))
    data_cobertura          = Column(Date)
    touro_reprodutor        = Column(String(100))   # nome ou registro do touro/sêmen
    partida_semen           = Column(String(60))    # partida/lote do sêmen (IA)

    # Diagnóstico de gestação
    data_diagnostico        = Column(Date)
    resultado_diagnostico   = Column(Enum("positivo", "negativo", "inconclusivo"))
    metodo_diagnostico      = Column(String(80))    # ex: ultrassonografia, palpação retal

    # Previsão de parto
    data_prevista_parto     = Column(Date)          # calculado: data_cobertura + 283 dias (média bovinos)
    data_inicio_periodo_seco = Column(Date)         # calculado: data_prevista_parto - 60 dias

    observacao              = Column(Text)
    criado_em               = Column(DateTime, server_default=func.now())
    atualizado_em           = Column(DateTime, server_default=func.now(), onupdate=func.now())

    animal                  = relationship("Animal", back_populates="reproducoes")


class Ocorrencia(Base):
    """Registro de doenças, exames e ocorrências sanitárias do animal."""
    __tablename__ = "ocorrencias"

    id                  = Column(Integer, primary_key=True, index=True)
    animal_id           = Column(Integer, ForeignKey("animais.id"), nullable=False)

    tipo                = Column(Enum("doenca", "exame", "acidente", "outro"), nullable=False, default="outro")
    descricao           = Column(String(200), nullable=False)   # ex: "Mastite", "CCS", "Tristeza Parasitária"
    data_ocorrencia     = Column(Date, nullable=False)
    data_resolucao      = Column(Date)                          # quando foi resolvido (se aplicável)

    # Para exames laboratoriais
    resultado_exame     = Column(String(255))                   # ex: "CCS: 250.000 cel/ml"

    # Impacto na produção
    afeta_producao      = Column(Boolean, default=False)        # se deve bloquear contagem do leite
    dias_afastamento    = Column(Integer, default=0)

    responsavel         = Column(String(100))                   # veterinário responsável
    observacao          = Column(Text)

    criado_em           = Column(DateTime, server_default=func.now())
    atualizado_em       = Column(DateTime, server_default=func.now(), onupdate=func.now())

    animal              = relationship("Animal", back_populates="ocorrencias")