from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import pegar_banco
from app.models.vacina import Vacina
from app.models.animal import Animal
from app.schemas.vacinas import VacinaCriar, VacinaResposta, VacinaAtualizar
from app.auth import pegar_usuario_atual
from app.models.usuario import Usuario
from app.logger import logger_vacinas
from datetime import date, timedelta
from typing import List

roteador = APIRouter(
    prefix="/vacinas",
    tags=["Vacinas"]
)


def validar_vacina(dados, banco, usuario_id, vacina_id=None):
    animal = banco.query(Animal).filter(
        Animal.id == dados.animal_id,
        Animal.usuario_id == usuario_id
    ).first()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal não encontrado.")
    if animal.status != "ativo":
        raise HTTPException(
            status_code=400,
            detail=f"Animal está '{animal.status}' e não pode ser vacinado."
        )
    if dados.data_aplicacao > date.today():
        raise HTTPException(
            status_code=400,
            detail="Data de aplicação não pode ser no futuro."
        )
    if dados.proxima_dose and dados.proxima_dose <= dados.data_aplicacao:
        raise HTTPException(
            status_code=400,
            detail="Próxima dose deve ser depois da data de aplicação."
        )
    if dados.validade_vacina and dados.validade_vacina < dados.data_aplicacao:
        raise HTTPException(
            status_code=400,
            detail="Não é possível aplicar uma vacina vencida."
        )

    if dados.nome_vacina:
        query = banco.query(Vacina).filter(
            Vacina.animal_id == dados.animal_id,
            Vacina.nome_vacina == dados.nome_vacina
        )
        if vacina_id:
            query = query.filter(Vacina.id != vacina_id)
        ultima = query.order_by(Vacina.data_aplicacao.desc()).first()
        if ultima:
            diferenca = abs((dados.data_aplicacao - ultima.data_aplicacao).days)
            if diferenca < 30:
                raise HTTPException(
                    status_code=400,
                    detail=f"Intervalo mínimo entre doses é de 30 dias. Última aplicação em {ultima.data_aplicacao}."
                )


@roteador.get("/", response_model=List[VacinaResposta])
def listar_vacinas(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        return banco.query(Vacina).join(Animal).filter(
            Animal.usuario_id == usuario.id
        ).order_by(Vacina.data_aplicacao.desc()).all()
    except Exception:
        logger_vacinas.error(f"Erro ao listar vacinas | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar vacinas. Tente novamente."
        )


@roteador.get("/alertas", response_model=List[dict])
def vacinas_vencendo(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        hoje = date.today()
        limite = hoje + timedelta(days=30)
        vacinas = banco.query(Vacina).join(Animal).filter(
            Animal.usuario_id == usuario.id,
            Vacina.proxima_dose.between(hoje, limite)
        ).all()

        return [
            {
                "vacina_id": v.id,
                "animal_id": v.animal_id,
                "animal_nome": v.animal.nome,
                "animal_brinco": v.animal.brinco,
                "nome_vacina": v.nome_vacina,
                "proxima_dose": v.proxima_dose,
                "dias_restantes": (v.proxima_dose - hoje).days
            }
            for v in vacinas
        ]
    except Exception:
        logger_vacinas.error(f"Erro ao buscar alertas | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar alertas de vacinas. Tente novamente."
        )


@roteador.get("/animal/{animal_id}", response_model=List[VacinaResposta])
def listar_vacinas_por_animal(
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
        return banco.query(Vacina).filter(
            Vacina.animal_id == animal_id
        ).order_by(Vacina.data_aplicacao.desc()).all()
    except HTTPException:
        raise
    except Exception:
        logger_vacinas.error(f"Erro ao listar vacinas do animal {animal_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar vacinas do animal. Tente novamente."
        )


@roteador.post("/", response_model=VacinaResposta)
def criar_vacina(
    vacina: VacinaCriar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    validar_vacina(vacina, banco, usuario.id)
    try:
        nova_vacina = Vacina(**vacina.model_dump())
        banco.add(nova_vacina)
        banco.commit()
        banco.refresh(nova_vacina)
        logger_vacinas.info(f"Vacina criada | animal: {vacina.animal_id} | usuário: {usuario.id}")
        return nova_vacina
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        logger_vacinas.error(f"Erro ao criar vacina | animal: {vacina.animal_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao registrar vacina. Tente novamente."
        )


@roteador.put("/{vacina_id}", response_model=VacinaResposta)
def atualizar_vacina(
    vacina_id: int,
    dados: VacinaAtualizar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if vacina_id <= 0:
        raise HTTPException(status_code=400, detail="ID da vacina inválido.")
    try:
        vacina = banco.query(Vacina).join(Animal).filter(
            Vacina.id == vacina_id,
            Animal.usuario_id == usuario.id
        ).first()
        if not vacina:
            raise HTTPException(status_code=404, detail="Vacina não encontrada.")

        dados_atualizados = dados.model_dump(exclude_unset=True)
        for campo, valor in dados_atualizados.items():
            setattr(vacina, campo, valor)

        # Revalidar regras após atualização
        validar_vacina(vacina, banco, usuario.id, vacina_id=vacina_id)

        banco.commit()
        banco.refresh(vacina)
        logger_vacinas.info(f"Vacina atualizada | id: {vacina_id} | usuário: {usuario.id}")
        return vacina
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        logger_vacinas.error(f"Erro ao atualizar vacina | id: {vacina_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar vacina. Tente novamente."
        )


@roteador.delete("/{vacina_id}")
def deletar_vacina(
    vacina_id: int,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if vacina_id <= 0:
        raise HTTPException(status_code=400, detail="ID da vacina inválido.")
    try:
        vacina = banco.query(Vacina).join(Animal).filter(
            Vacina.id == vacina_id,
            Animal.usuario_id == usuario.id
        ).first()
        if not vacina:
            raise HTTPException(status_code=404, detail="Vacina não encontrada.")
        banco.delete(vacina)
        banco.commit()
        logger_vacinas.info(f"Vacina deletada | id: {vacina_id} | usuário: {usuario.id}")
        return {"mensagem": "Vacina removida com sucesso."}
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        logger_vacinas.error(f"Erro ao deletar vacina | id: {vacina_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao remover vacina. Tente novamente."
        )