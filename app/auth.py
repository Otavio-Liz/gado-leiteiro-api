from datetime import datetime, timedelta
from jose import JWTError, jwt
from dotenv import load_dotenv
import os
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

load_dotenv()

CHAVE_SECRETA = os.getenv("SECRET_KEY", "chave-super-secreta")
ALGORITMO = "HS256"
EXPIRACAO_MINUTOS = 30

def criar_token(dados: dict):
    dados_copia = dados.copy()
    expiracao = datetime.utcnow() + timedelta(minutes=EXPIRACAO_MINUTOS)
    dados_copia.update({"exp": expiracao})
    return jwt.encode(dados_copia, CHAVE_SECRETA, algorithm=ALGORITMO)

def verificar_token(token: str):
    try:
        payload = jwt.decode(token, CHAVE_SECRETA, algorithms=[ALGORITMO])
        return payload.get("sub")
    except JWTError:
        return None
    
oauth2_esquema = OAuth2PasswordBearer(tokenUrl="/usuarios/login")

def pegar_usuario_atual(token: str = Depends(oauth2_esquema)):
    username = verificar_token(token)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return username