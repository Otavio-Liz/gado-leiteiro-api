from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.database import pegar_banco
from app.models.usuario import Usuario
from app.schemas.usuarios import (
    UsuarioCreate, UsuarioResponse, UsuarioAtualizar, LoginRequest,
    EsqueciSenhaRequest, RedefinirSenhaRequest,
    VerificarCodigoRequest, ReenviarConfirmacaoRequest
)
from app.security import verificar_senha, gerar_hash_senha
from app.auth import (
    criar_token, criar_refresh_token, verificar_token,
    verificar_bloqueio, registrar_tentativa_falha,
    resetar_tentativas, tentativas_restantes,
    pegar_usuario_atual, extrair_jti, jti_esta_valido, revogar_jti,
    EXPIRACAO_REFRESH_DIAS
)
from app.models.refresh_token_valido import RefreshTokenValido
from app.logger import logger_usuario
from app.limitador import limitador
import cloudinary.uploader
import resend
import os
import secrets
from PIL import Image
import io

resend.api_key = os.getenv("RESEND_API_KEY")
APP_URL = os.getenv("APP_URL", "http://localhost:8000")
FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev")

# Hash "morto" — nunca corresponde a senha real nenhuma. Usado só quando o
# e-mail não existe, pra que verificar_senha() SEMPRE rode (o bcrypt é a
# parte lenta da operação). Sem isso, login com e-mail inexistente retorna
# quase instantâneo enquanto e-mail existente demora ~100-300ms — uma
# diferença de tempo que dá pra usar pra descobrir quais e-mails têm conta.
HASH_DUMMY_TIMING = gerar_hash_senha(secrets.token_urlsafe(32))

roteador = APIRouter(prefix="/usuarios", tags=["Usuários"])

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

MINUTOS_VALIDADE_CODIGO = 4


def gerar_codigo_verificacao() -> str:
    return f"{secrets.randbelow(1000000):06d}"


def enviar_email_verificacao(email: str, nome: str, codigo: str):
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": email,
            "subject": "✅ Confirme seu e-mail — LeiteTech",
            "html": f"""
            <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px;background:#050d0a;color:#fff;border-radius:12px;">
                <h1 style="font-size:20px;color:#00ff88;margin-bottom:8px;">LeiteTech</h1>
                <h2 style="font-size:16px;font-weight:500;color:#fff;margin-bottom:16px;">Olá, {nome}! Confirme seu e-mail</h2>
                <p style="color:rgba(255,255,255,0.6);font-size:14px;line-height:1.6;margin-bottom:24px;">
                    Use o código abaixo para ativar sua conta. Ele expira em {MINUTOS_VALIDADE_CODIGO} minutos.
                </p>
                <div style="text-align:center;margin-bottom:24px;">
                    <span style="display:inline-block;padding:14px 28px;background:rgba(0,255,136,0.08);border:1px solid #00ff88;color:#00ff88;border-radius:8px;font-size:28px;font-weight:700;letter-spacing:0.2em;">
                        {codigo}
                    </span>
                </div>
                <p style="color:rgba(255,255,255,0.3);font-size:11px;margin-top:24px;">
                    Se não criou uma conta, ignore este e-mail.
                </p>
            </div>
            """
        })
    except Exception as e:
        logger_usuario.error(f"Erro ao enviar email de verificação para {email}: {e}")


