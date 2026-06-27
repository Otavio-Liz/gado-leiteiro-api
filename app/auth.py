from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import pegar_banco
import os

load_dotenv()

CHAVE_SECRETA = os.getenv("SECRET_KEY")
if not CHAVE_SECRETA:
    raise RuntimeError("SECRET_KEY não definida no ambiente. A aplicação não pode iniciar.")

ALGORITMO = "HS256"
EXPIRACAO_MINUTOS = 30
EXPIRACAO_REFRESH_DIAS = 7

oauth2_esquema = OAuth2PasswordBearer(tokenUrl="/usuarios/login")

# ── Controle de tentativas de login (persistido no banco) ─────────────────────
#
# Antes vivia num dict em memória do processo Python — funcionava bem com
# 1 único processo, mas não sobrevivia a um reinício e, em produção com
# múltiplos workers, cada worker tinha sua própria contagem (um atacante
# distribuindo requisições entre workers contornava o limite de tentativas).
# Persistido no banco, o bloqueio é o mesmo independente de quantos
# processos estejam rodando.

MAX_TENTATIVAS = 5
TEMPO_BLOQUEIO_MINUTOS = 15


def registrar_tentativa_falha(email: str, banco: Session):
    from app.models.tentativa_login import TentativaLogin
    agora = datetime.utcnow()

    entrada = banco.query(TentativaLogin).filter(TentativaLogin.email == email).first()
    if not entrada:
        entrada = TentativaLogin(email=email, tentativas=0, bloqueado_until=None)
        banco.add(entrada)

    if entrada.bloqueado_until and agora > entrada.bloqueado_until:
        entrada.tentativas = 0
        entrada.bloqueado_until = None

    entrada.tentativas += 1
    if entrada.tentativas >= MAX_TENTATIVAS:
        entrada.bloqueado_until = agora + timedelta(minutes=TEMPO_BLOQUEIO_MINUTOS)

    banco.commit()


def verificar_bloqueio(email: str, banco: Session):
    from app.models.tentativa_login import TentativaLogin
    entrada = banco.query(TentativaLogin).filter(TentativaLogin.email == email).first()
    if not entrada or not entrada.bloqueado_until:
        return

    agora = datetime.utcnow()
    if agora < entrada.bloqueado_until:
        minutos_restantes = int((entrada.bloqueado_until - agora).total_seconds() / 60) + 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Conta bloqueada por excesso de tentativas. Tente novamente em {minutos_restantes} minuto(s)"
        )


def resetar_tentativas(email: str, banco: Session):
    from app.models.tentativa_login import TentativaLogin
    banco.query(TentativaLogin).filter(TentativaLogin.email == email).delete()
    banco.commit()


def tentativas_restantes(email: str, banco: Session) -> int:
    from app.models.tentativa_login import TentativaLogin
    entrada = banco.query(TentativaLogin).filter(TentativaLogin.email == email).first()
    if not entrada:
        return MAX_TENTATIVAS
    return max(0, MAX_TENTATIVAS - entrada.tentativas)


# ── Tokens ────────────────────────────────────────────────────────────────────

def criar_token(dados: dict):
    dados_copia = dados.copy()
    expiracao = datetime.now(timezone.utc) + timedelta(minutes=EXPIRACAO_MINUTOS)
    dados_copia.update({"exp": expiracao, "tipo": "access"})
    return jwt.encode(dados_copia, CHAVE_SECRETA, algorithm=ALGORITMO)


def criar_refresh_token(dados: dict):
    dados_copia = dados.copy()
    expiracao = datetime.now(timezone.utc) + timedelta(days=EXPIRACAO_REFRESH_DIAS)
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
    email = verificar_token(token, tipo="access")
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"}
        )
    usuario = banco.query(Usuario).filter(Usuario.email == email).first()
    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if not usuario.ativo:
        raise HTTPException(status_code=403, detail="Usuário desativado ou email não verificado")
    return usuario