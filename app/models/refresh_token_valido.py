from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class RefreshTokenValido(Base):
    """
    Controla quais refresh tokens emitidos ainda são válidos. Cada refresh
    token carrega um "jti" (identificador único) no próprio JWT — essa
    tabela é a fonte de verdade de quais jtis ainda não foram revogados.

    Permite: (1) logout de verdade — revoga o jti no servidor, não só
    limpa o token do navegador; (2) rotação — a cada /refresh, o token
    antigo é revogado e um novo jti é emitido, então um token roubado e
    usado uma vez já não serve mais pro dono original nem pro ladrão.
    """
    __tablename__ = "refresh_tokens_validos"

    jti        = Column(String(36), primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    expira_em  = Column(DateTime, nullable=False)
    revogado   = Column(Boolean, nullable=False, default=False)
    criado_em  = Column(DateTime, server_default=func.now())