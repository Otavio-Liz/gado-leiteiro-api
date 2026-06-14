from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import pegar_banco
from app.models.producao import Producao
from app.schemas.producoes import ProducaoCriar, ProducaoResposta
from app.auth import pegar_usuario_atual
from typing import List

roteador = APIRouter(
    prefix="/producoes",
    tags=["Produções"]
)

@roteador.get("/", response_model=List[ProducaoResposta])
def listar_producoes(banco: Session = Depends(pegar_banco), usuario: str = Depends(pegar_usuario_atual)):
    producoes = banco.query(Producao).all()
    return producoes

@roteador.get("/animal/{animal_id}", response_model=List[ProducaoResposta])
def listar_producoes_por_animal(animal_id: int, banco: Session = Depends(pegar_banco), usuario: str = Depends(pegar_usuario_atual)):
    producoes = banco.query(Producao).filter(Producao.animal_id == animal_id).all()
    if not producoes:
        raise HTTPException(status_code=404, detail="Nenhuma produção encontrada para este animal")
    return producoes

@roteador.post("/", response_model=ProducaoResposta)
def criar_producao(producao: ProducaoCriar, banco: Session = Depends(pegar_banco), usuario: str = Depends(pegar_usuario_atual)):
    nova_producao = Producao(**producao.model_dump())
    banco.add(nova_producao)
    banco.commit()
    banco.refresh(nova_producao)
    return nova_producao

@roteador.delete("/{producao_id}")
def deletar_producao(producao_id: int, banco: Session = Depends(pegar_banco), usuario: str = Depends(pegar_usuario_atual)):
    producao = banco.query(Producao).filter(Producao.id == producao_id).first()
    if not producao:
        raise HTTPException(status_code=404, detail="Produção não encontrada")
    banco.delete(producao)
    banco.commit()
    return {"mensagem": "Produção removida com sucesso"}