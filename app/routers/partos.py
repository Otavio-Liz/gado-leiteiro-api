from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import pegar_banco
from app.models.parto import Parto
from app.models.animal import Animal
from app.schemas.partos import PartoCriar, PartoResposta, PartoAtualizar
from app.auth import pegar_usuario_atual
from app.models.usuario import Usuario
from app.logger import logger_partos
from datetime import date, timedelta
from typing import List

roteador = APIRouter(
    prefix="/partos",
    tags=["Partos"]
)


def validar_parto(dados, banco, usuario_id, parto_id=None):
    animal = banco.query(Animal).filter(
        Animal.id == dados.animal_id,
        Animal.usuario_id == usuario_id
    ).first()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal não encontrado.")
    if animal.sexo == "M":
        raise HTTPException(status_code=400, detail="Machos não podem ter partos registrados.")
    if animal.status not in ("ativo", "seco"):
        raise HTTPException(
            status_code=400,
            detail=f"Animal está '{animal.status}' e não pode ter partos registrados."
        )
    if dados.data_parto > date.today():
        raise HTTPException(status_code=400, detail="Data do parto não pode ser no futuro.")

    query = banco.query(Parto).filter(Parto.animal_id == dados.animal_id)
    if parto_id:
        query = query.filter(Parto.id != parto_id)
    partos_existentes = query.order_by(Parto.data_parto.desc()).all()

    for parto_existente in partos_existentes:
        diferenca = abs((dados.data_parto - parto_existente.data_parto).days)
        if diferenca < 270:
            raise HTTPException(
                status_code=400,
                detail=f"Intervalo mínimo entre partos é de 9 meses. Parto anterior em {parto_existente.data_parto}."
            )

    if dados.data_inicio_periodo_seco and dados.data_inicio_periodo_seco >= dados.data_parto:
        raise HTTPException(status_code=400, detail="Período seco deve ser antes do parto.")

    return animal


@roteador.get("/", response_model=List[PartoResposta])
def listar_partos(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        return banco.query(Parto).join(Animal).filter(
            Animal.usuario_id == usuario.id
        ).all()
    except Exception:
        logger_partos.error(f"Erro ao listar partos | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar partos. Tente novamente."
        )


@roteador.get("/alertas-parto-proximo", response_model=List[dict])
def alertas_parto_proximo(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        hoje = date.today()
        limite = hoje + timedelta(days=30)
        animais = banco.query(Animal).filter(
            Animal.usuario_id == usuario.id,
            Animal.status == "ativo",
            Animal.data_prevista_parto.between(hoje, limite)
        ).all()

        if not animais:
            return []

        return [
            {
                "animal_id": a.id,
                "animal_nome": a.nome,
                "animal_brinco": a.brinco,
                "data_prevista_parto": a.data_prevista_parto,
                "dias_restantes": (a.data_prevista_parto - hoje).days
            }
            for a in animais
        ]
    except Exception:
        logger_partos.error(f"Erro ao buscar alertas de parto | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar alertas de parto. Tente novamente."
        )


@roteador.get("/animal/{animal_id}", response_model=List[PartoResposta])
def listar_partos_por_animal(
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
        return banco.query(Parto).filter(
            Parto.animal_id == animal_id
        ).order_by(Parto.data_parto.desc()).all()
    except HTTPException:
        raise
    except Exception:
        logger_partos.error(f"Erro ao listar partos do animal {animal_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar partos do animal. Tente novamente."
        )


@roteador.post("/", response_model=PartoResposta)
def criar_parto(
    parto: PartoCriar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        animal = validar_parto(parto, banco, usuario.id)
        carencia_encerra_em = parto.data_parto + timedelta(days=parto.dias_carencia_colostro)

        novo_parto = Parto(
            **parto.model_dump(),
            carencia_encerra_em=carencia_encerra_em
        )
        banco.add(novo_parto)

        animal.status_reprodutivo = "em_lactacao"
        animal.data_prevista_parto = None
        animal.dias_em_lactacao = 0

        banco.commit()
        banco.refresh(novo_parto)
        logger_partos.info(f"Parto registrado | animal: {parto.animal_id} | usuário: {usuario.id}")
        return novo_parto
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        logger_partos.error(f"Erro ao registrar parto | animal: {parto.animal_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao registrar parto. Tente novamente."
        )


@roteador.put("/{parto_id}", response_model=PartoResposta)
def atualizar_parto(
    parto_id: int,
    dados: PartoAtualizar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if parto_id <= 0:
        raise HTTPException(status_code=400, detail="ID do parto inválido.")
    try:
        parto = banco.query(Parto).join(Animal).filter(
            Parto.id == parto_id,
            Animal.usuario_id == usuario.id
        ).first()
        if not parto:
            raise HTTPException(status_code=404, detail="Parto não encontrado.")

        for campo, valor in dados.model_dump(exclude_unset=True).items():
            setattr(parto, campo, valor)

        # Revalidar regras após atualização
        validar_parto(parto, banco, usuario.id, parto_id=parto_id)

        if dados.data_parto or dados.dias_carencia_colostro:
            parto.carencia_encerra_em = parto.data_parto + timedelta(days=parto.dias_carencia_colostro)

        banco.commit()
        banco.refresh(parto)
        logger_partos.info(f"Parto atualizado | id: {parto_id} | usuário: {usuario.id}")
        return parto
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        logger_partos.error(f"Erro ao atualizar parto | id: {parto_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar parto. Tente novamente."
        )


@roteador.delete("/{parto_id}")
def deletar_parto(
    parto_id: int,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if parto_id <= 0:
        raise HTTPException(status_code=400, detail="ID do parto inválido.")
    try:
        parto = banco.query(Parto).join(Animal).filter(
            Parto.id == parto_id,
            Animal.usuario_id == usuario.id
        ).first()
        if not parto:
            raise HTTPException(status_code=404, detail="Parto não encontrado.")
        banco.delete(parto)
        banco.commit()
        logger_partos.info(f"Parto deletado | id: {parto_id} | usuário: {usuario.id}")
        return {"mensagem": "Parto removido com sucesso."}
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        logger_partos.error(f"Erro ao deletar parto | id: {parto_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao remover parto. Tente novamente."
        )