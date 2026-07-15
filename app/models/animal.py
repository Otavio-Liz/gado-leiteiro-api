from sqlalchemy import Column, Integer, String, Date, Enum, DateTime, ForeignKey, Text, Index, Numeric
from sqlalchemy.sql import func
from app.database import Base
from sqlalchemy.orm import relationship


class Animal(Base):
    __tablename__ = "animais"

    id                  = Column(Integer, primary_key=True, index=True)
    usuario_id          = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)

    # Identificação
    nome                = Column(String(100), nullable=False)
    brinco              = Column(String(50), nullable=False, index=True)
    raca                = Column(String(80))
    nascimento          = Column(Date)
    sexo                = Column(Enum("F", "M"), nullable=False, default="F")

    # Genealogia
    nome_pai            = Column(String(100))
    nome_mae            = Column(String(100))
    registro_genealogico = Column(String(100))

    # Status
    status              = Column(Enum("ativo", "inativo", "vendido", "morto", "seco"), nullable=False, default="ativo", index=True)
    status_reprodutivo  = Column(Enum("vazia", "prenha", "em_cio", "em_lactacao", "seca", "nao_aplicavel"), nullable=False, default="nao_aplicavel", index=True)

    # Produção
    producao_diaria_litros = Column(Integer, default=0)

    # Reprodução
    data_ultima_inseminacao = Column(Date)
    data_prevista_parto     = Column(Date, index=True)
    dias_em_lactacao        = Column(Integer, default=0)
    quantidade_partos       = Column(Integer, nullable=False, default=0)
    data_ultimo_parto       = Column(Date)

    # Informações adicionais
    # DECIMAL(6,2), não Integer — peso é medida contínua (ex: 375.50 kg).
    # Corrigido para bater com o schema Pydantic (Decimal) e com a
    # migration que já alterou a coluna real no banco. Antes disso, o
    # SQLAlchemy aplicava o processamento de resultado do tipo Integer na
    # LEITURA dessa coluna, truncando qualquer valor decimal salvo
    # (ex: gravava 375.50, devolvia 375) mesmo com o banco guardando o
    # valor certo — o dado não se perdia, só a leitura vinha errada.
    peso_kg             = Column(Numeric(6, 2))
    observacao          = Column(Text)
    foto_url            = Column(String(500))

    criado_em           = Column(DateTime, server_default=func.now())
    atualizado_em       = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Índice composto — brinco único por produtor. Os outros dois cobrem o
    # padrão de filtro mais comum do sistema: praticamente toda consulta
    # filtra por usuario_id + status (animais "ativo" do usuário), e boa
    # parte também por status_reprodutivo (em lactação, prenha, etc.) — um
    # índice composto atende essa combinação melhor que índices isolados.
    __table_args__ = (
        Index("ix_animais_usuario_brinco", "usuario_id", "brinco", unique=True),
        Index("ix_animais_usuario_status", "usuario_id", "status"),
        Index("ix_animais_usuario_status_reprodutivo", "usuario_id", "status_reprodutivo"),
    )

    # Relacionamentos sem cascade — histórico preservado
    usuario             = relationship("Usuario", back_populates="animais")
    producoes           = relationship("Producao", back_populates="animal")
    partos              = relationship("Parto", back_populates="animal")
    medicamentos        = relationship("AplicacaoMedicamento", back_populates="animal")
    vacinas             = relationship("Vacina", back_populates="animal")
    reproducoes         = relationship("Reproducao", back_populates="animal")
    ocorrencias         = relationship("Ocorrencia", back_populates="animal")