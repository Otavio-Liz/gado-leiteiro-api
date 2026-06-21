from pydantic import BaseModel, field_validator, model_validator, Field
from datetime import date, datetime
from typing import Optional
from decimal import Decimal


# ─── Produção de Leite ───────────────────────────────────────────────────────

class ProducaoBase(BaseModel):
    animal_id:          int = Field(gt=0)
    data:               date
    quantidade_litros:  Decimal
    status:             str = "aproveitado"
    motivo_descarte:    Optional[str] = Field(default=None, max_length=300)
    observacao:         Optional[str] = Field(default=None, max_length=500)

    @field_validator("quantidade_litros")
    @classmethod
    def validar_litros(cls, v):
        if v <= 0:
            raise ValueError("Quantidade de litros deve ser maior que zero")
        return v

    @field_validator("status")
    @classmethod
    def validar_status(cls, v):
        if v not in ("aproveitado", "descartado"):
            raise ValueError("Status deve ser 'aproveitado' ou 'descartado'")
        return v

    @model_validator(mode="after")
    def validar_motivo_descarte(self):
        if self.status == "descartado" and not self.motivo_descarte:
            raise ValueError("Informe o motivo do descarte")
        return self


class ProducaoCriar(ProducaoBase):
    pass


class ProducaoAtualizar(BaseModel):
    data:               Optional[date] = None
    quantidade_litros:  Optional[Decimal] = None
    status:             Optional[str] = None
    motivo_descarte:    Optional[str] = Field(default=None, max_length=300)
    observacao:         Optional[str] = Field(default=None, max_length=500)

    @field_validator("quantidade_litros")
    @classmethod
    def validar_litros(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Quantidade de litros deve ser maior que zero")
        return v

    @field_validator("status")
    @classmethod
    def validar_status(cls, v):
        if v is not None and v not in ("aproveitado", "descartado"):
            raise ValueError("Status deve ser 'aproveitado' ou 'descartado'")
        return v

    @model_validator(mode="after")
    def validar_motivo_descarte(self):
        if self.status == "descartado" and not self.motivo_descarte:
            raise ValueError("Informe o motivo do descarte")
        return self


class ProducaoResposta(ProducaoBase):
    id:             int
    criado_em:      Optional[datetime] = None
    atualizado_em:  Optional[datetime] = None

    class Config:
        from_attributes = True


# ─── Relatório de Produção ───────────────────────────────────────────────────

class ProducaoAnimalRelatorio(BaseModel):
    """Relatório de produção por animal em um período."""
    animal_id:                 int
    animal_nome:               str
    animal_brinco:             str
    total_litros:              Decimal
    total_litros_aproveitados: Decimal
    total_litros_descartados:  Decimal
    media_diaria:              Decimal
    valor_total:               Decimal
    preco_litro_vigente:       Decimal


class ProducaoRebanhoRelatorio(BaseModel):
    """Relatório consolidado do rebanho."""
    periodo_inicio:            date
    periodo_fim:               date
    total_animais:             int
    total_litros:              Decimal
    total_litros_aproveitados: Decimal
    total_litros_descartados:  Decimal
    media_diaria_rebanho:      Decimal
    valor_total:               Decimal
    preco_litro_vigente:       Decimal
    animais:                   list[ProducaoAnimalRelatorio]


# ─── Preço do Leite ──────────────────────────────────────────────────────────

class PrecoLeiteBase(BaseModel):
    preco_litro:        Decimal = Field(gt=0)
    vigente_a_partir:   date
    observacao:         Optional[str] = Field(default=None, max_length=255)


class PrecoLeiteCriar(PrecoLeiteBase):
    pass


class PrecoLeiteAtualizar(BaseModel):
    preco_litro:        Optional[Decimal] = None
    vigente_a_partir:   Optional[date] = None
    observacao:         Optional[str] = Field(default=None, max_length=255)

    @field_validator("preco_litro")
    @classmethod
    def validar_preco(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Preço por litro deve ser maior que zero")
        return v


class PrecoLeiteResposta(PrecoLeiteBase):
    id:         int
    usuario_id: int
    criado_em:  Optional[datetime] = None

    class Config:
        from_attributes = True