from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import pegar_banco
from app.models.animal import Animal
from app.schemas.animais import AnimalCriar, AnimalResposta
from typing import List

roteador = APIRouter(
    prefix="/animais",
    tags=["Animais"]
)

@roteador.get("/", response_model=List[AnimalResposta])
def listar_animais(banco: Session = Depends(pegar_banco)):
    animais = banco.query(Animal).all()
    return animais

@roteador.get("/{animal_id}", response_model=AnimalResposta)
def buscar_animal(animal_id: int, banco: Session = Depends(pegar_banco)):
    animal = banco.query(Animal).filter(Animal.id == animal_id).first()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal não encontrado")
    return animal

@roteador.post("/", response_model=AnimalResposta)
def criar_animal(animal: AnimalCriar, banco: Session = Depends(pegar_banco)):
    novo_animal = Animal(**animal.model_dump())
    banco.add(novo_animal)
    banco.commit()
    banco.refresh(novo_animal)
    return novo_animal

@roteador.delete("/{animal_id}")
def deletar_animal(animal_id: int, banco: Session = Depends(pegar_banco)):
    animal = banco.query(Animal).filter(Animal.id == animal_id).first()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal não encontrado")
    banco.delete(animal)
    banco.commit()
    return {"mensagem": "Animal removido com sucesso"}