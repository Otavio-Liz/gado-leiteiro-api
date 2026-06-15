from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv
import os

load_dotenv()

servidor   = os.getenv("DB_HOST")
porta      = os.getenv("DB_PORT")
nome_banco = os.getenv("DB_NAME")
usuario    = os.getenv("DB_USER")
senha      = os.getenv("DB_PASSWORD")

if not all([servidor, porta, nome_banco, usuario, senha]):
    raise RuntimeError("Configurações do banco de dados incompletas. Verifique o arquivo .env")

url_banco = f"mysql+pymysql://{usuario}:{senha}@{servidor}:{porta}/{nome_banco}"

motor = create_engine(
    url_banco,
    pool_size=5,          # conexões mantidas abertas
    max_overflow=10,      # conexões extras permitidas em pico
    pool_timeout=30,      # segundos aguardando conexão disponível
    pool_recycle=1800,    # recicla conexões a cada 30 minutos
    pool_pre_ping=True    # testa conexão antes de usar — evita conexões mortas
)

SessaoLocal = sessionmaker(autocommit=False, autoflush=False, bind=motor)


class Base(DeclarativeBase):
    pass


def pegar_banco():
    sessao = SessaoLocal()
    try:
        yield sessao
    finally:
        sessao.close()