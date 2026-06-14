from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import pegar_banco
from app.models.vacina import Vacina
from app.models.animal import Animal
from app.schemas.vacinas import VacinaCriar, VacinaResposta, VacinaAtualizar
from app.auth import pegar_usuario_atual
from app.models.usuario import Usuario
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
        raise HTTPException(status_code=404, detail="Animal não encontrado")
    if animal.status != "ativo":
        raise HTTPException(status_code=400, detail=f"Animal está '{animal.status}' e não pode ser vacinado")
    if dados.data_aplicacao > date.today():
        raise HTTPException(status_code=400, detail="Data de aplicação não pode ser no futuro")
    if dados.proxima_dose and dados.proxima_dose <= dados.data_aplicacao:
        raise HTTPException(status_code=400, detail="Próxima dose deve ser depois da data de aplicação")
    if dados.validade_vacina and dados.validade_vacina < dados.data_aplicacao:
        raise HTTPException(status_code=400, detail="Não é possível aplicar uma vacina vencida")

    # Verificar intervalo mínimo entre doses da mesma vacina (30 dias)
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
                    detail=f"Intervalo mínimo entre doses da mesma vacina é de 30 dias. Última aplicação em {ultima.data_aplicacao}"
                )


@roteador.get("/", response_model=List[VacinaResposta])
def listar_vacinas(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    return banco.query(Vacina).join(Animal).filter(
        Animal.usuario_id == usuario.id
    ).order_by(Vacina.data_aplicacao.desc()).all()


@roteador.get("/alertas", response_model=List[dict])
def vacinas_vencendo(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    """Retorna vacinas com próxima dose nos próximos 30 dias."""
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


@roteador.get("/animal/{animal_id}", response_model=List[VacinaResposta])
def listar_vacinas_por_animal(
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
    return banco.query(Vacina).filter(
        Vacina.animal_id == animal_id
    ).order_by(Vacina.data_aplicacao.desc()).all()


@roteador.post("/", response_model=VacinaResposta)
def criar_vacina(
    vacina: VacinaCriar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    validar_vacina(vacina, banco, usuario.id)
    nova_vacina = Vacina(**vacina.model_dump())
    banco.add(nova_vacina)
    banco.commit()
    banco.refresh(nova_vacina)
    return nova_vacina


@roteador.put("/{vacina_id}", response_model=VacinaResposta)
def atualizar_vacina(
    vacina_id: int,
    dados: VacinaAtualizar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    vacina = banco.query(Vacina).join(Animal).filter(
        Vacina.id == vacina_id,
        Animal.usuario_id == usuario.id
    ).first()
    if not vacina:
        raise HTTPException(status_code=404, detail="Vacina não encontrada")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(vacina, campo, valor)
    banco.commit()
    banco.refresh(vacina)
    return vacina


@roteador.delete("/{vacina_id}")
def deletar_vacina(
    vacina_id: int,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    vacina = banco.query(Vacina).join(Animal).filter(
        Vacina.id == vacina_id,
        Animal.usuario_id == usuario.id
    ).first()
    if not vacina:
        raise HTTPException(status_code=404, detail="Vacina não encontrada")
    banco.delete(vacina)
    banco.commit()
    return {"mensagem": "Vacina removida com sucesso"}