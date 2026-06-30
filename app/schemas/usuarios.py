# ESTE ARQUIVO VAI EM: app/schemas/usuarios.py (classes BaseModel, sem rota)
from pydantic import BaseModel, field_validator, EmailStr, Field
from datetime import datetime
from typing import Optional


class UsuarioCreate(BaseModel):
    nome:   str = Field(min_length=2, max_length=150)
    email:  EmailStr
    senha:  str = Field(min_length=6, max_length=100)

    @field_validator("email")
    @classmethod
    def validar_email(cls, v):
        return v.lower().strip()

    @field_validator("nome")
    @classmethod
    def validar_nome(cls, v):
        if not any(c.isalpha() for c in v):
            raise ValueError("Nome deve conter pelo menos uma letra")
        return v.strip()

    @field_validator("senha")
    @classmethod
    def validar_senha(cls, v):
        if not any(c.islower() for c in v):
            raise ValueError("Senha deve ter pelo menos uma letra minúscula")
        if not any(c.isdigit() for c in v):
            raise ValueError("Senha deve ter pelo menos um número")
        if not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in v):
            raise ValueError("Senha deve ter pelo menos um símbolo especial")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    senha: str

    @field_validator("email")
    @classmethod
    def validar_email(cls, v):
        return v.lower().strip()


class UsuarioAtualizar(BaseModel):
    """
    foto_url NÃO existe mais aqui de propósito — esse campo nunca foi de
    fato usado pelo router (que só atualiza nome/nome_fazenda/email/senha),
    mas o schema aceitava qualquer URL nesse campo sem validar nada. Era um
    "campo morto perigoso": inofensivo hoje só porque ninguém lê
    dados.foto_url no router, mas um refactor futuro descuidado poderia
    aplicar esse valor direto, permitindo que qualquer usuário apontasse a
    própria foto de perfil pra uma URL arbitrária (incluindo conteúdo
    malicioso) sem passar pelo upload real via Cloudinary. A única forma
    válida de mudar a foto de perfil é POST /usuarios/perfil/foto.
    """
    nome:         Optional[str] = Field(default=None, min_length=2, max_length=150)
    nome_fazenda: Optional[str] = Field(default=None, max_length=150)
    email:        Optional[EmailStr] = None
    senha_atual:  Optional[str] = None
    senha:        Optional[str] = Field(default=None, min_length=6, max_length=100)

    @field_validator("nome_fazenda")
    @classmethod
    def validar_nome_fazenda(cls, v):
        return v.strip() if v is not None else v

    @field_validator("email")
    @classmethod
    def validar_email(cls, v):
        # Mesma normalização de UsuarioCreate/LoginRequest — sem isso, a
        # checagem de e-mail duplicado no router comparava o valor digitado
        # sem normalizar, deixando passar duplicidade só por diferença de
        # maiúscula/minúscula (ex: "JOAO@x.com" vs "joao@x.com" já existente).
        if v is not None:
            return v.lower().strip()
        return v

    @field_validator("senha")
    @classmethod
    def validar_senha(cls, v):
        if v is not None:
            if not any(c.islower() for c in v):
                raise ValueError("Senha deve ter pelo menos uma letra minúscula")
            if not any(c.isdigit() for c in v):
                raise ValueError("Senha deve ter pelo menos um número")
            if not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in v):
                raise ValueError("Senha deve ter pelo menos um símbolo especial")
        return v


class UsuarioResponse(BaseModel):
    id:             int
    nome:           str
    nome_fazenda:   Optional[str] = None
    email:          str
    # Informativo apenas — indica pro frontend que existe uma troca de
    # e-mail pendente de confirmação, sem expor o código em si (nunca
    # devolvido em nenhuma resposta da API).
    email_pendente: Optional[str] = None
    foto_url:       Optional[str] = None
    ativo:          bool
    criado_em:      Optional[datetime] = None

    class Config:
        from_attributes = True


# ─── Reset de senha ───────────────────────────────────────────────────────────

class EsqueciSenhaRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def validar_email(cls, v):
        return v.lower().strip()


class RedefinirSenhaRequest(BaseModel):
    token: str
    nova_senha: str = Field(min_length=6, max_length=100)

    @field_validator("nova_senha")
    @classmethod
    def validar_senha(cls, v):
        if not any(c.islower() for c in v):
            raise ValueError("Senha deve ter pelo menos uma letra minúscula")
        if not any(c.isdigit() for c in v):
            raise ValueError("Senha deve ter pelo menos um número")
        if not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in v):
            raise ValueError("Senha deve ter pelo menos um símbolo especial")
        return v


class VerificarCodigoRequest(BaseModel):
    email: EmailStr
    codigo: str = Field(min_length=6, max_length=6)

    @field_validator("email")
    @classmethod
    def validar_email(cls, v):
        return v.lower().strip()

    @field_validator("codigo")
    @classmethod
    def validar_codigo(cls, v):
        if not v.isdigit():
            raise ValueError("Código deve conter apenas números")
        return v


class ReenviarConfirmacaoRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def validar_email(cls, v):
        return v.lower().strip()


# ─── Troca de e-mail com confirmação ──────────────────────────────────────────

class ConfirmarNovoEmailRequest(BaseModel):
    """
    Usado em POST /usuarios/confirmar-novo-email. O usuário já está
    autenticado nesse ponto (rota protegida por pegar_usuario_atual) — só
    precisa confirmar o código que recebeu no e-mail NOVO, não o antigo.
    """
    codigo: str = Field(min_length=6, max_length=6)

    @field_validator("codigo")
    @classmethod
    def validar_codigo(cls, v):
        if not v.isdigit():
            raise ValueError("Código deve conter apenas números")
        return v


# ─── Refresh / Logout ──────────────────────────────────────────────────────────
#
# Antes o router lia o corpo da requisição via request.json() dentro de uma
# função síncrona — Request.json() é uma coroutine, então chamá-la sem
# await numa def comum não executava a leitura de verdade (retornava um
# objeto coroutine não resolvido), e o **request.json() quebrava com
# TypeError. Esses dois schemas substituem isso pelo padrão normal do
# FastAPI: parâmetro tipado direto na assinatura da rota.

class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str