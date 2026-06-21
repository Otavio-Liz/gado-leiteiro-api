from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import pegar_banco
from app.models.producao import Producao, PrecoLeite
from app.models.animal import Animal
from app.models.parto import Parto
from app.models.medicamento import AplicacaoMedicamento
from app.schemas.producoes import (
    ProducaoCriar, ProducaoResposta, ProducaoAtualizar,
    PrecoLeiteCriar, PrecoLeiteResposta, PrecoLeiteAtualizar,
)
from app.auth import pegar_usuario_atual
from app.models.usuario import Usuario
from app.logger import logger_prod
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional

roteador = APIRouter(
    prefix="/producoes",
    tags=["Produções"]
)

ANO_MINIMO = 2000
ANO_MAXIMO = 2100


def pegar_preco_vigente(usuario_id: int, data_ref: date, banco: Session) -> Optional[PrecoLeite]:
    return banco.query(PrecoLeite).filter(
        PrecoLeite.usuario_id == usuario_id,
        PrecoLeite.vigente_a_partir <= data_ref
    ).order_by(PrecoLeite.vigente_a_partir.desc()).first()


def verificar_carencia(animal_id: int, data: date, banco: Session):
    parto_carencia = banco.query(Parto).filter(
        Parto.animal_id == animal_id,
        Parto.carencia_encerra_em >= data,
        Parto.data_parto <= data
    ).first()
    if parto_carencia:
        return True, f"Carência pós-parto (colostro) até {parto_carencia.carencia_encerra_em}"

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
    try:
        return banco.query(Producao).join(Animal).filter(
            Animal.usuario_id == usuario.id
        ).order_by(Producao.data.desc()).all()
    except Exception:
        logger_prod.error(f"Erro ao listar produções | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar produções. Tente novamente."
        )


