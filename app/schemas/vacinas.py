from pydantic import BaseModel, field_validator, model_validator, Field
from datetime import date, datetime
from typing import Optional


class VacinaBase(BaseModel):
    animal_id:       int = Field(gt=0)
    nome_vacina:     str = Field(min_length=1, max_length=100)
    doenca_alvo:     Optional[str] = Field(default=None, max_length=100)
    data_aplicacao:  date
    proxima_dose:    Optional[date] = None
    lote:            Optional[str] = Field(default=None, max_length=50)
    validade_vacina: Optional[date] = None
    dose_aplicada:   Optional[str] = Field(default=None, max_length=50)
    via_aplicacao:   Optional[str] = Field(default=None, max_length=50)
    responsavel:     Optional[str] = Field(default=None, max_length=100)
    observacao:      Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validar_datas(self):
        if self.proxima_dose and self.data_aplicacao:
            if self.proxima_dose <= self.data_aplicacao:
                raise ValueError("Próxima dose deve ser depois da data de aplicação")
        if self.validade_vacina and self.data_aplicacao:
            if self.validade_vacina < self.data_aplicacao:
                raise ValueError("Vacina não pode ser aplicada após a data de validade")
        return self


class VacinaCriar(VacinaBase):
    pass


class VacinaAtualizar(BaseModel):
    nome_vacina:     Optional[str] = Field(default=None, min_length=1, max_length=100)
    doenca_alvo:     Optional[str] = Field(default=None, max_length=100)
    data_aplicacao:  Optional[date] = None
    proxima_dose:    Optional[date] = None
    lote:            Optional[str] = Field(default=None, max_length=50)
    validade_vacina: Optional[date] = None
    dose_aplicada:   Optional[str] = Field(default=None, max_length=50)
    via_aplicacao:   Optional[str] = Field(default=None, max_length=50)
    responsavel:     Optional[str] = Field(default=None, max_length=100)
    observacao:      Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validar_datas(self):
        if self.proxima_dose and self.data_aplicacao:
            if self.proxima_dose <= self.data_aplicacao:
                raise ValueError("Próxima dose deve ser depois da data de aplicação")
        if self.validade_vacina and self.data_aplicacao:
            if self.validade_vacina < self.data_aplicacao:
                raise ValueError("Vacina não pode ser aplicada após a data de validade")
        return self


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