from pydantic import BaseModel, validator
from datetime import date, datetime
from typing import Optional


class VacinaBase(BaseModel):
    animal_id:      int
    nome_vacina:    str
    doenca_alvo:    Optional[str] = None
    data_aplicacao: date
    proxima_dose:   Optional[date] = None
    lote:           Optional[str] = None
    validade_vacina: Optional[date] = None
    dose_aplicada:  Optional[str] = None
    via_aplicacao:  Optional[str] = None
    responsavel:    Optional[str] = None
    observacao:     Optional[str] = None

    @validator("proxima_dose")
    def validar_proxima_dose(cls, v, values):
        if v and values.get("data_aplicacao") and v <= values["data_aplicacao"]:
            raise ValueError("Próxima dose deve ser depois da data de aplicação")
        return v

    @validator("validade_vacina")
    def validar_validade(cls, v, values):
        if v and values.get("data_aplicacao") and v < values["data_aplicacao"]:
            raise ValueError("Vacina não pode ser aplicada após a data de validade")
        return v


class VacinaCriar(VacinaBase):
    pass


class VacinaAtualizar(BaseModel):
    nome_vacina:    Optional[str] = None
    doenca_alvo:    Optional[str] = None
    data_aplicacao: Optional[date] = None
    proxima_dose:   Optional[date] = None
    lote:           Optional[str] = None
    validade_vacina: Optional[date] = None
    dose_aplicada:  Optional[str] = None
    via_aplicacao:  Optional[str] = None
    responsavel:    Optional[str] = None
    observacao:     Optional[str] = None


class VacinaResposta(VacinaBase):
    id:             int
    criado_em:      Optional[datetime] = None
    atualizado_em:  Optional[datetime] = None

    class Config:
        from_attributes = True


class VacinaAlerta(BaseModel):
    """Retornado quando a próxima dose está próxima."""
    id:             int
    animal_id:      int
    animal_nome:    str
    nome_vacina:    str
    proxima_dose:   date
    dias_restantes: int

    class Config:
        from_attributes = True