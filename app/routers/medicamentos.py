from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import pegar_banco
from app.models.medicamento import Medicamento, AplicacaoMedicamento
from app.models.animal import Animal
from app.schemas.medicamentos import (
    MedicamentoCriar, MedicamentoResposta, MedicamentoAtualizar, MedicamentoAlerta,
    AplicacaoMedicamentoCriar, AplicacaoMedicamentoResposta, AplicacaoMedicamentoAtualizar
)
from app.auth import pegar_usuario_atual
from app.models.usuario import Usuario
from app.logger import logger_med
from datetime import date, timedelta
from typing import List

roteador = APIRouter(
    prefix="/medicamentos",
    tags=["Medicamentos"]
)


# ─── Medicamentos (Estoque) ───────────────────────────────────────────────────

@roteador.get("/", response_model=List[MedicamentoResposta])
def listar_medicamentos(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        return banco.query(Medicamento).filter(
            Medicamento.usuario_id == usuario.id
        ).all()
    except Exception:
        logger_med.error(f"Erro ao listar medicamentos | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar medicamentos. Tente novamente."
        )


@roteador.get("/alertas-estoque", response_model=List[MedicamentoAlerta])
def alertas_estoque_baixo(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        medicamentos = banco.query(Medicamento).filter(
            Medicamento.usuario_id == usuario.id,
            Medicamento.estoque_atual <= Medicamento.estoque_minimo
        ).all()
        return medicamentos or []
    except Exception:
        logger_med.error(f"Erro ao buscar alertas de estoque | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar alertas de estoque. Tente novamente."
        )


@roteador.get("/{medicamento_id}", response_model=MedicamentoResposta)
def buscar_medicamento(
    medicamento_id: int,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if medicamento_id <= 0:
        raise HTTPException(status_code=400, detail="ID do medicamento inválido.")
    try:
        medicamento = banco.query(Medicamento).filter(
            Medicamento.id == medicamento_id,
            Medicamento.usuario_id == usuario.id
        ).first()
        if not medicamento:
            raise HTTPException(status_code=404, detail="Medicamento não encontrado.")
        return medicamento
    except HTTPException:
        raise
    except Exception:
        logger_med.error(f"Erro ao buscar medicamento {medicamento_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar medicamento. Tente novamente."
        )


@roteador.post("/", response_model=MedicamentoResposta)
def criar_medicamento(
    medicamento: MedicamentoCriar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        novo = Medicamento(**medicamento.model_dump(), usuario_id=usuario.id)
        banco.add(novo)
        banco.commit()
        banco.refresh(novo)
        logger_med.info(f"Medicamento criado | {medicamento.nome} | usuário: {usuario.id}")
        return novo
    except Exception:
        banco.rollback()
        logger_med.error(f"Erro ao criar medicamento | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao cadastrar medicamento. Tente novamente."
        )


@roteador.put("/{medicamento_id}", response_model=MedicamentoResposta)
def atualizar_medicamento(
    medicamento_id: int,
    dados: MedicamentoAtualizar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if medicamento_id <= 0:
        raise HTTPException(status_code=400, detail="ID do medicamento inválido.")
    try:
        medicamento = banco.query(Medicamento).filter(
            Medicamento.id == medicamento_id,
            Medicamento.usuario_id == usuario.id
        ).first()
        if not medicamento:
            raise HTTPException(status_code=404, detail="Medicamento não encontrado.")
        for campo, valor in dados.model_dump(exclude_unset=True).items():
            setattr(medicamento, campo, valor)
        banco.commit()
        banco.refresh(medicamento)
        logger_med.info(f"Medicamento atualizado | id: {medicamento_id} | usuário: {usuario.id}")
        return medicamento
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        logger_med.error(f"Erro ao atualizar medicamento | id: {medicamento_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar medicamento. Tente novamente."
        )


@roteador.delete("/{medicamento_id}")
def deletar_medicamento(
    medicamento_id: int,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if medicamento_id <= 0:
        raise HTTPException(status_code=400, detail="ID do medicamento inválido.")
    try:
        medicamento = banco.query(Medicamento).filter(
            Medicamento.id == medicamento_id,
            Medicamento.usuario_id == usuario.id
        ).first()
        if not medicamento:
            raise HTTPException(status_code=404, detail="Medicamento não encontrado.")

        aplicacoes = banco.query(AplicacaoMedicamento).filter(
            AplicacaoMedicamento.medicamento_id == medicamento_id
        ).count()
        if aplicacoes > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Não é possível excluir. Há {aplicacoes} aplicação(ões) vinculada(s) a este medicamento."
            )

        banco.delete(medicamento)
        banco.commit()
        logger_med.info(f"Medicamento deletado | id: {medicamento_id} | usuário: {usuario.id}")
        return {"mensagem": "Medicamento removido com sucesso."}
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        logger_med.error(f"Erro ao deletar medicamento | id: {medicamento_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao remover medicamento. Tente novamente."
        )


# ─── Aplicações de Medicamento (por animal) ───────────────────────────────────

@roteador.get("/aplicacoes/todas", response_model=List[AplicacaoMedicamentoResposta])
def listar_aplicacoes(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        return banco.query(AplicacaoMedicamento).join(Animal).filter(
            Animal.usuario_id == usuario.id
        ).all()
    except Exception:
        logger_med.error(f"Erro ao listar aplicações | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar aplicações. Tente novamente."
        )


@roteador.get("/aplicacoes/animal/{animal_id}", response_model=List[AplicacaoMedicamentoResposta])
def listar_aplicacoes_por_animal(
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
        return banco.query(AplicacaoMedicamento).filter(
            AplicacaoMedicamento.animal_id == animal_id
        ).order_by(AplicacaoMedicamento.data_aplicacao.desc()).all()
    except HTTPException:
        raise
    except Exception:
        logger_med.error(f"Erro ao listar aplicações do animal {animal_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar aplicações do animal. Tente novamente."
        )


@roteador.get("/aplicacoes/em-carencia", response_model=List[dict])
def animais_em_carencia(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        hoje = date.today()
        aplicacoes = banco.query(AplicacaoMedicamento).join(Animal).filter(
            Animal.usuario_id == usuario.id,
            AplicacaoMedicamento.carencia_encerra_em >= hoje
        ).all()

        return [
            {
                "animal_id": a.animal_id,
                "animal_nome": a.animal.nome,
                "medicamento": a.medicamento.nome,
                "data_aplicacao": a.data_aplicacao,
                "carencia_encerra_em": a.carencia_encerra_em,
                "dias_restantes": (a.carencia_encerra_em - hoje).days
            }
            for a in aplicacoes
        ]
    except Exception:
        logger_med.error(f"Erro ao buscar animais em carência | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar animais em carência. Tente novamente."
        )


@roteador.post("/aplicacoes/", response_model=AplicacaoMedicamentoResposta)
def registrar_aplicacao(
    dados: AplicacaoMedicamentoCriar,
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
        if animal.status != "ativo":
            raise HTTPException(
                status_code=400,
                detail=f"Animal está '{animal.status}' e não pode receber medicamentos."
            )

        medicamento = banco.query(Medicamento).filter(
            Medicamento.id == dados.medicamento_id,
            Medicamento.usuario_id == usuario.id
        ).first()
        if not medicamento:
            raise HTTPException(status_code=404, detail="Medicamento não encontrado.")

        if medicamento.estoque_atual < dados.dose_aplicada:
            raise HTTPException(
                status_code=400,
                detail=f"Estoque insuficiente. Disponível: {medicamento.estoque_atual} {medicamento.unidade}."
            )

        if dados.data_aplicacao > date.today():
            raise HTTPException(
                status_code=400,
                detail="Data de aplicação não pode ser no futuro."
            )

        dias_carencia = medicamento.dias_carencia
        carencia_encerra_em = dados.data_aplicacao + timedelta(days=dias_carencia)

        nova_aplicacao = AplicacaoMedicamento(
            **dados.model_dump(),
            dias_carencia=dias_carencia,
            carencia_encerra_em=carencia_encerra_em
        )
        banco.add(nova_aplicacao)
        medicamento.estoque_atual -= dados.dose_aplicada

        banco.commit()
        banco.refresh(nova_aplicacao)
        logger_med.info(
            f"Aplicação registrada | animal: {dados.animal_id} | "
            f"medicamento: {dados.medicamento_id} | usuário: {usuario.id}"
        )
        return nova_aplicacao
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        logger_med.error(
            f"Erro ao registrar aplicação | animal: {dados.animal_id} | usuário: {usuario.id}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao registrar aplicação de medicamento. Tente novamente."
        )


@roteador.delete("/aplicacoes/{aplicacao_id}")
def deletar_aplicacao(
    aplicacao_id: int,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if aplicacao_id <= 0:
        raise HTTPException(status_code=400, detail="ID da aplicação inválido.")
    try:
        aplicacao = banco.query(AplicacaoMedicamento).join(Animal).filter(
            AplicacaoMedicamento.id == aplicacao_id,
            Animal.usuario_id == usuario.id
        ).first()
        if not aplicacao:
            raise HTTPException(status_code=404, detail="Aplicação não encontrada.")

        aplicacao.medicamento.estoque_atual += aplicacao.dose_aplicada
        banco.delete(aplicacao)
        banco.commit()
        logger_med.info(f"Aplicação deletada | id: {aplicacao_id} | usuário: {usuario.id}")
        return {"mensagem": "Aplicação removida e estoque restaurado com sucesso."}
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        logger_med.error(f"Erro ao deletar aplicação | id: {aplicacao_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao remover aplicação. Tente novamente."
        )