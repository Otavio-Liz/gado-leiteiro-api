from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.database import pegar_banco
from app.models.producao import Producao, PrecoLeite
from app.models.animal import Animal
from app.models.parto import Parto
from app.models.medicamento import AplicacaoMedicamento
from app.schemas.producoes import (
    ProducaoCriar, ProducaoResposta, ProducaoAtualizar,
    PrecoLeiteCriar, PrecoLeiteResposta, PrecoLeiteAtualizar,
    ProducaoRebanhoRelatorio, ProducaoAnimalRelatorio
)
from app.auth import pegar_usuario_atual
from app.models.usuario import Usuario
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional

roteador = APIRouter(
    prefix="/producoes",
    tags=["Produções"]
)


def pegar_preco_vigente(usuario_id: int, data_ref: date, banco: Session) -> Optional[PrecoLeite]:
    return banco.query(PrecoLeite).filter(
        PrecoLeite.usuario_id == usuario_id,
        PrecoLeite.vigente_a_partir <= data_ref
    ).order_by(PrecoLeite.vigente_a_partir.desc()).first()


def verificar_carencia(animal_id: int, data: date, banco: Session):
    """
    Verifica se o animal está em período de carência (parto ou medicamento).
    Retorna (esta_em_carencia, motivo).
    """
    # Verificar carência pós-parto (colostro)
    parto_carencia = banco.query(Parto).filter(
        Parto.animal_id == animal_id,
        Parto.carencia_encerra_em >= data,
        Parto.data_parto <= data
    ).first()
    if parto_carencia:
        return True, f"Carência pós-parto (colostro) até {parto_carencia.carencia_encerra_em}"

    # Verificar carência de medicamento
    med_carencia = banco.query(AplicacaoMedicamento).filter(
        AplicacaoMedicamento.animal_id == animal_id,
        AplicacaoMedicamento.carencia_encerra_em >= data,
        AplicacaoMedicamento.data_aplicacao <= data
    ).first()
    if med_carencia:
        return True, f"Carência medicamento '{med_carencia.medicamento.nome}' até {med_carencia.carencia_encerra_em}"

    return False, None


# ─── Produção ─────────────────────────────────────────────────────────────────

