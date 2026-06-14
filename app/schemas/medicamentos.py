from pydantic import BaseModel, validator
from datetime import date, datetime
from typing import Optional
from decimal import Decimal


# ─── Medicamento (Estoque) ───────────────────────────────────────────────────

class MedicamentoBase(BaseModel):
    nome:               str
    principio_ativo:    Optional[str] = None
    fabricante:         Optional[str] = None
    dias_carencia:      int = 0
    estoque_atual:      Decimal = Decimal("0")
    estoque_minimo:     Decimal = Decimal("0")
    unidade:            str = "dose"
    observacao:         Optional[str] = None

    @validator("dias_carencia")
    def validar_carencia(cls, v):
        if v < 0:
            raise ValueError("Dias de carência não pode ser negativo")
        return v

    @validator("estoque_atual", "estoque_minimo")
    def validar_estoque(cls, v):
        if v < 0:
            raise ValueError("Estoque não pode ser negativo")
        return v


class MedicamentoCriar(MedicamentoBase):
    pass


class MedicamentoAtualizar(BaseModel):
    nome:               Optional[str] = None
    principio_ativo:    Optional[str] = None
    fabricante:         Optional[str] = None
    dias_carencia:      Optional[int] = None
    estoque_atual:      Optional[Decimal] = None
    estoque_minimo:     Optional[Decimal] = None
    unidade:            Optional[str] = None
    observacao:         Optional[str] = None


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
    animal_id:      int
    medicamento_id: int
    data_aplicacao: date
    dose_aplicada:  Decimal
    motivo:         Optional[str] = None
    observacao:     Optional[str] = None

    @validator("dose_aplicada")
    def validar_dose(cls, v):
        if v <= 0:
            raise ValueError("Dose aplicada deve ser maior que zero")
        return v


class AplicacaoMedicamentoCriar(AplicacaoMedicamentoBase):
    pass


class AplicacaoMedicamentoAtualizar(BaseModel):
    data_aplicacao: Optional[date] = None
    dose_aplicada:  Optional[Decimal] = None
    motivo:         Optional[str] = None
    observacao:     Optional[str] = None


class AplicacaoMedicamentoResposta(AplicacaoMedicamentoBase):
    id:                     int
    dias_carencia:          int
    carencia_encerra_em:    Optional[date] = None
    criado_em:              Optional[datetime] = None

    class Config:
        from_attributes = True