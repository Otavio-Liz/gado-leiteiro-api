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
if len(CHAVE_SECRETA) < 32:
    # Chave curta é trivial de força-bruta contra um HMAC-SHA256 — exigir
    # um mínimo aqui pega esse erro de configuração antes do deploy, em vez
    # de descobrir depois que tokens podiam ser forjados.
    raise RuntimeError("SECRET_KEY muito curta (mínimo 32 caracteres). Gere uma chave forte antes de iniciar.")

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
#
# O payload inclui tanto "sub" (e-mail) quanto "usuario_id" — usuario_id é
# o identificador primário usado nos lookups (mais rápido, índice de
# inteiro vs. string, e não quebra se o e-mail do usuário mudar depois do
# token emitido). "sub" continua presente por compatibilidade/legibilidade
# do token e porque OAuth2PasswordBearer/ferramentas de debug esperam "sub".

def criar_token(usuario):
    """Recebe o objeto Usuario (não mais um dict solto) — assim usuario_id
    e email vêm sempre do mesmo lugar, sem risco de passar um dict
    incompleto por engano em algum chamador novo."""
    dados = {"sub": usuario.email, "usuario_id": usuario.id}
    expiracao = datetime.now(timezone.utc) + timedelta(minutes=EXPIRACAO_MINUTOS)
    dados.update({"exp": expiracao, "tipo": "access"})
    return jwt.encode(dados, CHAVE_SECRETA, algorithm=ALGORITMO)


def criar_refresh_token(usuario):
    """Retorna (token, jti) — o chamador é responsável por persistir o jti
    em RefreshTokenValido pra esse token poder ser revogado depois."""
    import uuid
    dados = {"sub": usuario.email, "usuario_id": usuario.id}
    jti = str(uuid.uuid4())
    expiracao = datetime.now(timezone.utc) + timedelta(days=EXPIRACAO_REFRESH_DIAS)
    dados.update({"exp": expiracao, "tipo": "refresh", "jti": jti})
    token = jwt.encode(dados, CHAVE_SECRETA, algorithm=ALGORITMO)
    return token, jti


def verificar_token(token: str, tipo: str = "access"):
    """Retorna o payload inteiro (dict) em vez de só o e-mail — chamadores
    que só precisam do e-mail continuam funcionando (ex: payload["sub"]),
    e quem precisa do usuario_id ou jti agora tem acesso direto, sem
    decodificar o token de novo em outra função."""
    try:
        cabecalho = jwt.get_unverified_header(token)
        if cabecalho.get("alg") != ALGORITMO:
            return None

        payload = jwt.decode(token, CHAVE_SECRETA, algorithms=[ALGORITMO])
        if payload.get("tipo") != tipo:
            return None
        return payload
    except JWTError:
        return None


def jti_esta_valido(jti: str, banco: Session) -> bool:
    """Só checagem (sem revogar) — usado em pontos que precisam confirmar
    validade sem consumir o token (ex: nenhum caso de uso atual fora da
    rotação, mas mantido por clareza/depuração)."""
    from app.models.refresh_token_valido import RefreshTokenValido
    if not jti:
        return False
    entrada = banco.query(RefreshTokenValido).filter(RefreshTokenValido.jti == jti).first()
    if not entrada or entrada.revogado:
        return False
    if entrada.expira_em < datetime.utcnow():
        return False
    return True


def revogar_jti_atomico(jti: str, banco: Session) -> bool:
    """Revoga o jti em UMA única operação UPDATE condicional, e retorna se
    a revogação de fato aconteceu agora (True) ou se ele já estava
    revogado/inexistente antes dessa chamada (False).

    Isso fecha a race condition de rotação: antes, "checar se está válido"
    (SELECT) e "revogar" (UPDATE) eram dois passos separados — duas
    requisições simultâneas com o mesmo refresh token podiam ambas passar
    pelo SELECT antes de qualquer uma revogar, e as duas geravam um par de
    tokens novos a partir do mesmo token antigo.

    Com um único UPDATE ... WHERE jti = :jti AND revogado = False, o MySQL
    garante atomicidade: só uma das requisições concorrentes consegue
    rowcount > 0 (a outra recebe 0, porque a primeira já tinha marcado
    revogado=True um instante antes). Quem recebe 0 trata como token
    inválido — não reemite tokens novos.
    """
    from app.models.refresh_token_valido import RefreshTokenValido
    if not jti:
        return False

    # Verifica expiração separadamente: revogar um token expirado não deve
    # "reativar" nada nem contar como sucesso — só queremos True quando o
    # jti existia, estava ativo (não revogado) E ainda dentro da validade.
    entrada = banco.query(RefreshTokenValido).filter(RefreshTokenValido.jti == jti).first()
    if not entrada or entrada.expira_em < datetime.utcnow():
        return False

    resultado = banco.query(RefreshTokenValido).filter(
        RefreshTokenValido.jti == jti,
        RefreshTokenValido.revogado == False
    ).update({"revogado": True})
    banco.commit()
    return resultado > 0


def revogar_jti(jti: str, banco: Session):
    """Mantido para os fluxos onde a operação é só "revogar" sem precisar
    saber atomicamente se foi essa chamada que revogou (ex: logout — não
    importa quem revogou primeiro, o resultado final desejado é o mesmo:
    o token não funciona mais)."""
    from app.models.refresh_token_valido import RefreshTokenValido
    entrada = banco.query(RefreshTokenValido).filter(RefreshTokenValido.jti == jti).first()
    if entrada:
        entrada.revogado = True
        banco.commit()


def pegar_usuario_atual(
    token: str = Depends(oauth2_esquema),
    banco: Session = Depends(pegar_banco)
):
    from app.models.usuario import Usuario
    payload = verificar_token(token, tipo="access")
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"}
        )

    usuario_id = payload.get("usuario_id")
    if usuario_id is not None:
        usuario = banco.query(Usuario).filter(Usuario.id == usuario_id).first()
    else:
        # Fallback pra tokens emitidos antes dessa mudança (ainda não
        # expirados, válidos por até 30 minutos a mais após o deploy) —
        # sem isso, todo usuário logado no momento do deploy seria
        # deslogado à força até o access token expirar sozinho.
        usuario = banco.query(Usuario).filter(Usuario.email == payload.get("sub")).first()

    if usuario is None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if not usuario.ativo:
        raise HTTPException(status_code=403, detail="Usuário desativado ou email não verificado")
    return usuario