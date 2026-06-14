from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import pegar_banco
from app.models.parto import Parto
from app.schemas.partos import PartoCriar, PartoResposta
from typing import List

roteador = APIRouter(
    prefix="/partos",
    tags=["Partos"]
)

@roteador.get("/", response_model=List[PartoResposta])
def listar_partos(banco: Session = Depends(pegar_banco)):
    return banco.query(Parto).all()

@roteador.get("/animal/{animal_id}", response_model=List[PartoResposta])
def listar_partos_por_animal(animal_id: int, banco: Session = Depends(pegar_banco)):
    partos = banco.query(Parto).filter(Parto.animal_id == animal_id).all()
    if not partos:
        raise HTTPException(status_code=404, detail="Nenhum parto encontrado para este animal")
    return partos

@roteador.post("/", response_model=PartoResposta)
def criar_parto(parto: PartoCriar, banco: Session = Depends(pegar_banco)):
    novo_parto = Parto(**parto.model_dump())
    banco.add(novo_parto)
    banco.commit()
    banco.refresh(novo_parto)
    return novo_parto

@roteador.delete("/{parto_id}")
def deletar_parto(parto_id: int, banco: Session = Depends(pegar_banco)):
    parto = banco.query(Parto).filter(Parto.id == parto_id).first()
    if not parto:
        raise HTTPException(status_code=404, detail="Parto não encontrado")
    banco.delete(parto)
    banco.commit()
    return {"mensagem": "Parto removido com sucesso"}