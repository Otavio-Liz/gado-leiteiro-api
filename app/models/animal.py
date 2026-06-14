from sqlalchemy import Column, Integer, String, Date, Enum, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from app.database import Base
from sqlalchemy.orm import relationship


class Animal(Base):
    __tablename__ = "animais"

    id                  = Column(Integer, primary_key=True, index=True)
    usuario_id          = Column(Integer, ForeignKey("usuarios.id"), nullable=False)

    # Identificação
    nome                = Column(String(100), nullable=False)
    brinco              = Column(String(50), nullable=False)
    raca                = Column(String(80))
    nascimento          = Column(Date)
    sexo                = Column(Enum("F", "M"), nullable=False, default="F")

    # Genealogia
    nome_pai            = Column(String(100))
    nome_mae            = Column(String(100))
    registro_genealogico = Column(String(100))  # número de registro em associação

    # Status
    status              = Column(Enum("ativo", "inativo", "vendido", "morto", "seco"), nullable=False, default="ativo")
    status_reprodutivo  = Column(Enum("vazia", "prenha", "em_cio", "em_lactacao", "seca", "nao_aplicavel"), nullable=False, default="nao_aplicavel")

    # Produção
    producao_diaria_litros = Column(Integer, default=0)  # litros por dia informados pelo produtor

    # Reprodução
    data_ultima_inseminacao = Column(Date)
    data_prevista_parto     = Column(Date)
    dias_em_lactacao        = Column(Integer, default=0)  # DEL - calculado a partir do último parto

    # Informações adicionais
    peso_kg             = Column(Integer)  # peso em kg
    observacao          = Column(Text)
    foto_url            = Column(String(500))  # URL da foto no Cloudinary

    criado_em           = Column(DateTime, server_default=func.now())
    atualizado_em       = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relacionamentos
    usuario             = relationship("Usuario", back_populates="animais")
    producoes           = relationship("Producao", back_populates="animal")
    partos              = relationship("Parto", back_populates="animal")
    medicamentos        = relationship("AplicacaoMedicamento", back_populates="animal")
    vacinas             = relationship("Vacina", back_populates="animal")
    reproducoes         = relationship("Reproducao", back_populates="animal")
    ocorrencias         = relationship("Ocorrencia", back_populates="animal")