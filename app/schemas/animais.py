from pydantic import BaseModel, validator
from datetime import date, datetime
from typing import Optional


class AnimalBase(BaseModel):
    nome:                   str
    brinco:                 str
    raca:                   Optional[str] = None
    nascimento:             Optional[date] = None
    sexo:                   str = "F"

    # Genealogia
    nome_pai:               Optional[str] = None
    nome_mae:               Optional[str] = None
    registro_genealogico:   Optional[str] = None

    # Status
    status:                 str = "ativo"
    status_reprodutivo:     str = "nao_aplicavel"

    # Produção
    producao_diaria_litros: Optional[int] = None

    # Reprodução
    data_ultima_inseminacao: Optional[date] = None
    data_prevista_parto:     Optional[date] = None
    dias_em_lactacao:        Optional[int] = None

    # Informações adicionais
    peso_kg:                Optional[int] = None
    observacao:             Optional[str] = None
    foto_url:               Optional[str] = None

    @validator("sexo")
    def validar_sexo(cls, v):
        if v not in ("F", "M"):
            raise ValueError("Sexo deve ser 'F' ou 'M'")
        return v

    @validator("status")
    def validar_status(cls, v):
        opcoes = ("ativo", "inativo", "vendido", "morto", "seco")
        if v not in opcoes:
            raise ValueError(f"Status deve ser um de: {opcoes}")
        return v

    @validator("status_reprodutivo")
    def validar_status_reprodutivo(cls, v):
        opcoes = ("vazia", "prenha", "em_cio", "em_lactacao", "seca", "nao_aplicavel")
        if v not in opcoes:
            raise ValueError(f"Status reprodutivo deve ser um de: {opcoes}")
        return v

    @validator("producao_diaria_litros")
    def validar_producao(cls, v):
        if v is not None and v < 0:
            raise ValueError("Produção diária não pode ser negativa")
        return v

    @validator("peso_kg")
    def validar_peso(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Peso deve ser maior que zero")
        return v


class AnimalCriar(AnimalBase):
    pass


class AnimalAtualizar(BaseModel):
    nome:                   Optional[str] = None
    brinco:                 Optional[str] = None
    raca:                   Optional[str] = None
    nascimento:             Optional[date] = None
    sexo:                   Optional[str] = None
    nome_pai:               Optional[str] = None
    nome_mae:               Optional[str] = None
    registro_genealogico:   Optional[str] = None
    status:                 Optional[str] = None
    status_reprodutivo:     Optional[str] = None
    producao_diaria_litros: Optional[int] = None
    data_ultima_inseminacao: Optional[date] = None
    data_prevista_parto:    Optional[date] = None
    dias_em_lactacao:       Optional[int] = None
    peso_kg:                Optional[int] = None
    observacao:             Optional[str] = None
    foto_url:               Optional[str] = None


class AnimalResposta(AnimalBase):
    id:         int
    usuario_id: int
    criado_em:  Optional[datetime] = None
    atualizado_em: Optional[datetime] = None

    class Config:
        from_attributes = True