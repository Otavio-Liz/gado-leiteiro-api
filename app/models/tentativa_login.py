from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.sql import func
from app.database import Base


class TentativaLogin(Base):
    """
    Controle de tentativas de login falhas, persistido no banco (substitui
    o dict em memória que existia antes — esse não sobrevivia a um reinício
    do servidor e não era compartilhado entre múltiplos processos/workers).
    Chave é o e-mail digitado, não o ID do usuário — assim o comportamento
    de bloqueio é idêntico tanto para e-mails cadastrados quanto não
    cadastrados, sem revelar qual é qual.
    """
    __tablename__ = "tentativas_login"

    email           = Column(String(255), primary_key=True)
    tentativas      = Column(Integer, nullable=False, default=0)
    bloqueado_until = Column(DateTime, nullable=True)
    atualizado_em   = Column(DateTime, server_default=func.now(), onupdate=func.now())