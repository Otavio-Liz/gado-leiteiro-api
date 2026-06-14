from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional

class VacinaBase(BaseModel):
    animal_id:      int
    nome_vacina:    str
    data_aplicacao: date
    proxima_dose:   Optional[date] = None
    observacao:     Optional[str] = None

class VacinaCriar(VacinaBase):
    pass

class VacinaResposta(VacinaBase):
    id:        int
    criado_em: Optional[datetime] = None

    class Config:
        from_attributes = True