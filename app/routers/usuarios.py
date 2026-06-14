from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import pegar_banco
from app.models.usuario import Usuario
from app.schemas.usuarios import UsuarioCreate, UsuarioResponse, UsuarioAtualizar
from app.security import verificar_senha, gerar_hash_senha
from app.auth import (
    criar_token, criar_refresh_token, verificar_token,
    verificar_bloqueio, registrar_tentativa_falha,
    resetar_tentativas, tentativas_restantes,
    pegar_usuario_atual
)
from app.cloudinary_config import upload_foto_animal, deletar_foto_animal
from app.limitador import limitador
from pydantic import BaseModel
import cloudinary.uploader

roteador = APIRouter(prefix="/usuarios", tags=["Usuários"])


class RefreshTokenRequest(BaseModel):
    refresh_token: str


@roteador.post("/login")
@limitador.limit("10/minute")
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    banco: Session = Depends(pegar_banco)
):
    # Verificar se está bloqueado
    verificar_bloqueio(form.username)

    usuario = banco.query(Usuario).filter(Usuario.username == form.username).first()

    if not usuario or not verificar_senha(form.password, usuario.senha_hash):
        registrar_tentativa_falha(form.username)
        restantes = tentativas_restantes(form.username)

        if restantes == 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Conta bloqueada por 15 minutos devido a excesso de tentativas"
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Usuário ou senha incorretos. Tentativas restantes: {restantes}"
        )

    if not usuario.ativo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuário desativado. Entre em contato com o suporte"
        )

    resetar_tentativas(form.username)

    access_token = criar_token({"sub": usuario.username})
    refresh_token = criar_refresh_token({"sub": usuario.username})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expira_em_minutos": 30
    }


@roteador.post("/refresh")
def renovar_token(
    dados: RefreshTokenRequest,
    banco: Session = Depends(pegar_banco)
):
    """Renova o access token usando o refresh token sem precisar fazer login novamente."""
    username = verificar_token(dados.refresh_token, tipo="refresh")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido ou expirado. Faça login novamente"
        )

    usuario = banco.query(Usuario).filter(Usuario.username == username).first()
    if not usuario or not usuario.ativo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado ou desativado"
        )

    novo_access_token = criar_token({"sub": usuario.username})

    return {
        "access_token": novo_access_token,
        "token_type": "bearer",
        "expira_em_minutos": 30
    }


@roteador.post("/cadastrar", response_model=UsuarioResponse)
@limitador.limit("5/minute")
def cadastrar(
    request: Request,
    dados: UsuarioCreate,
    banco: Session = Depends(pegar_banco)
):
    if banco.query(Usuario).filter(Usuario.username == dados.username).first():
        raise HTTPException(status_code=400, detail="Username já está em uso")
    if dados.email and banco.query(Usuario).filter(Usuario.email == dados.email).first():
        raise HTTPException(status_code=400, detail="E-mail já está em uso")

    novo_usuario = Usuario(
        username=dados.username,
        senha_hash=gerar_hash_senha(dados.senha),
        nome_completo=dados.nome_completo,
        email=dados.email
    )
    banco.add(novo_usuario)
    banco.commit()
    banco.refresh(novo_usuario)
    return novo_usuario


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
        raise HTTPException(status_code=400, detail="E-mail já está em uso")

    if dados.senha:
        usuario.senha_hash = gerar_hash_senha(dados.senha)
    if dados.nome_completo is not None:
        usuario.nome_completo = dados.nome_completo
    if dados.email is not None:
        usuario.email = dados.email

    banco.commit()
    banco.refresh(usuario)
    return usuario


@roteador.post("/perfil/foto", response_model=UsuarioResponse)
def upload_foto_perfil(
    foto: UploadFile = File(...),
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    # Validar tipo de arquivo
    tipos_permitidos = ["image/jpeg", "image/png", "image/webp", "image/jpg"]
    if foto.content_type not in tipos_permitidos:
        raise HTTPException(status_code=400, detail="Formato inválido. Use JPG, PNG ou WEBP")

    # Validar tamanho (máx 5MB)
    conteudo = foto.file.read()
    if len(conteudo) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Foto muito grande. Tamanho máximo: 5MB")

    # Upload para o Cloudinary
    resultado = cloudinary.uploader.upload(
        conteudo,
        folder="gado_leiteiro/perfis",
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
    return usuario


@roteador.delete("/perfil/foto")
def remover_foto_perfil(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if not usuario.foto_url:
        raise HTTPException(status_code=404, detail="Você não possui foto de perfil cadastrada")

    cloudinary.uploader.destroy(f"gado_leiteiro/perfis/usuario_{usuario.id}")
    usuario.foto_url = None
    banco.commit()
    return {"mensagem": "Foto de perfil removida com sucesso"}