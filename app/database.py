from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()

servidor    = os.getenv("DB_HOST")
porta       = os.getenv("DB_PORT")
nome_banco  = os.getenv("DB_NAME")
usuario     = os.getenv("DB_USER")
senha       = os.getenv("DB_PASSWORD")

url_banco = f"mysql+pymysql://{usuario}:{senha}@{servidor}:{porta}/{nome_banco}"

motor = create_engine(url_banco)

SessaoLocal = sessionmaker(autocommit=False, autoflush=False, bind=motor)

Base = declarative_base()

def pegar_banco():
    sessao = SessaoLocal()
    try:
        yield sessao
    finally:
        sessao.close()