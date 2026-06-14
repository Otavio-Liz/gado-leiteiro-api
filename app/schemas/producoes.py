from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional

class ProducaoBase(BaseModel):
    animal_id:         int
    data:              date
    quantidade_litros: float
    turno:             str = "manha"
    observacao:        Optional[str] = None

class ProducaoCriar(ProducaoBase):
    pass

class ProducaoResposta(ProducaoBase):
    id:        int
    criado_em: Optional[datetime] = None

    class Config:
        from_attributes = True