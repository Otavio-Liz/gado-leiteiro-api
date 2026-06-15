from pydantic import BaseModel, field_validator, Field
from datetime import date, datetime
from typing import Optional


class PartoBase(BaseModel):
    animal_id:                int = Field(gt=0)
    data_parto:               date
    tipo_parto:               str = "normal"
    status_cria:              str = "vivo"
    sexo_cria:                Optional[str] = None
    nome_cria:                Optional[str] = Field(default=None, max_length=100)
    peso_cria_kg:             Optional[int] = None
    dias_carencia_colostro:   int = 7
    data_inicio_periodo_seco: Optional[date] = None
    observacao:               Optional[str] = Field(default=None, max_length=500)

    @field_validator("tipo_parto")
    @classmethod
    def validar_tipo_parto(cls, v):
        opcoes = ("normal", "cesariana", "distocico")
        if v not in opcoes:
            raise ValueError(f"Tipo de parto deve ser um de: {opcoes}")
        return v

    @field_validator("status_cria")
    @classmethod
    def validar_status_cria(cls, v):
        opcoes = ("vivo", "morto", "natimorto")
        if v not in opcoes:
            raise ValueError(f"Status da cria deve ser um de: {opcoes}")
        return v

    @field_validator("sexo_cria")
    @classmethod
    def validar_sexo_cria(cls, v):
        if v is not None and v not in ("F", "M"):
            raise ValueError("Sexo da cria deve ser 'F' ou 'M'")
        return v

    @field_validator("dias_carencia_colostro")
    @classmethod
    def validar_carencia(cls, v):
        if v < 0:
            raise ValueError("Dias de carência não pode ser negativo")
        return v

    @field_validator("peso_cria_kg")
    @classmethod
    def validar_peso_cria(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Peso da cria deve ser maior que zero")
        return v


class PartoCriar(PartoBase):
    pass


class PartoAtualizar(BaseModel):
    data_parto:               Optional[date] = None
    tipo_parto:               Optional[str] = None
    status_cria:              Optional[str] = None
    sexo_cria:                Optional[str] = None
    nome_cria:                Optional[str] = Field(default=None, max_length=100)
    peso_cria_kg:             Optional[int] = None
    dias_carencia_colostro:   Optional[int] = None
    data_inicio_periodo_seco: Optional[date] = None
    observacao:               Optional[str] = Field(default=None, max_length=500)

    @field_validator("tipo_parto")
    @classmethod
    def validar_tipo_parto(cls, v):
        if v is not None:
            opcoes = ("normal", "cesariana", "distocico")
            if v not in opcoes:
                raise ValueError(f"Tipo de parto deve ser um de: {opcoes}")
        return v

    @field_validator("status_cria")
    @classmethod
    def validar_status_cria(cls, v):
        if v is not None:
            opcoes = ("vivo", "morto", "natimorto")
            if v not in opcoes:
                raise ValueError(f"Status da cria deve ser um de: {opcoes}")
        return v

    @field_validator("sexo_cria")
    @classmethod
    def validar_sexo_cria(cls, v):
        if v is not None and v not in ("F", "M"):
            raise ValueError("Sexo da cria deve ser 'F' ou 'M'")
        return v

    @field_validator("dias_carencia_colostro")
    @classmethod
    def validar_carencia(cls, v):
        if v is not None and v < 0:
            raise ValueError("Dias de carência não pode ser negativo")
        return v

    @field_validator("peso_cria_kg")
    @classmethod
    def validar_peso_cria(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Peso da cria deve ser maior que zero")
        return v


class PartoResposta(PartoBase):
    id:                  int
    carencia_encerra_em: Optional[date] = None
    criado_em:           Optional[datetime] = None
    atualizado_em:       Optional[datetime] = None

    class Config:
        from_attributes = True