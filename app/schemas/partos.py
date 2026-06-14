from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional

class PartoBase(BaseModel):
    animal_id:  int
    data_parto: date
    status_cria: str = "vivo"
    sexo_cria:  Optional[str] = None
    observacao: Optional[str] = None

class PartoCriar(PartoBase):
    pass

class PartoResposta(PartoBase):
    id:        int
    criado_em: Optional[datetime] = None

    class Config:
        from_attributes = True