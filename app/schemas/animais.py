from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional

class AnimalBase(BaseModel):
    nome:       str
    brinco:     str
    raca:       Optional[str] = None
    nascimento: Optional[date] = None
    sexo:       str = "F"
    status:     str = "ativo"

class AnimalCriar(AnimalBase):
    usuario_id: int

class AnimalResposta(AnimalBase):
    id:        int
    criado_em: Optional[datetime] = None

    class Config:
        from_attributes = True