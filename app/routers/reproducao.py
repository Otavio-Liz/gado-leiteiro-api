from fastapi import APIRouter, Depends, HTTPException, status
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
from app.logger import logger_rep
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
    try:
        return banco.query(Reproducao).join(Animal).filter(
            Animal.usuario_id == usuario.id
        ).order_by(Reproducao.data_cobertura.desc()).all()
    except Exception:
        logger_rep.error(f"Erro ao listar reproduções | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar registros reprodutivos. Tente novamente."
        )


@roteador.get("/animal/{animal_id}", response_model=List[ReproducaoResposta])
def listar_reproducoes_por_animal(
    animal_id: int,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if animal_id <= 0:
        raise HTTPException(status_code=400, detail="ID do animal inválido.")
    try:
        animal = banco.query(Animal).filter(
            Animal.id == animal_id,
            Animal.usuario_id == usuario.id
        ).first()
        if not animal:
            raise HTTPException(status_code=404, detail="Animal não encontrado.")
        return banco.query(Reproducao).filter(
            Reproducao.animal_id == animal_id
        ).order_by(Reproducao.data_cobertura.desc()).all()
    except HTTPException:
        raise
    except Exception:
        logger_rep.error(f"Erro ao listar reproduções do animal {animal_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar registros reprodutivos. Tente novamente."
        )


@roteador.post("/", response_model=ReproducaoResposta)
def registrar_reproducao(
    dados: ReproducaoCriar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        animal = banco.query(Animal).filter(
            Animal.id == dados.animal_id,
            Animal.usuario_id == usuario.id
        ).first()
        if not animal:
            raise HTTPException(status_code=404, detail="Animal não encontrado.")
        if animal.sexo == "M":
            raise HTTPException(
                status_code=400,
                detail="Machos não podem ter registros reprodutivos femininos."
            )
        if animal.status != "ativo":
            raise HTTPException(
                status_code=400,
                detail=f"Animal está '{animal.status}' e não pode ter registros reprodutivos."
            )

        dados_dict = dados.model_dump()

        if dados.data_cobertura:
            data_prevista_parto = dados.data_cobertura + timedelta(days=283)
            data_inicio_seco = data_prevista_parto - timedelta(days=60)
            dados_dict["data_prevista_parto"] = data_prevista_parto
            dados_dict["data_inicio_periodo_seco"] = data_inicio_seco
            animal.data_ultima_inseminacao = dados.data_cobertura
            animal.data_prevista_parto = data_prevista_parto

        if dados.resultado_diagnostico == "positivo":
            animal.status_reprodutivo = "prenha"

        nova_reproducao = Reproducao(**dados_dict)
        banco.add(nova_reproducao)
        banco.commit()
        banco.refresh(nova_reproducao)
        logger_rep.info(f"Reprodução registrada | animal: {dados.animal_id} | usuário: {usuario.id}")
        return nova_reproducao
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        logger_rep.error(f"Erro ao registrar reprodução | animal: {dados.animal_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao registrar reprodução. Tente novamente."
        )


@roteador.put("/{reproducao_id}", response_model=ReproducaoResposta)
def atualizar_reproducao(
    reproducao_id: int,
    dados: ReproducaoAtualizar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if reproducao_id <= 0:
        raise HTTPException(status_code=400, detail="ID do registro inválido.")
    try:
        reproducao = banco.query(Reproducao).join(Animal).filter(
            Reproducao.id == reproducao_id,
            Animal.usuario_id == usuario.id
        ).first()
        if not reproducao:
            raise HTTPException(status_code=404, detail="Registro reprodutivo não encontrado.")
        for campo, valor in dados.model_dump(exclude_unset=True).items():
            setattr(reproducao, campo, valor)
        banco.commit()
        banco.refresh(reproducao)
        logger_rep.info(f"Reprodução atualizada | id: {reproducao_id} | usuário: {usuario.id}")
        return reproducao
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        logger_rep.error(f"Erro ao atualizar reprodução | id: {reproducao_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar registro reprodutivo. Tente novamente."
        )


@roteador.delete("/{reproducao_id}")
def deletar_reproducao(
    reproducao_id: int,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if reproducao_id <= 0:
        raise HTTPException(status_code=400, detail="ID do registro inválido.")
    try:
        reproducao = banco.query(Reproducao).join(Animal).filter(
            Reproducao.id == reproducao_id,
            Animal.usuario_id == usuario.id
        ).first()
        if not reproducao:
            raise HTTPException(status_code=404, detail="Registro reprodutivo não encontrado.")
        banco.delete(reproducao)
        banco.commit()
        logger_rep.info(f"Reprodução deletada | id: {reproducao_id} | usuário: {usuario.id}")
        return {"mensagem": "Registro reprodutivo removido com sucesso."}
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        logger_rep.error(f"Erro ao deletar reprodução | id: {reproducao_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao remover registro reprodutivo. Tente novamente."
        )


# ─── Ocorrências Sanitárias ───────────────────────────────────────────────────

@roteador.get("/ocorrencias/", response_model=List[OcorrenciaResposta])
def listar_ocorrencias(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        return banco.query(Ocorrencia).join(Animal).filter(
            Animal.usuario_id == usuario.id
        ).order_by(Ocorrencia.data_ocorrencia.desc()).all()
    except Exception:
        logger_rep.error(f"Erro ao listar ocorrências | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar ocorrências. Tente novamente."
        )


@roteador.get("/ocorrencias/abertas", response_model=List[OcorrenciaResposta])
def listar_ocorrencias_abertas(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        return banco.query(Ocorrencia).join(Animal).filter(
            Animal.usuario_id == usuario.id,
            Ocorrencia.data_resolucao.is_(None)
        ).order_by(Ocorrencia.data_ocorrencia.desc()).all()
    except Exception:
        logger_rep.error(f"Erro ao listar ocorrências abertas | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar ocorrências abertas. Tente novamente."
        )


@roteador.get("/ocorrencias/animal/{animal_id}", response_model=List[OcorrenciaResposta])
def listar_ocorrencias_por_animal(
    animal_id: int,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if animal_id <= 0:
        raise HTTPException(status_code=400, detail="ID do animal inválido.")
    try:
        animal = banco.query(Animal).filter(
            Animal.id == animal_id,
            Animal.usuario_id == usuario.id
        ).first()
        if not animal:
            raise HTTPException(status_code=404, detail="Animal não encontrado.")
        return banco.query(Ocorrencia).filter(
            Ocorrencia.animal_id == animal_id
        ).order_by(Ocorrencia.data_ocorrencia.desc()).all()
    except HTTPException:
        raise
    except Exception:
        logger_rep.error(f"Erro ao listar ocorrências do animal {animal_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar ocorrências do animal. Tente novamente."
        )


@roteador.post("/ocorrencias/", response_model=OcorrenciaResposta)
def registrar_ocorrencia(
    dados: OcorrenciaCriar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        animal = banco.query(Animal).filter(
            Animal.id == dados.animal_id,
            Animal.usuario_id == usuario.id
        ).first()
        if not animal:
            raise HTTPException(status_code=404, detail="Animal não encontrado.")
        if dados.data_ocorrencia > date.today():
            raise HTTPException(
                status_code=400,
                detail="Data da ocorrência não pode ser no futuro."
            )
        nova_ocorrencia = Ocorrencia(**dados.model_dump())
        banco.add(nova_ocorrencia)
        banco.commit()
        banco.refresh(nova_ocorrencia)
        logger_rep.info(f"Ocorrência registrada | animal: {dados.animal_id} | usuário: {usuario.id}")
        return nova_ocorrencia
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        logger_rep.error(f"Erro ao registrar ocorrência | animal: {dados.animal_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao registrar ocorrência. Tente novamente."
        )


@roteador.put("/ocorrencias/{ocorrencia_id}", response_model=OcorrenciaResposta)
def atualizar_ocorrencia(
    ocorrencia_id: int,
    dados: OcorrenciaAtualizar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if ocorrencia_id <= 0:
        raise HTTPException(status_code=400, detail="ID da ocorrência inválido.")
    try:
        ocorrencia = banco.query(Ocorrencia).join(Animal).filter(
            Ocorrencia.id == ocorrencia_id,
            Animal.usuario_id == usuario.id
        ).first()
        if not ocorrencia:
            raise HTTPException(status_code=404, detail="Ocorrência não encontrada.")
        for campo, valor in dados.model_dump(exclude_unset=True).items():
            setattr(ocorrencia, campo, valor)
        banco.commit()
        banco.refresh(ocorrencia)
        logger_rep.info(f"Ocorrência atualizada | id: {ocorrencia_id} | usuário: {usuario.id}")
        return ocorrencia
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        logger_rep.error(f"Erro ao atualizar ocorrência | id: {ocorrencia_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar ocorrência. Tente novamente."
        )


@roteador.delete("/ocorrencias/{ocorrencia_id}")
def deletar_ocorrencia(
    ocorrencia_id: int,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if ocorrencia_id <= 0:
        raise HTTPException(status_code=400, detail="ID da ocorrência inválido.")
    try:
        ocorrencia = banco.query(Ocorrencia).join(Animal).filter(
            Ocorrencia.id == ocorrencia_id,
            Animal.usuario_id == usuario.id
        ).first()
        if not ocorrencia:
            raise HTTPException(status_code=404, detail="Ocorrência não encontrada.")
        banco.delete(ocorrencia)
        banco.commit()
        logger_rep.info(f"Ocorrência deletada | id: {ocorrencia_id} | usuário: {usuario.id}")
        return {"mensagem": "Ocorrência removida com sucesso."}
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        logger_rep.error(f"Erro ao deletar ocorrência | id: {ocorrencia_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao remover ocorrência. Tente novamente."
        )