from pydantic import BaseModel, field_validator, EmailStr, HttpUrl, Field
from datetime import datetime
from typing import Optional


class UsuarioCreate(BaseModel):
    username:       str = Field(min_length=3, max_length=50)
    senha:          str = Field(min_length=6, max_length=100)
    nome_completo:  Optional[str] = Field(default=None, max_length=100)
    email:          Optional[EmailStr] = None

    @field_validator("username")
    @classmethod
    def validar_username(cls, v):
        if not v.isalnum():
            raise ValueError("Username deve conter apenas letras e números")
        return v.lower()

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


class UsuarioAtualizar(BaseModel):
    nome_completo:  Optional[str] = Field(default=None, max_length=100)
    email:          Optional[EmailStr] = None
    senha:          Optional[str] = Field(default=None, min_length=6, max_length=100)
    foto_url:       Optional[HttpUrl] = None

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
    username:       str
    nome_completo:  Optional[str] = None
    email:          Optional[str] = None
    foto_url:       Optional[str] = None
    ativo:          bool
    criado_em:      Optional[datetime] = None

    class Config:
        from_attributes = True