def enviar_email_reset(email: str, nome: str, token: str):
    link = f"{FRONTEND_URL}/redefinir-senha?token={token}"
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": email,
            "subject": "🔑 Redefinição de senha — LeiteTech",
            "html": f"""
            <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px;background:#050d0a;color:#fff;border-radius:12px;">
                <h1 style="font-size:20px;color:#00ff88;margin-bottom:8px;">LeiteTech</h1>
                <h2 style="font-size:16px;font-weight:500;color:#fff;margin-bottom:16px;">Olá, {nome}! Redefina sua senha</h2>
                <p style="color:rgba(255,255,255,0.6);font-size:14px;line-height:1.6;margin-bottom:24px;">
                    Clique no botão abaixo para criar uma nova senha. O link expira em 1 hora.
                </p>
                <a href="{link}" style="display:inline-block;padding:12px 24px;background:transparent;border:1px solid #00ff88;color:#00ff88;border-radius:8px;text-decoration:none;font-size:14px;font-weight:600;">
                    REDEFINIR SENHA
                </a>
                <p style="color:rgba(255,255,255,0.3);font-size:11px;margin-top:24px;">
                    Se não solicitou a redefinição, ignore este e-mail. Sua senha não será alterada.
                </p>
            </div>
            """
        })
    except Exception as e:
        logger_usuario.error(f"Erro ao enviar email de reset para {email}: {e}")


@roteador.post("/cadastrar", response_model=dict)
@limitador.limit("5/minute")
def cadastrar(
    request: Request,
    dados: UsuarioCreate,
    banco: Session = Depends(pegar_banco)
):
    usuario_existente = banco.query(Usuario).filter(Usuario.email == dados.email).first()

    if usuario_existente and usuario_existente.ativo:
        raise HTTPException(status_code=400, detail="E-mail já está em uso.")

    codigo = gerar_codigo_verificacao()
    expira_em = datetime.utcnow() + timedelta(minutes=MINUTOS_VALIDADE_CODIGO)

    try:
        if usuario_existente:
            # Conta existe mas nunca foi ativada (ex: e-mail anterior falhou
            # ou o código expirou) — em vez de bloquear, atualiza os dados
            # com o que foi reenviado agora e manda um código novo.
            usuario_existente.nome = dados.nome
            usuario_existente.senha_hash = gerar_hash_senha(dados.senha)
            usuario_existente.codigo_verificacao = codigo
            usuario_existente.codigo_verificacao_expira = expira_em
            banco.commit()
            mensagem_resposta = "Você já tinha um cadastro pendente de confirmação. Enviamos um novo código para seu e-mail."
        else:
            novo_usuario = Usuario(
                nome=dados.nome,
                email=dados.email,
                senha_hash=gerar_hash_senha(dados.senha),
                ativo=False,
                codigo_verificacao=codigo,
                codigo_verificacao_expira=expira_em
            )
            banco.add(novo_usuario)
            banco.commit()
            banco.refresh(novo_usuario)
            mensagem_resposta = "Cadastro realizado! Enviamos um código de confirmação para seu e-mail."

        enviar_email_verificacao(dados.email, dados.nome, codigo)

        logger_usuario.info(f"Cadastro/reenvio de código | email: {dados.email}")

        return {
            "mensagem": mensagem_resposta,
            "email": dados.email
        }
    except HTTPException:
        raise
    except Exception as e:
        banco.rollback()
        logger_usuario.error(f"Erro ao cadastrar usuário | email: {dados.email} | erro: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao cadastrar usuário. Tente novamente."
        )


@roteador.post("/verificar-codigo", response_model=dict)
@limitador.limit("10/minute")
def verificar_codigo(
    request: Request,
    dados: VerificarCodigoRequest,
    banco: Session = Depends(pegar_banco)
):
    usuario = banco.query(Usuario).filter(Usuario.email == dados.email).first()

    if not usuario or not usuario.codigo_verificacao:
        raise HTTPException(status_code=400, detail="Código inválido ou expirado.")

    if usuario.ativo:
        raise HTTPException(status_code=400, detail="Esta conta já está confirmada.")

    if usuario.codigo_verificacao != dados.codigo:
        raise HTTPException(status_code=400, detail="Código incorreto.")

    if usuario.codigo_verificacao_expira < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Código expirado. Solicite um novo.")

    usuario.ativo = True
    usuario.codigo_verificacao = None
    usuario.codigo_verificacao_expira = None
    banco.commit()

    logger_usuario.info(f"E-mail verificado por código | email: {usuario.email}")

    return {"mensagem": "E-mail confirmado com sucesso! Você já pode fazer login."}


