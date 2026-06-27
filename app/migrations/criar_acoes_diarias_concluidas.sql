from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


class AcaoDiariaConcluida(Base):
    """
    Registra quais "ações do dia" (checklist do Dashboard) já foram marcadas
    como concluídas, por usuário e por dia. As ações em si são geradas
    dinamicamente no endpoint — essa tabela só guarda quais chaves foram
    marcadas em qual data, pra o checklist persistir entre recarregamentos.
    """
    __tablename__ = "acoes_diarias_concluidas"

    id           = Column(Integer, primary_key=True, index=True)
    usuario_id   = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    data         = Column(Date, nullable=False, index=True)
    chave_acao   = Column(String(100), nullable=False)
    concluida_em = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("usuario_id", "data", "chave_acao", name="uq_acao_usuario_data_chave"),
    )