@roteador.get("/animal/{animal_id}", response_model=List[ProducaoResposta])
def listar_producoes_por_animal(
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
        return banco.query(Producao).filter(
            Producao.animal_id == animal_id
        ).order_by(Producao.data.desc()).all()
    except HTTPException:
        raise
    except Exception:
        logger_prod.error(f"Erro ao listar produções do animal {animal_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar produções do animal. Tente novamente."
        )


@roteador.post("/", response_model=ProducaoResposta)
def registrar_producao(
    producao: ProducaoCriar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        animal = banco.query(Animal).filter(
            Animal.id == producao.animal_id,
            Animal.usuario_id == usuario.id
        ).first()
        if not animal:
            raise HTTPException(status_code=404, detail="Animal não encontrado.")
        if animal.status != "ativo":
            raise HTTPException(
                status_code=400,
                detail=f"Animal está '{animal.status}' e não pode ter produções registradas."
            )
        if animal.sexo == "M":
            raise HTTPException(status_code=400, detail="Machos não produzem leite.")
        if animal.status_reprodutivo != "em_lactacao":
            raise HTTPException(
                status_code=400,
                detail="Animal não está em lactação. Registre um parto primeiro."
            )
        if producao.data > date.today():
            raise HTTPException(
                status_code=400,
                detail="Data de produção não pode ser no futuro."
            )

        existente = banco.query(Producao).filter(
            Producao.animal_id == producao.animal_id,
            Producao.data == producao.data
        ).first()
        if existente:
            raise HTTPException(
                status_code=400,
                detail="Já existe produção registrada para este animal nesta data."
            )

        em_carencia, motivo = verificar_carencia(producao.animal_id, producao.data, banco)
        dados = producao.model_dump()
        if em_carencia:
            dados["status"] = "descartado"
            dados["motivo_descarte"] = motivo

        nova_producao = Producao(**dados)
        banco.add(nova_producao)
        banco.commit()
        banco.refresh(nova_producao)
        logger_prod.info(f"Produção registrada | animal: {producao.animal_id} | usuário: {usuario.id}")
        return nova_producao
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        logger_prod.error(f"Erro ao registrar produção | animal: {producao.animal_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao registrar produção. Tente novamente."
        )


@roteador.put("/{producao_id}", response_model=ProducaoResposta)
def atualizar_producao(
    producao_id: int,
    dados: ProducaoAtualizar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if producao_id <= 0:
        raise HTTPException(status_code=400, detail="ID da produção inválido.")
    try:
        producao = banco.query(Producao).join(Animal).filter(
            Producao.id == producao_id,
            Animal.usuario_id == usuario.id
        ).first()
        if not producao:
            raise HTTPException(status_code=404, detail="Produção não encontrada.")
        if dados.quantidade_litros is not None and dados.quantidade_litros <= 0:
            raise HTTPException(
                status_code=400,
                detail="Quantidade de litros deve ser maior que zero."
            )
        if dados.data is not None and dados.data > date.today():
            raise HTTPException(
                status_code=400,
                detail="Data de produção não pode ser no futuro."
            )
        for campo, valor in dados.model_dump(exclude_unset=True).items():
            setattr(producao, campo, valor)
        banco.commit()
        banco.refresh(producao)
        logger_prod.info(f"Produção atualizada | id: {producao_id} | usuário: {usuario.id}")
        return producao
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        logger_prod.error(f"Erro ao atualizar produção | id: {producao_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar produção. Tente novamente."
        )


@roteador.delete("/{producao_id}")
def deletar_producao(
    producao_id: int,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if producao_id <= 0:
        raise HTTPException(status_code=400, detail="ID da produção inválido.")
    try:
        producao = banco.query(Producao).join(Animal).filter(
            Producao.id == producao_id,
            Animal.usuario_id == usuario.id
        ).first()
        if not producao:
            raise HTTPException(status_code=404, detail="Produção não encontrada.")
        banco.delete(producao)
        banco.commit()
        logger_prod.info(f"Produção deletada | id: {producao_id} | usuário: {usuario.id}")
        return {"mensagem": "Produção removida com sucesso."}
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        logger_prod.error(f"Erro ao deletar produção | id: {producao_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao remover produção. Tente novamente."
        )


# ─── Relatórios ───────────────────────────────────────────────────────────────

@roteador.get("/relatorio/diario")
def relatorio_diario(
    data_ref: date = None,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        if not data_ref:
            data_ref = date.today()
        return _gerar_relatorio(usuario.id, data_ref, data_ref, banco)
    except HTTPException:
        raise
    except Exception:
        logger_prod.error(f"Erro ao gerar relatório diário | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao gerar relatório diário. Tente novamente."
        )


@roteador.get("/relatorio/semanal")
def relatorio_semanal(
    data_ref: date = None,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        if not data_ref:
            data_ref = date.today()
        inicio = data_ref - timedelta(days=data_ref.weekday())
        fim = inicio + timedelta(days=6)
        return _gerar_relatorio(usuario.id, inicio, fim, banco)
    except HTTPException:
        raise
    except Exception:
        logger_prod.error(f"Erro ao gerar relatório semanal | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao gerar relatório semanal. Tente novamente."
        )


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
        raise HTTPException(status_code=400, detail="Mês deve ser entre 1 e 12.")
    if ano < ANO_MINIMO or ano > ANO_MAXIMO:
        raise HTTPException(
            status_code=400,
            detail=f"Ano deve ser entre {ANO_MINIMO} e {ANO_MAXIMO}."
        )
    try:
        inicio = date(ano, mes, 1)
        fim = date(ano, mes + 1, 1) - timedelta(days=1) if mes < 12 else date(ano + 1, 1, 1) - timedelta(days=1)
        relatorio = _gerar_relatorio(usuario.id, inicio, fim, banco)
        relatorio["semanas"] = _calcular_semanas(usuario.id, inicio, fim, relatorio["preco_litro_vigente"], banco)
        return relatorio
    except HTTPException:
        raise
    except Exception:
        logger_prod.error(f"Erro ao gerar relatório mensal | {mes}/{ano} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao gerar relatório mensal. Tente novamente."
        )


def _gerar_relatorio(usuario_id: int, inicio: date, fim: date, banco: Session):
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


def _calcular_semanas(usuario_id: int, inicio: date, fim: date, preco_litro: Decimal, banco: Session):
    """
    Recorta o período em semanas de calendário (segunda a domingo, com a
    primeira e a última possivelmente parciais nas bordas do período) e soma
    a produção de cada uma. Usado pelo gráfico "Receita por Semana" do
    relatório mensal — sem isso, o frontend não tinha como montar esse gráfico.
    """
    animais_ids = [
        a.id for a in banco.query(Animal.id).filter(
            Animal.usuario_id == usuario_id,
            Animal.status == "ativo",
            Animal.sexo == "F"
        ).all()
    ]

    producoes = banco.query(Producao).filter(
        Producao.animal_id.in_(animais_ids),
        Producao.data.between(inicio, fim)
    ).all() if animais_ids else []

    semanas = []
    cursor = inicio
    while cursor <= fim:
        fim_semana = min(cursor + timedelta(days=6 - cursor.weekday()), fim)

        do_periodo = [p for p in producoes if cursor <= p.data <= fim_semana]
        total = sum((p.quantidade_litros for p in do_periodo), Decimal("0"))
        aproveitado = sum((p.quantidade_litros for p in do_periodo if p.status == "aproveitado"), Decimal("0"))

        semanas.append({
            "inicio": cursor,
            "fim": fim_semana,
            "total_litros": round(total, 2),
            "total_litros_aproveitados": round(aproveitado, 2),
            "receita": round(aproveitado * preco_litro, 2),
        })
        cursor = fim_semana + timedelta(days=1)

    return semanas


# ─── Preço do Leite ──────────────────────────────────────────────────────────

@roteador.get("/preco-leite/", response_model=List[PrecoLeiteResposta])
def listar_precos(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        return banco.query(PrecoLeite).filter(
            PrecoLeite.usuario_id == usuario.id
        ).order_by(PrecoLeite.vigente_a_partir.desc()).all()
    except Exception:
        logger_prod.error(f"Erro ao listar preços | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar preços. Tente novamente."
        )


@roteador.get("/preco-leite/vigente", response_model=PrecoLeiteResposta)
def preco_vigente(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        preco = pegar_preco_vigente(usuario.id, date.today(), banco)
        if not preco:
            raise HTTPException(
                status_code=404,
                detail="Nenhum preço cadastrado. Cadastre o preço do leite primeiro."
            )
        return preco
    except HTTPException:
        raise
    except Exception:
        logger_prod.error(f"Erro ao buscar preço vigente | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar preço vigente. Tente novamente."
        )


@roteador.post("/preco-leite/", response_model=PrecoLeiteResposta)
def cadastrar_preco(
    dados: PrecoLeiteCriar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        novo_preco = PrecoLeite(**dados.model_dump(), usuario_id=usuario.id)
        banco.add(novo_preco)
        banco.commit()
        banco.refresh(novo_preco)
        logger_prod.info(f"Preço cadastrado | R${dados.preco_litro}/L | usuário: {usuario.id}")
        return novo_preco
    except Exception:
        banco.rollback()
        logger_prod.error(f"Erro ao cadastrar preço | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao cadastrar preço. Tente novamente."
        )


@roteador.put("/preco-leite/{preco_id}", response_model=PrecoLeiteResposta)
def atualizar_preco(
    preco_id: int,
    dados: PrecoLeiteAtualizar,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if preco_id <= 0:
        raise HTTPException(status_code=400, detail="ID do preço inválido.")
    try:
        preco = banco.query(PrecoLeite).filter(
            PrecoLeite.id == preco_id,
            PrecoLeite.usuario_id == usuario.id
        ).first()
        if not preco:
            raise HTTPException(status_code=404, detail="Preço não encontrado.")
        for campo, valor in dados.model_dump(exclude_unset=True).items():
            setattr(preco, campo, valor)
        banco.commit()
        banco.refresh(preco)
        logger_prod.info(f"Preço atualizado | id: {preco_id} | usuário: {usuario.id}")
        return preco
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        logger_prod.error(f"Erro ao atualizar preço | id: {preco_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar preço. Tente novamente."
        )


@roteador.delete("/preco-leite/{preco_id}")
def deletar_preco(
    preco_id: int,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    if preco_id <= 0:
        raise HTTPException(status_code=400, detail="ID do preço inválido.")
    try:
        preco = banco.query(PrecoLeite).filter(
            PrecoLeite.id == preco_id,
            PrecoLeite.usuario_id == usuario.id
        ).first()
        if not preco:
            raise HTTPException(status_code=404, detail="Preço não encontrado.")
        banco.delete(preco)
        banco.commit()
        logger_prod.info(f"Preço deletado | id: {preco_id} | usuário: {usuario.id}")
        return {"mensagem": "Preço removido com sucesso."}
    except HTTPException:
        raise
    except Exception:
        banco.rollback()
        logger_prod.error(f"Erro ao deletar preço | id: {preco_id} | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao deletar preço. Tente novamente."
        )