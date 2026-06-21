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
    nome:       Optional[str] = Field(default=None, min_length=2, max_length=150)
    email:      Optional[EmailStr] = None
    senha:      Optional[str] = Field(default=None, min_length=6, max_length=100)
    foto_url:   Optional[str] = None

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
    id:         int
    nome:       str
    email:      str
    foto_url:   Optional[str] = None
    ativo:      bool
    criado_em:  Optional[datetime] = None

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