from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional

class MedicamentoBase(BaseModel):
    animal_id:   int
    nome:        str
    motivo:      Optional[str] = None
    data_inicio: date
    data_fim:    Optional[date] = None
    observacao:  Optional[str] = None

class MedicamentoCriar(MedicamentoBase):
    pass

class MedicamentoResposta(MedicamentoBase):
    id:        int
    criado_em: Optional[datetime] = None

    class Config:
        from_attributes = True