@roteador.post("/reenviar-confirmacao", response_model=dict)
@limitador.limit("3/minute")
def reenviar_confirmacao(
    request: Request,
    dados: ReenviarConfirmacaoRequest,
    banco: Session = Depends(pegar_banco)
):
    usuario = banco.query(Usuario).filter(Usuario.email == dados.email).first()

    if usuario and not usuario.ativo:
        codigo = gerar_codigo_verificacao()
        usuario.codigo_verificacao = codigo
        usuario.codigo_verificacao_expira = datetime.utcnow() + timedelta(minutes=MINUTOS_VALIDADE_CODIGO)
        banco.commit()
        enviar_email_verificacao(usuario.email, usuario.nome, codigo)
        logger_usuario.info(f"Código de confirmação reenviado | email: {dados.email}")

    # Mesma resposta independente do resultado, para não revelar se o
    # e-mail existe ou já está confirmado (mesmo padrão de /esqueci-senha).
    return {"mensagem": "Se este e-mail estiver cadastrado e pendente de confirmação, enviamos um novo código."}


@roteador.post("/refresh")
def renovar_token(
    request: Request,
    banco: Session = Depends(pegar_banco)
):
    from pydantic import BaseModel
    class RefreshTokenRequest(BaseModel):
        refresh_token: str

    dados = RefreshTokenRequest(**request.json())
    email = verificar_token(dados.refresh_token, tipo="refresh")

    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido ou expirado. Faça login novamente."
        )

    jti_antigo = extrair_jti(dados.refresh_token)
    if not jti_esta_valido(jti_antigo, banco):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido ou já utilizado. Faça login novamente."
        )

    usuario = banco.query(Usuario).filter(Usuario.email == email).first()
    if not usuario or not usuario.ativo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado ou desativado."
        )

    # Rotação: revoga o token usado e emite um novo — um refresh token só
    # serve pra uma renovação por vez. Se alguém usar um já rotacionado
    # (ex.: token roubado e usado depois do dono já ter renovado o dele),
    # essa tentativa cai no "jti_esta_valido" acima e é rejeitada.
    revogar_jti(jti_antigo, banco)
    novo_access_token = criar_token({"sub": usuario.email})
    novo_refresh_token, novo_jti = criar_refresh_token({"sub": usuario.email})
    banco.add(RefreshTokenValido(
        jti=novo_jti, usuario_id=usuario.id,
        expira_em=datetime.utcnow() + timedelta(days=EXPIRACAO_REFRESH_DIAS)
    ))
    banco.commit()

    return {
        "access_token": novo_access_token,
        "refresh_token": novo_refresh_token,
        "token_type": "bearer",
        "expira_em_minutos": 30
    }


@roteador.post("/logout")
def logout(
    request: Request,
    banco: Session = Depends(pegar_banco)
):
    """Revoga o refresh token no servidor — diferente de só limpar o
    token do navegador, isso garante que ele não funcione mais em
    lugar nenhum, mesmo que tenha sido copiado/roubado antes."""
    from pydantic import BaseModel
    class LogoutRequest(BaseModel):
        refresh_token: str

    try:
        dados = LogoutRequest(**request.json())
        jti = extrair_jti(dados.refresh_token)
        if jti:
            revogar_jti(jti, banco)
    except Exception:
        pass  # logout nunca falha visivelmente pro usuário, mesmo com token já inválido/mal formado

    return {"mensagem": "Sessão encerrada."}


