from datetime import datetime, timedelta
from jose import JWTError, jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import pegar_banco
import os

load_dotenv()

CHAVE_SECRETA = os.getenv("SECRET_KEY", "chave-super-secreta")
ALGORITMO = "HS256"
EXPIRACAO_MINUTOS = 30
EXPIRACAO_REFRESH_DIAS = 7

oauth2_esquema = OAuth2PasswordBearer(tokenUrl="/usuarios/login")

# ── Controle de tentativas de login em memória ────────────────────────────────
# { "username": {"tentativas": int, "bloqueado_ate": datetime} }
_tentativas_login: dict = {}

MAX_TENTATIVAS = 5
TEMPO_BLOQUEIO_MINUTOS = 15


def registrar_tentativa_falha(username: str):
    agora = datetime.utcnow()
    if username not in _tentativas_login:
        _tentativas_login[username] = {"tentativas": 0, "bloqueado_ate": None}

    entrada = _tentativas_login[username]

    # Se o bloqueio já expirou, resetar
    if entrada["bloqueado_ate"] and agora > entrada["bloqueado_ate"]:
        entrada["tentativas"] = 0
        entrada["bloqueado_ate"] = None

    entrada["tentativas"] += 1

    if entrada["tentativas"] >= MAX_TENTATIVAS:
        entrada["bloqueado_ate"] = agora + timedelta(minutes=TEMPO_BLOQUEIO_MINUTOS)


def verificar_bloqueio(username: str):
    if username not in _tentativas_login:
        return

    entrada = _tentativas_login[username]
    agora = datetime.utcnow()

    if entrada["bloqueado_ate"] and agora < entrada["bloqueado_ate"]:
        minutos_restantes = int((entrada["bloqueado_ate"] - agora).total_seconds() / 60) + 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Conta bloqueada por excesso de tentativas. Tente novamente em {minutos_restantes} minuto(s)"
        )


def resetar_tentativas(username: str):
    if username in _tentativas_login:
        del _tentativas_login[username]


def tentativas_restantes(username: str) -> int:
    if username not in _tentativas_login:
        return MAX_TENTATIVAS
    entrada = _tentativas_login[username]
    return max(0, MAX_TENTATIVAS - entrada["tentativas"])


# ── Tokens ────────────────────────────────────────────────────────────────────

def criar_token(dados: dict):
    """Cria o access token com expiração curta (30 minutos)."""
    dados_copia = dados.copy()
    expiracao = datetime.utcnow() + timedelta(minutes=EXPIRACAO_MINUTOS)
    dados_copia.update({"exp": expiracao, "tipo": "access"})
    return jwt.encode(dados_copia, CHAVE_SECRETA, algorithm=ALGORITMO)


def criar_refresh_token(dados: dict):
    """Cria o refresh token com expiração longa (7 dias)."""
    dados_copia = dados.copy()
    expiracao = datetime.utcnow() + timedelta(days=EXPIRACAO_REFRESH_DIAS)
    dados_copia.update({"exp": expiracao, "tipo": "refresh"})
    return jwt.encode(dados_copia, CHAVE_SECRETA, algorithm=ALGORITMO)


def verificar_token(token: str, tipo: str = "access"):
    try:
        payload = jwt.decode(token, CHAVE_SECRETA, algorithms=[ALGORITMO])
        if payload.get("tipo") != tipo:
            return None
        return payload.get("sub")
    except JWTError:
        return None


def pegar_usuario_atual(
    token: str = Depends(oauth2_esquema),
    banco: Session = Depends(pegar_banco)
):
    from app.models.usuario import Usuario
    username = verificar_token(token, tipo="access")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"}
        )
    usuario = banco.query(Usuario).filter(Usuario.username == username).first()
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if not usuario.ativo:
        raise HTTPException(status_code=403, detail="Usuário desativado")
    return usuario