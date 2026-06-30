# ESTE ARQUIVO VAI EM: app/models/usuario.py (com o campo nome_fazenda adicionado)
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id                          = Column(Integer, primary_key=True, index=True)
    nome                        = Column(String(150), nullable=False)
    nome_fazenda                = Column(String(150), nullable=True)
    email                       = Column(String(150), unique=True, nullable=False, index=True)
    senha_hash                  = Column(String(255), nullable=False)
    foto_url                    = Column(String(500))
    ativo                       = Column(Boolean, default=False)
    token_verificacao           = Column(String(255), nullable=True)
    codigo_verificacao          = Column(String(6), nullable=True)
    codigo_verificacao_expira   = Column(DateTime, nullable=True)
    token_reset                 = Column(String(255), nullable=True)
    token_reset_expira          = Column(DateTime, nullable=True)

    # Troca de e-mail com confirmação — o e-mail novo só é aplicado de fato
    # (sobrescrevendo a coluna `email`) depois que o código abaixo é
    # confirmado em POST /usuarios/confirmar-novo-email. Até lá, login e
    # identidade continuam pelo e-mail antigo.
    email_pendente               = Column(String(150), nullable=True)
    email_pendente_codigo        = Column(String(6), nullable=True)
    email_pendente_expira        = Column(DateTime, nullable=True)

    # Contador de tentativas erradas de código — compartilhado entre o
    # código de ativação de cadastro (codigo_verificacao) e o de
    # confirmação de novo e-mail (email_pendente_codigo), já que só um
    # dos dois fluxos fica pendente de cada vez por usuário.
    tentativas_codigo_verificacao = Column(Integer, nullable=False, default=0)

    criado_em                   = Column(DateTime, server_default=func.now())
    atualizado_em                = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relacionamentos
    animais         = relationship("Animal", back_populates="usuario")
    medicamentos    = relationship("Medicamento", back_populates="usuario")
    precos_leite    = relationship("PrecoLeite", back_populates="usuario")