@roteador.post("/login")
@limitador.limit("10/minute")
def login(
    request: Request,
    dados: LoginRequest,
    banco: Session = Depends(pegar_banco)
):
    verificar_bloqueio(dados.email, banco)

    usuario = banco.query(Usuario).filter(Usuario.email == dados.email).first()
    senha_correta = verificar_senha(dados.senha, usuario.senha_hash if usuario else HASH_DUMMY_TIMING)

    if not usuario or not senha_correta:
        registrar_tentativa_falha(dados.email, banco)
        restantes = tentativas_restantes(dados.email, banco)

        if restantes == 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Conta bloqueada por 15 minutos devido a excesso de tentativas."
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"E-mail ou senha incorretos. {restantes} tentativa(s) restante(s)."
        )

    if not usuario.ativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conta não verificada. Verifique seu e-mail para ativar a conta."
        )

    resetar_tentativas(dados.email, banco)

    access_token = criar_token({"sub": usuario.email})
    refresh_token, jti = criar_refresh_token({"sub": usuario.email})
    banco.add(RefreshTokenValido(
        jti=jti, usuario_id=usuario.id,
        expira_em=datetime.utcnow() + timedelta(days=EXPIRACAO_REFRESH_DIAS)
    ))
    banco.commit()

    logger_usuario.info(f"Login realizado | email: {usuario.email}")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expira_em_minutos": 30
    }


@roteador.post("/esqueci-senha", response_model=dict)
@limitador.limit("3/minute")
def esqueci_senha(
    request: Request,
    dados: EsqueciSenhaRequest,
    banco: Session = Depends(pegar_banco)
):
    usuario = banco.query(Usuario).filter(Usuario.email == dados.email).first()

    if usuario and usuario.ativo:
        token_reset = secrets.token_urlsafe(32)
        usuario.token_reset = token_reset
        usuario.token_reset_expira = datetime.utcnow() + timedelta(hours=1)
        banco.commit()
        enviar_email_reset(dados.email, usuario.nome, token_reset)
        logger_usuario.info(f"Reset de senha solicitado | email: {dados.email}")

    return {"mensagem": "Se este e-mail estiver cadastrado, você receberá as instruções em breve."}


@roteador.post("/redefinir-senha", response_model=dict)
def redefinir_senha(
    dados: RedefinirSenhaRequest,
    banco: Session = Depends(pegar_banco)
):
    usuario = banco.query(Usuario).filter(Usuario.token_reset == dados.token).first()

    if not usuario:
        raise HTTPException(status_code=400, detail="Link de redefinição inválido ou expirado.")

    if usuario.token_reset_expira < datetime.utcnow():
        usuario.token_reset = None
        usuario.token_reset_expira = None
        banco.commit()
        raise HTTPException(status_code=400, detail="Link de redefinição expirado. Solicite um novo.")

    try:
        usuario.senha_hash = gerar_hash_senha(dados.nova_senha)
        usuario.token_reset = None
        usuario.token_reset_expira = None
        # Mesmo motivo da troca de senha pelo Perfil: redefinição por
        # "esqueci minha senha" é tipicamente usada justamente por suspeita
        # de conta comprometida — revoga todas as sessões ativas.
        banco.query(RefreshTokenValido).filter(
            RefreshTokenValido.usuario_id == usuario.id,
            RefreshTokenValido.revogado == False
        ).update({"revogado": True})
        banco.commit()
        logger_usuario.info(f"Senha redefinida | email: {usuario.email}")
        return {"mensagem": "Senha redefinida com sucesso! Você já pode fazer login."}
    except Exception:
        banco.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao redefinir senha. Tente novamente."
        )


@roteador.get("/perfil", response_model=UsuarioResponse)
def perfil(usuario: Usuario = Depends(pegar_usuario_atual)):
    return usuario


