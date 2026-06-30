from pydantic import BaseModel, field_validator, HttpUrl, Field
from datetime import date, datetime
from typing import Optional
from decimal import Decimal


class AnimalBase(BaseModel):
    nome:                   str = Field(min_length=1, max_length=100)
    brinco:                 str = Field(min_length=1, max_length=50)
    raca:                   Optional[str] = Field(default=None, max_length=100)
    nascimento:             Optional[date] = None
    sexo:                   str = "F"

    # Genealogia
    nome_pai:               Optional[str] = Field(default=None, max_length=100)
    nome_mae:               Optional[str] = Field(default=None, max_length=100)
    registro_genealogico:   Optional[str] = Field(default=None, max_length=100)

    # Status
    status:                 str = "ativo"
    status_reprodutivo:     str = "nao_aplicavel"

    # Produção
    producao_diaria_litros: Optional[int] = None

    # Reprodução
    data_ultima_inseminacao: Optional[date] = None
    data_prevista_parto:     Optional[date] = None
    dias_em_lactacao:        Optional[int] = None
    quantidade_partos:       Optional[int] = 0

    # Informações adicionais
    # peso_kg é Decimal (não int) — peso de animal é uma medida contínua,
    # faz sentido aceitar casas decimais (ex: 375.50). Numeric(6,2) no
    # banco, ver migration correspondente.
    peso_kg:                Optional[Decimal] = None
    observacao:             Optional[str] = Field(default=None, max_length=500)
    foto_url:               Optional[HttpUrl] = None

    @field_validator("sexo")
    @classmethod
    def validar_sexo(cls, v):
        if v not in ("F", "M"):
            raise ValueError("Sexo deve ser 'F' ou 'M'")
        return v

    @field_validator("status")
    @classmethod
    def validar_status(cls, v):
        opcoes = ("ativo", "inativo", "vendido", "morto", "seco")
        if v not in opcoes:
            raise ValueError(f"Status deve ser um de: {opcoes}")
        return v

    @field_validator("status_reprodutivo")
    @classmethod
    def validar_status_reprodutivo(cls, v):
        opcoes = ("vazia", "prenha", "em_cio", "em_lactacao", "seca", "nao_aplicavel")
        if v not in opcoes:
            raise ValueError(f"Status reprodutivo deve ser um de: {opcoes}")
        return v

    @field_validator("producao_diaria_litros")
    @classmethod
    def validar_producao(cls, v):
        if v is not None and v < 0:
            raise ValueError("Produção diária não pode ser negativa")
        return v

    @field_validator("peso_kg")
    @classmethod
    def validar_peso(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Peso deve ser maior que zero")
        return v

    @field_validator("quantidade_partos")
    @classmethod
    def validar_quantidade_partos(cls, v):
        if v is not None and v < 0:
            raise ValueError("Quantidade de partos não pode ser negativa")
        return v


class AnimalCriar(AnimalBase):
    pass


class AnimalAtualizar(BaseModel):
    nome:                   Optional[str] = Field(default=None, min_length=1, max_length=100)
    brinco:                 Optional[str] = Field(default=None, min_length=1, max_length=50)
    raca:                   Optional[str] = Field(default=None, max_length=100)
    nascimento:             Optional[date] = None
    sexo:                   Optional[str] = None
    nome_pai:               Optional[str] = Field(default=None, max_length=100)
    nome_mae:               Optional[str] = Field(default=None, max_length=100)
    registro_genealogico:   Optional[str] = Field(default=None, max_length=100)
    status:                 Optional[str] = None
    status_reprodutivo:     Optional[str] = None
    producao_diaria_litros: Optional[int] = None
    data_ultima_inseminacao: Optional[date] = None
    data_prevista_parto:    Optional[date] = None
    dias_em_lactacao:       Optional[int] = None
    quantidade_partos:      Optional[int] = None
    data_ultimo_parto:      Optional[date] = None
    peso_kg:                Optional[Decimal] = None
    observacao:             Optional[str] = Field(default=None, max_length=500)
    foto_url:               Optional[HttpUrl] = None

    @field_validator("sexo")
    @classmethod
    def validar_sexo(cls, v):
        if v is not None and v not in ("F", "M"):
            raise ValueError("Sexo deve ser 'F' ou 'M'")
        return v

    @field_validator("status")
    @classmethod
    def validar_status(cls, v):
        if v is not None:
            opcoes = ("ativo", "inativo", "vendido", "morto", "seco")
            if v not in opcoes:
                raise ValueError(f"Status deve ser um de: {opcoes}")
        return v

    @field_validator("status_reprodutivo")
    @classmethod
    def validar_status_reprodutivo(cls, v):
        if v is not None:
            opcoes = ("vazia", "prenha", "em_cio", "em_lactacao", "seca", "nao_aplicavel")
            if v not in opcoes:
                raise ValueError(f"Status reprodutivo deve ser um de: {opcoes}")
        return v

    @field_validator("producao_diaria_litros")
    @classmethod
    def validar_producao(cls, v):
        if v is not None and v < 0:
            raise ValueError("Produção diária não pode ser negativa")
        return v

    @field_validator("peso_kg")
    @classmethod
    def validar_peso(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Peso deve ser maior que zero")
        return v

    @field_validator("quantidade_partos")
    @classmethod
    def validar_quantidade_partos(cls, v):
        if v is not None and v < 0:
            raise ValueError("Quantidade de partos não pode ser negativa")
        return v


class AnimalResposta(AnimalBase):
    id:                int
    usuario_id:        int
    data_ultimo_parto: Optional[date] = None
    criado_em:         Optional[datetime] = None
    atualizado_em:     Optional[datetime] = None

    class Config:
        from_attributes = True