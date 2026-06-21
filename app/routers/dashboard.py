from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import pegar_banco
from app.models.animal import Animal
from app.models.vacina import Vacina
from app.models.medicamento import Medicamento, AplicacaoMedicamento
from app.models.parto import Parto
from app.models.producao import Producao, PrecoLeite
from app.models.reproducao import Ocorrencia
from app.auth import pegar_usuario_atual
from app.models.usuario import Usuario
from app.logger import logger_dash
from datetime import date, timedelta
from decimal import Decimal

roteador = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard e Alertas"]
)


@roteador.get("/alertas")
def alertas_consolidados(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        hoje = date.today()
        limite_30 = hoje + timedelta(days=30)

        vacinas = banco.query(Vacina).join(Animal).filter(
            Animal.usuario_id == usuario.id,
            Vacina.proxima_dose.between(hoje, limite_30)
        ).all()

        alertas_vacinas = [
            {
                "animal_id": v.animal_id,
                "animal_nome": v.animal.nome,
                "animal_brinco": v.animal.brinco,
                "vacina": v.nome_vacina,
                "proxima_dose": v.proxima_dose,
                "dias_restantes": (v.proxima_dose - hoje).days
            }
            for v in vacinas
        ]

        medicamentos_baixos = banco.query(Medicamento).filter(
            Medicamento.usuario_id == usuario.id,
            Medicamento.estoque_atual <= Medicamento.estoque_minimo
        ).all()

        alertas_estoque = [
            {
                "medicamento_id": m.id,
                "nome": m.nome,
                "estoque_atual": m.estoque_atual,
                "estoque_minimo": m.estoque_minimo,
                "unidade": m.unidade
            }
            for m in medicamentos_baixos
        ]

        animais_parto = banco.query(Animal).filter(
            Animal.usuario_id == usuario.id,
            Animal.status == "ativo",
            Animal.data_prevista_parto.between(hoje, limite_30)
        ).all()

        alertas_partos = [
            {
                "animal_id": a.id,
                "animal_nome": a.nome,
                "animal_brinco": a.brinco,
                "data_prevista_parto": a.data_prevista_parto,
                "dias_restantes": (a.data_prevista_parto - hoje).days
            }
            for a in animais_parto
        ]

        aplicacoes = banco.query(AplicacaoMedicamento).join(Animal).filter(
            Animal.usuario_id == usuario.id,
            AplicacaoMedicamento.carencia_encerra_em >= hoje
        ).all()

        alertas_carencia_med = [
            {
                "animal_id": a.animal_id,
                "animal_nome": a.animal.nome,
                "animal_brinco": a.animal.brinco,
                "medicamento": a.medicamento.nome,
                "carencia_encerra_em": a.carencia_encerra_em,
                "dias_restantes": (a.carencia_encerra_em - hoje).days
            }
            for a in aplicacoes
        ]

        partos_carencia = banco.query(Parto).join(Animal).filter(
            Animal.usuario_id == usuario.id,
            Parto.carencia_encerra_em >= hoje
        ).all()

        alertas_carencia_parto = [
            {
                "animal_id": p.animal_id,
                "animal_nome": p.animal.nome,
                "animal_brinco": p.animal.brinco,
                "data_parto": p.data_parto,
                "carencia_encerra_em": p.carencia_encerra_em,
                "dias_restantes": (p.carencia_encerra_em - hoje).days
            }
            for p in partos_carencia
        ]

        ocorrencias = banco.query(Ocorrencia).join(Animal).filter(
            Animal.usuario_id == usuario.id,
            Ocorrencia.data_resolucao.is_(None)
        ).all()

        alertas_ocorrencias = [
            {
                "ocorrencia_id": o.id,
                "animal_id": o.animal_id,
                "animal_nome": o.animal.nome,
                "animal_brinco": o.animal.brinco,
                "tipo": o.tipo,
                "descricao": o.descricao,
                "data_ocorrencia": o.data_ocorrencia,
                "dias_aberta": (hoje - o.data_ocorrencia).days
            }
            for o in ocorrencias
        ]

        logger_dash.info(f"Alertas consultados | usuário: {usuario.id}")

        return {
            "data_consulta": hoje,
            "total_alertas": (
                len(alertas_vacinas) +
                len(alertas_estoque) +
                len(alertas_partos) +
                len(alertas_carencia_med) +
                len(alertas_carencia_parto) +
                len(alertas_ocorrencias)
            ),
            "vacinas_vencendo": {"total": len(alertas_vacinas), "itens": alertas_vacinas},
            "estoque_baixo": {"total": len(alertas_estoque), "itens": alertas_estoque},
            "partos_proximos": {"total": len(alertas_partos), "itens": alertas_partos},
            "animais_em_carencia_medicamento": {"total": len(alertas_carencia_med), "itens": alertas_carencia_med},
            "animais_em_carencia_parto": {"total": len(alertas_carencia_parto), "itens": alertas_carencia_parto},
            "ocorrencias_abertas": {"total": len(alertas_ocorrencias), "itens": alertas_ocorrencias}
        }
    except Exception:
        logger_dash.error(f"Erro ao buscar alertas | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar alertas. Tente novamente."
        )


@roteador.get("/resumo")
def resumo_dashboard(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        hoje = date.today()
        inicio_mes = hoje.replace(day=1)

        total_animais = banco.query(Animal).filter(
            Animal.usuario_id == usuario.id,
            Animal.status == "ativo"
        ).count()

        total_femeas = banco.query(Animal).filter(
            Animal.usuario_id == usuario.id,
            Animal.status == "ativo",
            Animal.sexo == "F"
        ).count()

        total_machos = banco.query(Animal).filter(
            Animal.usuario_id == usuario.id,
            Animal.status == "ativo",
            Animal.sexo == "M"
        ).count()

        em_lactacao = banco.query(Animal).filter(
            Animal.usuario_id == usuario.id,
            Animal.status == "ativo",
            Animal.status_reprodutivo == "em_lactacao"
        ).count()

        prenhas = banco.query(Animal).filter(
            Animal.usuario_id == usuario.id,
            Animal.status == "ativo",
            Animal.status_reprodutivo == "prenha"
        ).count()

        producoes_hoje = banco.query(Producao).join(Animal).filter(
            Animal.usuario_id == usuario.id,
            Producao.data == hoje
        ).all()

        litros_hoje = sum(p.quantidade_litros for p in producoes_hoje)
        litros_hoje_aproveitados = sum(
            p.quantidade_litros for p in producoes_hoje if p.status == "aproveitado"
        )

        producoes_mes = banco.query(Producao).join(Animal).filter(
            Animal.usuario_id == usuario.id,
            Producao.data.between(inicio_mes, hoje)
        ).all()

        litros_mes = sum(p.quantidade_litros for p in producoes_mes)
        litros_mes_aproveitados = sum(
            p.quantidade_litros for p in producoes_mes if p.status == "aproveitado"
        )

        preco = banco.query(PrecoLeite).filter(
            PrecoLeite.usuario_id == usuario.id,
            PrecoLeite.vigente_a_partir <= hoje
        ).order_by(PrecoLeite.vigente_a_partir.desc()).first()

        preco_litro = preco.preco_litro if preco else Decimal("0")
        valor_hoje = litros_hoje_aproveitados * preco_litro
        valor_mes = litros_mes_aproveitados * preco_litro

        limite_30 = hoje + timedelta(days=30)

        total_alertas = (
            banco.query(Vacina).join(Animal).filter(
                Animal.usuario_id == usuario.id,
                Vacina.proxima_dose.between(hoje, limite_30)
            ).count() +
            banco.query(Medicamento).filter(
                Medicamento.usuario_id == usuario.id,
                Medicamento.estoque_atual <= Medicamento.estoque_minimo
            ).count() +
            banco.query(Animal).filter(
                Animal.usuario_id == usuario.id,
                Animal.status == "ativo",
                Animal.data_prevista_parto.between(hoje, limite_30)
            ).count() +
            banco.query(Ocorrencia).join(Animal).filter(
                Animal.usuario_id == usuario.id,
                Ocorrencia.data_resolucao.is_(None)
            ).count()
        )

        # Produção dos últimos 7 dias (incluindo hoje) — usado pelo gráfico
        # "Produção — 7 dias" do dashboard, que antes não tinha nenhum dado
        # real vindo do backend.
        producao_semanal = []
        for i in range(6, -1, -1):
            dia = hoje - timedelta(days=i)
            producoes_dia = banco.query(Producao).join(Animal).filter(
                Animal.usuario_id == usuario.id,
                Producao.data == dia
            ).all()
            total_dia = sum((p.quantidade_litros for p in producoes_dia), Decimal("0"))
            producao_semanal.append({"data": dia, "total": round(total_dia, 2)})

        logger_dash.info(f"Resumo consultado | usuário: {usuario.id}")

        return {
            "data_consulta": hoje,
            "rebanho": {
                "total_animais": total_animais,
                "femeas": total_femeas,
                "machos": total_machos,
                "em_lactacao": em_lactacao,
                "prenhas": prenhas
            },
            "producao_hoje": {
                "total_litros": round(litros_hoje, 2),
                "litros_aproveitados": round(litros_hoje_aproveitados, 2),
                "litros_descartados": round(litros_hoje - litros_hoje_aproveitados, 2),
                "valor_estimado": round(valor_hoje, 2),
                "animais_registrados": len(producoes_hoje)
            },
            "producao_mes": {
                "total_litros": round(litros_mes, 2),
                "litros_aproveitados": round(litros_mes_aproveitados, 2),
                "litros_descartados": round(litros_mes - litros_mes_aproveitados, 2),
                "valor_estimado": round(valor_mes, 2)
            },
            "producao_semanal": producao_semanal,
            "preco_litro_vigente": preco_litro,
            "total_alertas_pendentes": total_alertas
        }
    except Exception:
        logger_dash.error(f"Erro ao buscar resumo | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar resumo do dashboard. Tente novamente."
        )