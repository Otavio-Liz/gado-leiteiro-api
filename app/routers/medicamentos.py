from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import pegar_banco
from app.models.medicamento import Medicamento
from app.schemas.medicamentos import MedicamentoCriar, MedicamentoResposta
from typing import List

roteador = APIRouter(
    prefix="/medicamentos",
    tags=["Medicamentos"]
)

@roteador.get("/", response_model=List[MedicamentoResposta])
def listar_medicamentos(banco: Session = Depends(pegar_banco)):
    return banco.query(Medicamento).all()

@roteador.get("/animal/{animal_id}", response_model=List[MedicamentoResposta])
def listar_medicamentos_por_animal(animal_id: int, banco: Session = Depends(pegar_banco)):
    medicamentos = banco.query(Medicamento).filter(Medicamento.animal_id == animal_id).all()
    if not medicamentos:
        raise HTTPException(status_code=404, detail="Nenhum medicamento encontrado para este animal")
    return medicamentos

@roteador.post("/", response_model=MedicamentoResposta)
def criar_medicamento(medicamento: MedicamentoCriar, banco: Session = Depends(pegar_banco)):
    novo_medicamento = Medicamento(**medicamento.model_dump())
    banco.add(novo_medicamento)
    banco.commit()
    banco.refresh(novo_medicamento)
    return novo_medicamento

@roteador.delete("/{medicamento_id}")
def deletar_medicamento(medicamento_id: int, banco: Session = Depends(pegar_banco)):
    medicamento = banco.query(Medicamento).filter(Medicamento.id == medicamento_id).first()
    if not medicamento:
        raise HTTPException(status_code=404, detail="Medicamento não encontrado")
    banco.delete(medicamento)
    banco.commit()
    return {"mensagem": "Medicamento removido com sucesso"}