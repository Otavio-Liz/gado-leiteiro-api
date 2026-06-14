from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id          = Column(Integer, primary_key=True, index=True)
    username    = Column(String(50), unique=True, nullable=False, index=True)
    senha_hash  = Column(String(255), nullable=False)
    nome_completo = Column(String(150))
    email       = Column(String(150), unique=True)
    foto_url    = Column(String(500))
    ativo       = Column(Boolean, default=True)
    criado_em   = Column(DateTime, server_default=func.now())
    atualizado_em = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relacionamentos
    animais         = relationship("Animal", back_populates="usuario")
    medicamentos    = relationship("Medicamento", back_populates="usuario")
    precos_leite    = relationship("PrecoLeite", back_populates="usuario")