from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import pegar_banco
from app.models.reproducao import Reproducao, Ocorrencia
from app.models.animal import Animal
from app.schemas.reproducao import (
    ReproducaoCriar, ReproducaoResposta, ReproducaoAtualizar,
    OcorrenciaCriar, OcorrenciaResposta, OcorrenciaAtualizar
)
from app.auth import pegar_usuario_atual
from app.models.usuario import Usuario
from datetime import date, timedelta
from typing import List

roteador = APIRouter(
    prefix="/reproducao",
    tags=["Reprodução e Sanidade"]
)


# ─── Reprodução ──────────────────────────────────────────────────────────────

@roteador.get("/", response_model=List[ReproducaoResposta])
def listar_reproducoes(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    return banco.query(Reproducao).join(Animal).filter(
        Animal.usuario_id == usuario.id
    ).order_by(Reproducao.data_cobertura.desc()).all()


@roteador.get("/animal/{animal_id}", response_model=List[ReproducaoResposta])
def listar_reproducoes_por_animal(
    animal_id: int,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    animal = banco.query(Animal).filter(
        Animal.id == animal_id,
        Animal.usuario_id == usuario.id
    ).first()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal não encontrado")
    return banco.query(Reproducao).filter(
        Reproducao.animal_id == animal_id
    ).order_by(Reproducao.data_cobertura.desc()).all()


@roteador.post("/", response_model=ReproducaoResposta)
def registrar_reproducao(
    dados: ReproducaoCriar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    animal = banco.query(Animal).filter(
        Animal.id == dados.animal_id,
        Animal.usuario_id == usuario.id
    ).first()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal não encontrado")
    if animal.sexo == "M":
        raise HTTPException(status_code=400, detail="Machos não podem ter registros reprodutivos femininos")
    if animal.status != "ativo":
        raise HTTPException(status_code=400, detail=f"Animal está '{animal.status}'")

    dados_dict = dados.model_dump()

    # Calcular data prevista do parto (gestação bovina ~283 dias)
    if dados.data_cobertura:
        data_prevista_parto = dados.data_cobertura + timedelta(days=283)
        data_inicio_seco = data_prevista_parto - timedelta(days=60)
        dados_dict["data_prevista_parto"] = data_prevista_parto
        dados_dict["data_inicio_periodo_seco"] = data_inicio_seco

        # Atualizar animal
        animal.data_ultima_inseminacao = dados.data_cobertura
        animal.data_prevista_parto = data_prevista_parto

    # Atualizar status reprodutivo se diagnóstico positivo
    if dados.resultado_diagnostico == "positivo":
        animal.status_reprodutivo = "prenha"

    nova_reproducao = Reproducao(**dados_dict)
    banco.add(nova_reproducao)
    banco.commit()
    banco.refresh(nova_reproducao)
    return nova_reproducao


@roteador.put("/{reproducao_id}", response_model=ReproducaoResposta)
def atualizar_reproducao(
    reproducao_id: int,
    dados: ReproducaoAtualizar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    reproducao = banco.query(Reproducao).join(Animal).filter(
        Reproducao.id == reproducao_id,
        Animal.usuario_id == usuario.id
    ).first()
    if not reproducao:
        raise HTTPException(status_code=404, detail="Registro reprodutivo não encontrado")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(reproducao, campo, valor)
    banco.commit()
    banco.refresh(reproducao)
    return reproducao


@roteador.delete("/{reproducao_id}")
def deletar_reproducao(
    reproducao_id: int,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    reproducao = banco.query(Reproducao).join(Animal).filter(
        Reproducao.id == reproducao_id,
        Animal.usuario_id == usuario.id
    ).first()
    if not reproducao:
        raise HTTPException(status_code=404, detail="Registro reprodutivo não encontrado")
    banco.delete(reproducao)
    banco.commit()
    return {"mensagem": "Registro reprodutivo removido com sucesso"}


# ─── Ocorrências Sanitárias ───────────────────────────────────────────────────

@roteador.get("/ocorrencias/", response_model=List[OcorrenciaResposta])
def listar_ocorrencias(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    return banco.query(Ocorrencia).join(Animal).filter(
        Animal.usuario_id == usuario.id
    ).order_by(Ocorrencia.data_ocorrencia.desc()).all()


@roteador.get("/ocorrencias/abertas", response_model=List[OcorrenciaResposta])
def listar_ocorrencias_abertas(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    """Retorna ocorrências ainda não resolvidas."""
    return banco.query(Ocorrencia).join(Animal).filter(
        Animal.usuario_id == usuario.id,
        Ocorrencia.data_resolucao == None
    ).order_by(Ocorrencia.data_ocorrencia.desc()).all()


@roteador.get("/ocorrencias/animal/{animal_id}", response_model=List[OcorrenciaResposta])
def listar_ocorrencias_por_animal(
    animal_id: int,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    animal = banco.query(Animal).filter(
        Animal.id == animal_id,
        Animal.usuario_id == usuario.id
    ).first()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal não encontrado")
    return banco.query(Ocorrencia).filter(
        Ocorrencia.animal_id == animal_id
    ).order_by(Ocorrencia.data_ocorrencia.desc()).all()


@roteador.post("/ocorrencias/", response_model=OcorrenciaResposta)
def registrar_ocorrencia(
    dados: OcorrenciaCriar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    animal = banco.query(Animal).filter(
        Animal.id == dados.animal_id,
        Animal.usuario_id == usuario.id
    ).first()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal não encontrado")
    if dados.data_ocorrencia > date.today():
        raise HTTPException(status_code=400, detail="Data da ocorrência não pode ser no futuro")

    nova_ocorrencia = Ocorrencia(**dados.model_dump())
    banco.add(nova_ocorrencia)
    banco.commit()
    banco.refresh(nova_ocorrencia)
    return nova_ocorrencia


@roteador.put("/ocorrencias/{ocorrencia_id}", response_model=OcorrenciaResposta)
def atualizar_ocorrencia(
    ocorrencia_id: int,
    dados: OcorrenciaAtualizar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    ocorrencia = banco.query(Ocorrencia).join(Animal).filter(
        Ocorrencia.id == ocorrencia_id,
        Animal.usuario_id == usuario.id
    ).first()
    if not ocorrencia:
        raise HTTPException(status_code=404, detail="Ocorrência não encontrada")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(ocorrencia, campo, valor)
    banco.commit()
    banco.refresh(ocorrencia)
    return ocorrencia


@roteador.delete("/ocorrencias/{ocorrencia_id}")
def deletar_ocorrencia(
    ocorrencia_id: int,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    ocorrencia = banco.query(Ocorrencia).join(Animal).filter(
        Ocorrencia.id == ocorrencia_id,
        Animal.usuario_id == usuario.id
    ).first()
    if not ocorrencia:
        raise HTTPException(status_code=404, detail="Ocorrência não encontrada")
    banco.delete(ocorrencia)
    banco.commit()
    return {"mensagem": "Ocorrência removida com sucesso"}