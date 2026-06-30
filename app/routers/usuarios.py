from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.database import pegar_banco
from app.models.usuario import Usuario
from app.schemas.usuarios import (
    UsuarioCreate, UsuarioResponse, UsuarioAtualizar, LoginRequest,
    EsqueciSenhaRequest, RedefinirSenhaRequest,
    VerificarCodigoRequest, ReenviarConfirmacaoRequest,
    ConfirmarNovoEmailRequest, RefreshTokenRequest, LogoutRequest
)
from app.security import verificar_senha, gerar_hash_senha
from app.auth import (
    criar_token, criar_refresh_token, verificar_token,
    verificar_bloqueio, registrar_tentativa_falha,
    resetar_tentativas, tentativas_restantes,
    pegar_usuario_atual, revogar_jti, revogar_jti_atomico,
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

# Limite de tentativas erradas de código de verificação por "ciclo" de
# código ativo — compartilhado entre ativação de cadastro e confirmação de
# novo e-mail, ambos usando a mesma coluna tentativas_codigo_verificacao.
# Ao atingir o limite, o código é invalidado e a pessoa precisa solicitar
# um novo, em vez de poder continuar tentando indefinidamente (o código
# tem só 6 dígitos — 1 milhão de combinações é pouco contra tentativa
# ilimitada, mesmo com rate limit por IP, já que um atacante pode trocar
# de IP/proxy).
MAX_TENTATIVAS_CODIGO = 5


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


def enviar_email_confirmacao_novo_email(email: str, nome: str, codigo: str):
    """Enviado SEMPRE para o e-mail NOVO (nunca para o antigo) — confirmar
    posse do endereço novo é o objetivo desse fluxo. O e-mail antigo
    continua sendo a identidade de login até essa confirmação acontecer."""
    try:
        resend.Emails.send({
            "from": FROM_EMAIL,
            "to": email,
            "subject": "✅ Confirme seu novo e-mail — LeiteTech",
            "html": f"""
            <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px;background:#050d0a;color:#fff;border-radius:12px;">
                <h1 style="font-size:20px;color:#00ff88;margin-bottom:8px;">LeiteTech</h1>
                <h2 style="font-size:16px;font-weight:500;color:#fff;margin-bottom:16px;">Olá, {nome}! Confirme seu novo e-mail</h2>
                <p style="color:rgba(255,255,255,0.6);font-size:14px;line-height:1.6;margin-bottom:24px;">
                    Você solicitou a troca do e-mail da sua conta. Use o código abaixo para confirmar este endereço como o novo e-mail de login. Ele expira em {MINUTOS_VALIDADE_CODIGO} minutos.
                </p>
                <div style="text-align:center;margin-bottom:24px;">
                    <span style="display:inline-block;padding:14px 28px;background:rgba(0,255,136,0.08);border:1px solid #00ff88;color:#00ff88;border-radius:8px;font-size:28px;font-weight:700;letter-spacing:0.2em;">
                        {codigo}
                    </span>
                </div>
                <p style="color:rgba(255,255,255,0.3);font-size:11px;margin-top:24px;">
                    Se você não solicitou essa troca, ignore este e-mail — seu e-mail de login atual continuará funcionando normalmente.
                </p>
            </div>
            """
        })
    except Exception as e:
        logger_usuario.error(f"Erro ao enviar email de confirmação de novo e-mail para {email}: {e}")


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
            usuario_existente.tentativas_codigo_verificacao = 0
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

    if usuario.codigo_verificacao_expira < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Código expirado. Solicite um novo.")

    if usuario.codigo_verificacao != dados.codigo:
        # Conta tentativa errada — depois de MAX_TENTATIVAS_CODIGO, o
        # código é invalidado e a pessoa precisa solicitar um novo. Sem
        # isso, o código de 6 dígitos podia ser atacado por força bruta
        # (rate limit de IP não impede um atacante trocando de IP).
        usuario.tentativas_codigo_verificacao += 1
        if usuario.tentativas_codigo_verificacao >= MAX_TENTATIVAS_CODIGO:
            usuario.codigo_verificacao = None
            usuario.codigo_verificacao_expira = None
            usuario.tentativas_codigo_verificacao = 0
            banco.commit()
            raise HTTPException(
                status_code=400,
                detail="Muitas tentativas incorretas. Solicite um novo código."
            )
        banco.commit()
        raise HTTPException(status_code=400, detail="Código incorreto.")

    usuario.ativo = True
    usuario.codigo_verificacao = None
    usuario.codigo_verificacao_expira = None
    usuario.tentativas_codigo_verificacao = 0
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
        usuario.tentativas_codigo_verificacao = 0
        banco.commit()
        enviar_email_verificacao(usuario.email, usuario.nome, codigo)
        logger_usuario.info(f"Código de confirmação reenviado | email: {dados.email}")

    # Mesma resposta independente do resultado, para não revelar se o
    # e-mail existe ou já está confirmado (mesmo padrão de /esqueci-senha).
    return {"mensagem": "Se este e-mail estiver cadastrado e pendente de confirmação, enviamos um novo código."}


@roteador.post("/refresh")
def renovar_token(
    dados: RefreshTokenRequest,
    banco: Session = Depends(pegar_banco)
):
    """
    Antes lia o corpo via request.json() dentro de função síncrona —
    Request.json() é coroutine, então **request.json() quebrava com
    TypeError em toda chamada (bug crítico: /refresh estava 100% quebrado).
    Agora recebe RefreshTokenRequest como parâmetro normal, igual o resto
    do arquivo já fazia.
    """
    payload = verificar_token(dados.refresh_token, tipo="refresh")
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido ou expirado. Faça login novamente."
        )

    usuario_id = payload.get("usuario_id")
    if usuario_id is not None:
        usuario = banco.query(Usuario).filter(Usuario.id == usuario_id).first()
    else:
        # Fallback pra refresh tokens emitidos antes do usuario_id existir
        # no payload — válidos por até 7 dias após o deploy dessa mudança.
        usuario = banco.query(Usuario).filter(Usuario.email == payload.get("sub")).first()

    if not usuario or not usuario.ativo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado ou desativado."
        )

    # Rotação atômica: revogar_jti_atomico faz a checagem de validade E a
    # revogação numa única operação UPDATE condicional no banco. Antes,
    # eram duas etapas separadas (jti_esta_valido + revogar_jti) — duas
    # requisições concorrentes com o mesmo refresh token podiam ambas
    # passar pela checagem antes de qualquer uma revogar, e as duas
    # geravam um par de tokens novos a partir do MESMO token antigo (race
    # condition real). Com a operação atômica, só uma das duas chamadas
    # concorrentes recebe True — a outra recebe False e é rejeitada aqui,
    # antes de gerar qualquer token novo.
    jti_antigo = payload.get("jti")
    revogado_com_sucesso = revogar_jti_atomico(jti_antigo, banco)
    if not revogado_com_sucesso:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido, expirado ou já utilizado. Faça login novamente."
        )

    novo_access_token = criar_token(usuario)
    novo_refresh_token, novo_jti = criar_refresh_token(usuario)
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
    dados: LogoutRequest,
    banco: Session = Depends(pegar_banco)
):
    """
    Revoga o refresh token no servidor — diferente de só limpar o token do
    navegador, isso garante que ele não funcione mais em lugar nenhum,
    mesmo que tenha sido copiado/roubado antes.

    Antes, o uso de request.json() síncrono quebrava antes mesmo de extrair
    o jti, e o try/except: pass engolia esse erro — logout sempre "dava
    certo" pra quem chamava, mas NUNCA revogava nada de verdade. Agora
    recebe LogoutRequest tipado e revoga de fato.
    """
    payload = verificar_token(dados.refresh_token, tipo="refresh")
    if payload is not None:
        jti = payload.get("jti")
        if jti:
            revogar_jti(jti, banco)

    # Resposta sempre igual, mesmo se o token já estiver inválido/expirado —
    # do ponto de vista de quem chama, "sessão encerrada" é verdade nos
    # dois casos (ou foi revogada agora, ou já não valia nada mesmo).
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

    access_token = criar_token(usuario)
    refresh_token, jti = criar_refresh_token(usuario)
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
    """
    Troca de e-mail agora exige senha atual e nunca aplica o e-mail novo
    direto — grava em email_pendente + código, manda o código pro e-mail
    NOVO, e só aplica de fato em POST /usuarios/confirmar-novo-email. O
    e-mail de login continua sendo o antigo até essa confirmação.

    foto_url não existe mais em UsuarioAtualizar (removido do schema) — a
    única forma de mudar a foto de perfil é POST /usuarios/perfil/foto.
    """
    email_novo_solicitado = dados.email is not None and dados.email != usuario.email

    if email_novo_solicitado:
        if not dados.senha_atual:
            raise HTTPException(status_code=400, detail="Informe sua senha atual para trocar de e-mail.")
        if not verificar_senha(dados.senha_atual, usuario.senha_hash):
            raise HTTPException(status_code=400, detail="Senha atual incorreta.")
        if banco.query(Usuario).filter(
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

        codigo_email_pendente = None
        if email_novo_solicitado:
            codigo_email_pendente = gerar_codigo_verificacao()
            usuario.email_pendente = dados.email  # já normalizado pelo schema (lower/strip)
            usuario.email_pendente_codigo = codigo_email_pendente
            usuario.email_pendente_expira = datetime.utcnow() + timedelta(minutes=MINUTOS_VALIDADE_CODIGO)
            usuario.tentativas_codigo_verificacao = 0

        banco.commit()
        banco.refresh(usuario)

        if email_novo_solicitado:
            enviar_email_confirmacao_novo_email(dados.email, usuario.nome, codigo_email_pendente)

        logger_usuario.info(f"Perfil atualizado | email: {usuario.email}")
        return usuario
    except Exception:
        banco.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar perfil. Tente novamente."
        )


