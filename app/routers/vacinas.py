from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import pegar_banco
from app.models.vacina import Vacina
from app.schemas.vacinas import VacinaCriar, VacinaResposta
from app.auth import pegar_usuario_atual
from typing import List

roteador = APIRouter(
    prefix="/vacinas",
    tags=["Vacinas"]
)

@roteador.get("/", response_model=List[VacinaResposta])
def listar_vacinas(banco: Session = Depends(pegar_banco), usuario: str = Depends(pegar_usuario_atual)):
    return banco.query(Vacina).all()

@roteador.get("/animal/{animal_id}", response_model=List[VacinaResposta])
def listar_vacinas_por_animal(animal_id: int, banco: Session = Depends(pegar_banco), usuario: str = Depends(pegar_usuario_atual)):
    vacinas = banco.query(Vacina).filter(Vacina.animal_id == animal_id).all()
    if not vacinas:
        raise HTTPException(status_code=404, detail="Nenhuma vacina encontrada para este animal")
    return vacinas

@roteador.get("/alertas", response_model=List[VacinaResposta])
def vacinas_vencendo(banco: Session = Depends(pegar_banco), usuario: str = Depends(pegar_usuario_atual)):
    from datetime import date, timedelta
    hoje = date.today()
    limite = hoje + timedelta(days=30)
    vacinas = banco.query(Vacina).filter(Vacina.proxima_dose.between(hoje, limite)).all()
    if not vacinas:
        raise HTTPException(status_code=404, detail="Nenhuma vacina vencendo nos próximos 30 dias")
    return vacinas

@roteador.post("/", response_model=VacinaResposta)
def criar_vacina(vacina: VacinaCriar, banco: Session = Depends(pegar_banco), usuario: str = Depends(pegar_usuario_atual)):
    nova_vacina = Vacina(**vacina.model_dump())
    banco.add(nova_vacina)
    banco.commit()
    banco.refresh(nova_vacina)
    return nova_vacina

@roteador.delete("/{vacina_id}")
def deletar_vacina(vacina_id: int, banco: Session = Depends(pegar_banco), usuario: str = Depends(pegar_usuario_atual)):
    vacina = banco.query(Vacina).filter(Vacina.id == vacina_id).first()
    if not vacina:
        raise HTTPException(status_code=404, detail="Vacina não encontrada")
    banco.delete(vacina)
    banco.commit()
    return {"mensagem": "Vacina removida com sucesso"}
