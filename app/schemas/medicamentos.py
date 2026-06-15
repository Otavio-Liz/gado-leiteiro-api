from pydantic import BaseModel, field_validator, Field
from datetime import date, datetime
from typing import Optional
from decimal import Decimal


UNIDADES_VALIDAS = ("dose", "ml", "mg", "g", "comprimido", "frasco")


# ─── Medicamento (Estoque) ───────────────────────────────────────────────────

class MedicamentoBase(BaseModel):
    nome:               str = Field(min_length=1, max_length=100)
    principio_ativo:    Optional[str] = Field(default=None, max_length=100)
    fabricante:         Optional[str] = Field(default=None, max_length=100)
    dias_carencia:      int = 0
    estoque_atual:      Decimal = Decimal("0")
    estoque_minimo:     Decimal = Decimal("0")
    unidade:            str = "dose"
    observacao:         Optional[str] = Field(default=None, max_length=500)

    @field_validator("dias_carencia")
    @classmethod
    def validar_carencia(cls, v):
        if v < 0:
            raise ValueError("Dias de carência não pode ser negativo")
        return v

    @field_validator("estoque_atual", "estoque_minimo")
    @classmethod
    def validar_estoque(cls, v):
        if v < 0:
            raise ValueError("Estoque não pode ser negativo")
        return v

    @field_validator("unidade")
    @classmethod
    def validar_unidade(cls, v):
        if v not in UNIDADES_VALIDAS:
            raise ValueError(f"Unidade deve ser uma de: {UNIDADES_VALIDAS}")
        return v


class MedicamentoCriar(MedicamentoBase):
    pass


class MedicamentoAtualizar(BaseModel):
    nome:               Optional[str] = Field(default=None, min_length=1, max_length=100)
    principio_ativo:    Optional[str] = Field(default=None, max_length=100)
    fabricante:         Optional[str] = Field(default=None, max_length=100)
    dias_carencia:      Optional[int] = None
    estoque_atual:      Optional[Decimal] = None
    estoque_minimo:     Optional[Decimal] = None
    unidade:            Optional[str] = None
    observacao:         Optional[str] = Field(default=None, max_length=500)

    @field_validator("dias_carencia")
    @classmethod
    def validar_carencia(cls, v):
        if v is not None and v < 0:
            raise ValueError("Dias de carência não pode ser negativo")
        return v

    @field_validator("estoque_atual", "estoque_minimo")
    @classmethod
    def validar_estoque(cls, v):
        if v is not None and v < 0:
            raise ValueError("Estoque não pode ser negativo")
        return v

    @field_validator("unidade")
    @classmethod
    def validar_unidade(cls, v):
        if v is not None and v not in UNIDADES_VALIDAS:
            raise ValueError(f"Unidade deve ser uma de: {UNIDADES_VALIDAS}")
        return v


class MedicamentoResposta(MedicamentoBase):
    id:             int
    usuario_id:     int
    criado_em:      Optional[datetime] = None
    atualizado_em:  Optional[datetime] = None

    class Config:
        from_attributes = True


class MedicamentoAlerta(BaseModel):
    """Retornado quando estoque está abaixo do mínimo."""
    id:             int
    nome:           str
    estoque_atual:  Decimal
    estoque_minimo: Decimal
    unidade:        str

    class Config:
        from_attributes = True


# ─── Aplicação de Medicamento (por animal) ───────────────────────────────────

class AplicacaoMedicamentoBase(BaseModel):
    animal_id:      int = Field(gt=0)
    medicamento_id: int = Field(gt=0)
    data_aplicacao: date
    dose_aplicada:  Decimal
    motivo:         Optional[str] = Field(default=None, max_length=200)
    observacao:     Optional[str] = Field(default=None, max_length=500)

    @field_validator("dose_aplicada")
    @classmethod
    def validar_dose(cls, v):
        if v <= 0:
            raise ValueError("Dose aplicada deve ser maior que zero")
        return v


class AplicacaoMedicamentoCriar(AplicacaoMedicamentoBase):
    pass


class AplicacaoMedicamentoAtualizar(BaseModel):
    data_aplicacao: Optional[date] = None
    dose_aplicada:  Optional[Decimal] = None
    motivo:         Optional[str] = Field(default=None, max_length=200)
    observacao:     Optional[str] = Field(default=None, max_length=500)

    @field_validator("dose_aplicada")
    @classmethod
    def validar_dose(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Dose aplicada deve ser maior que zero")
        return v


class AplicacaoMedicamentoResposta(AplicacaoMedicamentoBase):
    id:                     int
    dias_carencia:          int
    carencia_encerra_em:    Optional[date] = None
    criado_em:              Optional[datetime] = None

    class Config:
        from_attributes = True