@roteador.post("/confirmar-novo-email", response_model=UsuarioResponse)
@limitador.limit("10/minute")
def confirmar_novo_email(
    request: Request,
    dados: ConfirmarNovoEmailRequest,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    """
    Aplica de fato a troca de e-mail iniciada em PUT /perfil, depois de
    confirmar o código enviado para o e-mail NOVO. O usuário já está
    autenticado nesse ponto (com o e-mail ANTIGO, que continua valendo até
    aqui).
    """
    if not usuario.email_pendente or not usuario.email_pendente_codigo:
        raise HTTPException(status_code=400, detail="Não há troca de e-mail pendente.")

    if usuario.email_pendente_expira and usuario.email_pendente_expira < datetime.utcnow():
        usuario.email_pendente = None
        usuario.email_pendente_codigo = None
        usuario.email_pendente_expira = None
        usuario.tentativas_codigo_verificacao = 0
        banco.commit()
        raise HTTPException(status_code=400, detail="Código expirado. Solicite a troca de e-mail novamente.")

    if dados.codigo != usuario.email_pendente_codigo:
        usuario.tentativas_codigo_verificacao += 1
        if usuario.tentativas_codigo_verificacao >= MAX_TENTATIVAS_CODIGO:
            usuario.email_pendente = None
            usuario.email_pendente_codigo = None
            usuario.email_pendente_expira = None
            usuario.tentativas_codigo_verificacao = 0
            banco.commit()
            raise HTTPException(
                status_code=400,
                detail="Muitas tentativas incorretas. Solicite a troca de e-mail novamente."
            )
        banco.commit()
        raise HTTPException(status_code=400, detail="Código incorreto.")

    # Reconfere unicidade no momento da confirmação — proteção contra a
    # janela de tempo entre solicitar a troca e confirmar (alguém poderia
    # ter cadastrado esse mesmo e-mail nesse meio-tempo).
    conflito = banco.query(Usuario).filter(
        Usuario.email == usuario.email_pendente,
        Usuario.id != usuario.id
    ).first()
    if conflito:
        usuario.email_pendente = None
        usuario.email_pendente_codigo = None
        usuario.email_pendente_expira = None
        usuario.tentativas_codigo_verificacao = 0
        banco.commit()
        raise HTTPException(status_code=400, detail="Este e-mail já está em uso por outra conta.")

    usuario.email = usuario.email_pendente
    usuario.email_pendente = None
    usuario.email_pendente_codigo = None
    usuario.email_pendente_expira = None
    usuario.tentativas_codigo_verificacao = 0
    banco.commit()
    banco.refresh(usuario)

    logger_usuario.info(f"E-mail alterado com confirmação | novo email: {usuario.email}")
    return usuario


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