@roteador.put("/perfil", response_model=UsuarioResponse)
def atualizar_perfil(
    dados: UsuarioAtualizar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if dados.email and banco.query(Usuario).filter(
        Usuario.email == dados.email,
        Usuario.id != usuario.id
    ).first():
        raise HTTPException(status_code=400, detail="E-mail já está em uso.")

    if dados.senha:
        if not dados.senha_atual:
            raise HTTPException(status_code=400, detail="Informe sua senha atual para definir uma nova senha.")
        if not verificar_senha(dados.senha_atual, usuario.senha_hash):
            raise HTTPException(status_code=400, detail="Senha atual incorreta.")
        if verificar_senha(dados.senha, usuario.senha_hash):
            raise HTTPException(status_code=400, detail="A nova senha não pode ser igual à senha atual.")

    try:
        if dados.senha:
            usuario.senha_hash = gerar_hash_senha(dados.senha)
            # Revoga TODOS os refresh tokens ativos desse usuário — se a
            # senha foi trocada por suspeita de acesso indevido, um token
            # roubado continuar funcionando normalmente depois da troca
            # anularia o motivo de ter trocado a senha. Forçar login de
            # novo em qualquer dispositivo/sessão é o comportamento esperado.
            banco.query(RefreshTokenValido).filter(
                RefreshTokenValido.usuario_id == usuario.id,
                RefreshTokenValido.revogado == False
            ).update({"revogado": True})
        if dados.nome is not None:
            usuario.nome = dados.nome
        if dados.nome_fazenda is not None:
            usuario.nome_fazenda = dados.nome_fazenda
        if dados.email is not None:
            usuario.email = dados.email  # já normalizado pelo schema (lower/strip)

        banco.commit()
        banco.refresh(usuario)
        logger_usuario.info(f"Perfil atualizado | email: {usuario.email}")
        return usuario
    except Exception:
        banco.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar perfil. Tente novamente."
        )


@roteador.post("/perfil/foto", response_model=UsuarioResponse)
def upload_foto_perfil(
    foto: UploadFile = File(...),
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    tipos_permitidos = ["image/jpeg", "image/png", "image/webp", "image/jpg"]
    if foto.content_type not in tipos_permitidos:
        raise HTTPException(status_code=400, detail="Formato inválido. Use JPG, PNG ou WEBP.")

    try:
        conteudo = foto.file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="Erro ao ler o arquivo enviado.")

    if len(conteudo) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Foto muito grande. Tamanho máximo: 5MB.")

    # O content_type acima vem do cliente e pode ser falsificado — confere
    # o conteúdo real do arquivo, abrindo-o de fato como imagem.
    try:
        imagem_verificacao = Image.open(io.BytesIO(conteudo))
        imagem_verificacao.verify()
        imagem_formato = Image.open(io.BytesIO(conteudo)).format
    except Exception:
        raise HTTPException(status_code=400, detail="Arquivo não é uma imagem válida.")
    if imagem_formato not in ("JPEG", "PNG", "WEBP"):
        raise HTTPException(status_code=400, detail="Formato inválido. Use JPG, PNG ou WEBP.")

    try:
        resultado = cloudinary.uploader.upload(
            conteudo,
            folder="leitetech/perfis",
            public_id=f"usuario_{usuario.id}",
            overwrite=True,
            transformation=[
                {"width": 400, "height": 400, "crop": "fill", "gravity": "face"},
                {"quality": "auto"},
                {"fetch_format": "auto"}
            ]
        )
        usuario.foto_url = resultado["secure_url"]
        banco.commit()
        banco.refresh(usuario)
        logger_usuario.info(f"Foto de perfil atualizada | email: {usuario.email}")
        return usuario
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Erro ao fazer upload da foto. Tente novamente."
        )


@roteador.delete("/perfil/foto")
def remover_foto_perfil(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if not usuario.foto_url:
        raise HTTPException(status_code=404, detail="Você não possui foto de perfil cadastrada.")

    try:
        cloudinary.uploader.destroy(f"leitetech/perfis/usuario_{usuario.id}")
        usuario.foto_url = None
        banco.commit()
        logger_usuario.info(f"Foto de perfil removida | email: {usuario.email}")
        return {"mensagem": "Foto de perfil removida com sucesso."}
    except Exception:
        banco.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Erro ao remover foto. Tente novamente."
        )