@roteador.get("/", response_model=List[ProducaoResposta])
def listar_producoes(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    return banco.query(Producao).join(Animal).filter(
        Animal.usuario_id == usuario.id
    ).order_by(Producao.data.desc()).all()


@roteador.get("/animal/{animal_id}", response_model=List[ProducaoResposta])
def listar_producoes_por_animal(
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
    return banco.query(Producao).filter(
        Producao.animal_id == animal_id
    ).order_by(Producao.data.desc()).all()


@roteador.post("/", response_model=ProducaoResposta)
def registrar_producao(
    producao: ProducaoCriar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    # Verificar animal
    animal = banco.query(Animal).filter(
        Animal.id == producao.animal_id,
        Animal.usuario_id == usuario.id
    ).first()
    if not animal:
        raise HTTPException(status_code=404, detail="Animal não encontrado")
    if animal.status != "ativo":
        raise HTTPException(status_code=400, detail=f"Animal está '{animal.status}' e não pode ter produções registradas")
    if animal.sexo == "M":
        raise HTTPException(status_code=400, detail="Machos não produzem leite")
    if animal.status_reprodutivo != "em_lactacao":
        raise HTTPException(status_code=400, detail="Animal não está em lactação. Registre um parto primeiro")

    # Data não pode ser no futuro
    if producao.data > date.today():
        raise HTTPException(status_code=400, detail="Data de produção não pode ser no futuro")

    # Verificar duplicidade (um registro por animal por dia)
    existente = banco.query(Producao).filter(
        Producao.animal_id == producao.animal_id,
        Producao.data == producao.data
    ).first()
    if existente:
        raise HTTPException(status_code=400, detail="Já existe produção registrada para este animal nesta data")

    # Verificar carência automática
    em_carencia, motivo = verificar_carencia(producao.animal_id, producao.data, banco)

    dados = producao.model_dump()
    if em_carencia:
        dados["status"] = "descartado"
        dados["motivo_descarte"] = motivo

    nova_producao = Producao(**dados)
    banco.add(nova_producao)
    banco.commit()
    banco.refresh(nova_producao)
    return nova_producao


@roteador.put("/{producao_id}", response_model=ProducaoResposta)
def atualizar_producao(
    producao_id: int,
    dados: ProducaoAtualizar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    producao = banco.query(Producao).join(Animal).filter(
        Producao.id == producao_id,
        Animal.usuario_id == usuario.id
    ).first()
    if not producao:
        raise HTTPException(status_code=404, detail="Produção não encontrada")
    if dados.quantidade_litros is not None and dados.quantidade_litros <= 0:
        raise HTTPException(status_code=400, detail="Quantidade de litros deve ser maior que zero")
    if dados.data is not None and dados.data > date.today():
        raise HTTPException(status_code=400, detail="Data de produção não pode ser no futuro")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(producao, campo, valor)
    banco.commit()
    banco.refresh(producao)
    return producao


@roteador.delete("/{producao_id}")
def deletar_producao(
    producao_id: int,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    producao = banco.query(Producao).join(Animal).filter(
        Producao.id == producao_id,
        Animal.usuario_id == usuario.id
    ).first()
    if not producao:
        raise HTTPException(status_code=404, detail="Produção não encontrada")
    banco.delete(producao)
    banco.commit()
    return {"mensagem": "Produção removida com sucesso"}


# ─── Relatórios ───────────────────────────────────────────────────────────────

@roteador.get("/relatorio/diario")
def relatorio_diario(
    data_ref: date = None,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if not data_ref:
        data_ref = date.today()
    return _gerar_relatorio(usuario.id, data_ref, data_ref, banco)


@roteador.get("/relatorio/semanal")
def relatorio_semanal(
    data_ref: date = None,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if not data_ref:
        data_ref = date.today()
    inicio = data_ref - timedelta(days=data_ref.weekday())
    fim = inicio + timedelta(days=6)
    return _gerar_relatorio(usuario.id, inicio, fim, banco)


@roteador.get("/relatorio/mensal")
def relatorio_mensal(
    ano: int = None,
    mes: int = None,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    hoje = date.today()
    if not ano:
        ano = hoje.year
    if not mes:
        mes = hoje.month
    if mes < 1 or mes > 12:
        raise HTTPException(status_code=400, detail="Mês deve ser entre 1 e 12")
    inicio = date(ano, mes, 1)
    if mes == 12:
        fim = date(ano + 1, 1, 1) - timedelta(days=1)
    else:
        fim = date(ano, mes + 1, 1) - timedelta(days=1)
    return _gerar_relatorio(usuario.id, inicio, fim, banco)


def _gerar_relatorio(usuario_id: int, inicio: date, fim: date, banco: Session):
    """Gera relatório de produção consolidado por período."""
    preco = pegar_preco_vigente(usuario_id, fim, banco)
    preco_litro = preco.preco_litro if preco else Decimal("0")

    animais = banco.query(Animal).filter(
        Animal.usuario_id == usuario_id,
        Animal.status == "ativo",
        Animal.sexo == "F"
    ).all()

    animais_relatorio = []
    total_geral = Decimal("0")
    total_aproveitado_geral = Decimal("0")
    total_descartado_geral = Decimal("0")

    for animal in animais:
        producoes = banco.query(Producao).filter(
            Producao.animal_id == animal.id,
            Producao.data.between(inicio, fim)
        ).all()

        if not producoes:
            continue

        total = sum(p.quantidade_litros for p in producoes)
        aproveitado = sum(p.quantidade_litros for p in producoes if p.status == "aproveitado")
        descartado = sum(p.quantidade_litros for p in producoes if p.status == "descartado")
        dias = (fim - inicio).days + 1
        media = total / dias if dias > 0 else Decimal("0")
        valor = aproveitado * preco_litro

        animais_relatorio.append({
            "animal_id": animal.id,
            "animal_nome": animal.nome,
            "animal_brinco": animal.brinco,
            "total_litros": round(total, 2),
            "total_litros_aproveitados": round(aproveitado, 2),
            "total_litros_descartados": round(descartado, 2),
            "media_diaria": round(media, 2),
            "valor_total": round(valor, 2),
            "preco_litro_vigente": preco_litro
        })

        total_geral += total
        total_aproveitado_geral += aproveitado
        total_descartado_geral += descartado

    dias_periodo = (fim - inicio).days + 1

    return {
        "periodo_inicio": inicio,
        "periodo_fim": fim,
        "total_animais": len(animais_relatorio),
        "total_litros": round(total_geral, 2),
        "total_litros_aproveitados": round(total_aproveitado_geral, 2),
        "total_litros_descartados": round(total_descartado_geral, 2),
        "media_diaria_rebanho": round(total_geral / dias_periodo, 2) if dias_periodo > 0 else 0,
        "valor_total": round(total_aproveitado_geral * preco_litro, 2),
        "preco_litro_vigente": preco_litro,
        "animais": animais_relatorio
    }


# ─── Preço do Leite ──────────────────────────────────────────────────────────

@roteador.get("/preco-leite/", response_model=List[PrecoLeiteResposta])
def listar_precos(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    return banco.query(PrecoLeite).filter(
        PrecoLeite.usuario_id == usuario.id
    ).order_by(PrecoLeite.vigente_a_partir.desc()).all()


@roteador.get("/preco-leite/vigente", response_model=PrecoLeiteResposta)
def preco_vigente(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    preco = pegar_preco_vigente(usuario.id, date.today(), banco)
    if not preco:
        raise HTTPException(status_code=404, detail="Nenhum preço cadastrado. Cadastre o preço do leite primeiro")
    return preco


@roteador.post("/preco-leite/", response_model=PrecoLeiteResposta)
def cadastrar_preco(
    dados: PrecoLeiteCriar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    novo_preco = PrecoLeite(**dados.model_dump(), usuario_id=usuario.id)
    banco.add(novo_preco)
    banco.commit()
    banco.refresh(novo_preco)
    return novo_preco


@roteador.put("/preco-leite/{preco_id}", response_model=PrecoLeiteResposta)
def atualizar_preco(
    preco_id: int,
    dados: PrecoLeiteAtualizar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    preco = banco.query(PrecoLeite).filter(
        PrecoLeite.id == preco_id,
        PrecoLeite.usuario_id == usuario.id
    ).first()
    if not preco:
        raise HTTPException(status_code=404, detail="Preço não encontrado")
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(preco, campo, valor)
    banco.commit()
    banco.refresh(preco)
    return preco