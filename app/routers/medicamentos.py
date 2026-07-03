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
from decimal import Decimal
from typing import List

roteador = APIRouter(
    prefix="/medicamentos",
    tags=["Medicamentos"]
)


def montar_resposta_aplicacao(aplicacao: AplicacaoMedicamento) -> AplicacaoMedicamentoResposta:
    """Preenche animal_nome e medicamento_nome a partir dos relacionamentos,
    já que esses campos não existem na tabela e não vêm automaticamente
    do from_attributes."""
    resposta = AplicacaoMedicamentoResposta.model_validate(aplicacao)
    resposta.animal_nome = aplicacao.animal.nome if aplicacao.animal else None
    resposta.medicamento_nome = aplicacao.medicamento.nome if aplicacao.medicamento else None
    return resposta


def calcular_carencia(data_aplicacao: date, dias_carencia: int) -> date:
    """Calcula a data de encerramento da carência a partir da data de
    aplicação e dos dias de carência do medicamento (snapshot no momento
    da aplicação). Centralizado aqui para ser reaproveitado tanto no
    registro quanto na edição de aplicações."""
    return data_aplicacao + timedelta(days=dias_carencia)


def ajustar_estoque_diferenca(medicamento: Medicamento, dose_antiga: Decimal, dose_nova: Decimal) -> None:
    """Ajusta o estoque do medicamento pela diferença entre uma dose antiga
    e uma nova. Se a dose aumentou, debita a diferença do estoque (e
    valida se há saldo suficiente); se diminuiu, devolve a diferença.
    Reaproveitável para qualquer fluxo futuro que precise corrigir estoque
    por diferença de quantidade, não só na edição de aplicação."""
    diferenca = dose_nova - dose_antiga
    if diferenca > 0 and medicamento.estoque_atual < diferenca:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Estoque insuficiente para aumentar a dose. "
                f"Disponível: {medicamento.estoque_atual} {medicamento.unidade}, "
                f"necessário adicional: {diferenca} {medicamento.unidade}."
            )
        )
    medicamento.estoque_atual -= diferenca


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

        # Conta só aplicações de animais do próprio usuário — sem o join
        # com Animal, aplicações de outro usuário que referenciem o mesmo
        # medicamento_id contariam no bloqueio, o que é incorreto.
        aplicacoes = banco.query(AplicacaoMedicamento).join(Animal).filter(
            AplicacaoMedicamento.medicamento_id == medicamento_id,
            Animal.usuario_id == usuario.id
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
        aplicacoes = banco.query(AplicacaoMedicamento).join(Animal).filter(
            Animal.usuario_id == usuario.id
        ).all()
        return [montar_resposta_aplicacao(a) for a in aplicacoes]
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
        aplicacoes = banco.query(AplicacaoMedicamento).filter(
            AplicacaoMedicamento.animal_id == animal_id
        ).order_by(AplicacaoMedicamento.data_aplicacao.desc()).all()
        return [montar_resposta_aplicacao(a) for a in aplicacoes]
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
                "id": a.id,
                "animal_id": a.animal_id,
                "animal_nome": a.animal.nome if a.animal else None,
                "medicamento_nome": a.medicamento.nome if a.medicamento else None,
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

        dias_carencia = medicamento.dias_carencia
        carencia_encerra_em = calcular_carencia(dados.data_aplicacao, dias_carencia)

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
        return montar_resposta_aplicacao(nova_aplicacao)
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


@roteador.put("/aplicacoes/{aplicacao_id}", response_model=AplicacaoMedicamentoResposta)
def atualizar_aplicacao(
    aplicacao_id: int,
    dados: AplicacaoMedicamentoAtualizar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    """
    Edita uma aplicação existente. O schema AplicacaoMedicamentoAtualizar
    não permite trocar animal_id nem medicamento_id — só dose, data e
    campos descritivos. Por isso o ajuste de estoque só precisa lidar
    com diferença de dose no MESMO medicamento (ver ajustar_estoque_diferenca).

    Decisão assumida: não bloqueia edição se o animal estiver inativo,
    pois trata-se de correção de um registro histórico, não de uma nova
    aplicação. Avise se preferir bloquear como no POST.
    """
    if aplicacao_id <= 0:
        raise HTTPException(status_code=400, detail="ID da aplicação inválido.")
    try:
        aplicacao = banco.query(AplicacaoMedicamento).join(Animal).filter(
            AplicacaoMedicamento.id == aplicacao_id,
            Animal.usuario_id == usuario.id
        ).first()
        if not aplicacao:
            raise HTTPException(status_code=404, detail="Aplicação não encontrada.")

        medicamento = banco.query(Medicamento).filter(
            Medicamento.id == aplicacao.medicamento_id,
            Medicamento.usuario_id == usuario.id
        ).first()
        if not medicamento:
            raise HTTPException(status_code=404, detail="Medicamento vinculado não encontrado.")

        dados_alterados = dados.model_dump(exclude_unset=True)

        if "dose_aplicada" in dados_alterados:
            ajustar_estoque_diferenca(
                medicamento,
                aplicacao.dose_aplicada,
                dados_alterados["dose_aplicada"]
            )
            aplicacao.dose_aplicada = dados_alterados["dose_aplicada"]

        if "data_aplicacao" in dados_alterados:
            aplicacao.data_aplicacao = dados_alterados["data_aplicacao"]
            # dias_carencia é o snapshot tirado na criação da aplicação;
            # mantemos esse valor e só recalculamos a data final de carência.
            aplicacao.carencia_encerra_em = calcular_carencia(
                aplicacao.data_aplicacao, aplicacao.dias_carencia
            )

        for campo in ("motivo", "responsavel", "observacao"):
            if campo in dados_alterados:
                setattr(aplicacao, campo, dados_alterados[campo])

        banco.commit()
        banco.refresh(aplicacao)
        logger_med.info(f"Aplicação atualizada | id: {aplicacao_id} | usuário: {usuario.id}")
        return montar_resposta_aplicacao(aplicacao)
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        logger_med.error(f"Erro ao atualizar aplicação | id: {aplicacao_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar aplicação de medicamento. Tente novamente."
        )


@roteador.delete("/aplicacoes/{aplicacao_id}")
def deletar_aplicacao(
    aplicacao_id: int,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    """
    Remove uma aplicação e devolve a dose ao estoque do medicamento.
    Reaproveita ajustar_estoque_diferenca com dose_nova=0, que já
    trata a diferença negativa como devolução — sem lógica de estoque
    duplicada.

    Não bloqueia por animal inativo, pelo mesmo motivo do PUT: apagar
    um registro histórico incorreto não deveria depender do status
    atual do animal.
    """
    if aplicacao_id <= 0:
        raise HTTPException(status_code=400, detail="ID da aplicação inválido.")
    try:
        aplicacao = banco.query(AplicacaoMedicamento).join(Animal).filter(
            AplicacaoMedicamento.id == aplicacao_id,
            Animal.usuario_id == usuario.id
        ).first()
        if not aplicacao:
            raise HTTPException(status_code=404, detail="Aplicação não encontrada.")

        medicamento = banco.query(Medicamento).filter(
            Medicamento.id == aplicacao.medicamento_id,
            Medicamento.usuario_id == usuario.id
        ).first()
        if not medicamento:
            raise HTTPException(status_code=404, detail="Medicamento vinculado não encontrado.")

        ajustar_estoque_diferenca(medicamento, aplicacao.dose_aplicada, Decimal("0"))

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
            detail="Erro ao remover aplicação de medicamento. Tente novamente."
        )