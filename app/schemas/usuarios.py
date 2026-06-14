from pydantic import BaseModel, validator
from datetime import datetime
from typing import Optional


class UsuarioCreate(BaseModel):
    username:       str
    senha:          str
    nome_completo:  Optional[str] = None
    email:          Optional[str] = None

    @validator("username")
    def validar_username(cls, v):
        if len(v) < 3:
            raise ValueError("Username deve ter pelo menos 3 caracteres")
        if not v.isalnum():
            raise ValueError("Username deve conter apenas letras e números")
        return v.lower()

    @validator("senha")
    def validar_senha(cls, v):
        if len(v) < 6:
            raise ValueError("Senha deve ter pelo menos 6 caracteres")
        return v


class UsuarioAtualizar(BaseModel):
    nome_completo:  Optional[str] = None
    email:          Optional[str] = None
    senha:          Optional[str] = None


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