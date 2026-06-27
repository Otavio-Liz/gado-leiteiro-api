from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc
from app.database import pegar_banco
from app.models.animal import Animal
from app.models.vacina import Vacina
from app.models.medicamento import Medicamento, AplicacaoMedicamento
from app.models.parto import Parto
from app.models.producao import Producao
from app.models.reproducao import Ocorrencia, Reproducao
from app.models.acao_diaria import AcaoDiariaConcluida
from app.utils_financeiro import construir_tabela_precos
from app.auth import pegar_usuario_atual
from app.models.usuario import Usuario
from app.logger import logger_dash
from datetime import date, timedelta
from decimal import Decimal

roteador = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard e Alertas"]
)


def idade_em_meses(nascimento, hoje):
    if not nascimento:
        return None
    return (hoje.year - nascimento.year) * 12 + (hoje.month - nascimento.month) - (1 if hoje.day < nascimento.day else 0)


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
                "foto_url": a.foto_url,
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

        # Distribuição do rebanho — classificação por precedência:
        # 1) idade < 12 meses -> bezerro/bezerra (qualquer sexo)
        # 2) 12+ meses, macho -> novilho (machos não têm conceito de parto,
        #    então não há uma regra de "graduação" — fica só por idade)
        # 3) 12+ meses, fêmea, NUNCA teve parto -> novilha, MESMO que esteja
        #    prenha do primeiro filho (regra explícita: só deixa de ser
        #    novilha quando o parto for de fato registrado no sistema)
        # 4) 12+ meses, fêmea, já teve 1+ parto -> classifica pelo status
        #    reprodutivo atual (em lactação / prenha / seca-ou-vazia)
        animais_ativos = banco.query(Animal).filter(
            Animal.usuario_id == usuario.id,
            Animal.status == "ativo"
        ).all()

        em_lactacao = 0
        prenhas = 0
        secas = 0
        novilhas = 0
        novilhos = 0
        bezerros = 0

        for a in animais_ativos:
            meses = idade_em_meses(a.nascimento, hoje)
            if meses is None:
                continue  # sem data de nascimento cadastrada — não entra em nenhuma categoria por idade

            if meses < 12:
                bezerros += 1
                continue

            if a.sexo == "M":
                novilhos += 1
                continue

            partos = a.quantidade_partos or 0
            if partos == 0:
                novilhas += 1
            elif a.status_reprodutivo == "em_lactacao":
                em_lactacao += 1
            elif a.status_reprodutivo == "prenha":
                prenhas += 1
            else:
                secas += 1  # seca oficialmente, ou vazia/em_cio/não_aplicável — sem uma 6ª categoria pra "vaca ociosa"

        distribuicao_rebanho = {
            "em_lactacao": em_lactacao,
            "prenhas": prenhas,
            "secas": secas,
            "novilhas": novilhas,
            "novilhos": novilhos,
            "bezerros": bezerros,
        }

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

        preco_em = construir_tabela_precos(usuario.id, banco)
        preco_litro = preco_em(hoje)
        valor_hoje = litros_hoje_aproveitados * preco_litro
        # valor_mes soma dia a dia, com o preço vigente em CADA dia — não
        # um preço único pro mês inteiro (bug real: se o preço mudasse no
        # meio do mês, a receita de todos os dias saía calculada com o
        # preço mais novo, mesmo os dias vendidos pelo preço antigo).
        valor_mes = sum(
            (p.quantidade_litros * preco_em(p.data) for p in producoes_mes if p.status == "aproveitado"),
            Decimal("0")
        )

        # Produção diária dos últimos 7 dias (hoje incluso) — sempre com os 7
        # dias presentes, mesmo sem produção, pra não quebrar a linha do gráfico.
        inicio_semana = hoje - timedelta(days=6)
        producoes_semana = banco.query(Producao).join(Animal).filter(
            Animal.usuario_id == usuario.id,
            Producao.data.between(inicio_semana, hoje)
        ).all()
        litros_por_dia = {}
        for p in producoes_semana:
            litros_por_dia[p.data] = litros_por_dia.get(p.data, 0) + float(p.quantidade_litros)

        producao_semanal = [
            {"data": (inicio_semana + timedelta(days=i)), "total": round(litros_por_dia.get(inicio_semana + timedelta(days=i), 0), 2)}
            for i in range(7)
        ]

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
            "distribuicao_rebanho": distribuicao_rebanho,
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

@roteador.get("/producao-por-animal")
def producao_por_animal(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    """Ranking dos animais com mais litros produzidos hoje (top 5)."""
    try:
        hoje = date.today()

        linhas = banco.query(
            Animal.id, Animal.nome, Animal.foto_url,
            sqlfunc.sum(Producao.quantidade_litros).label("litros")
        ).join(Producao, Producao.animal_id == Animal.id).filter(
            Animal.usuario_id == usuario.id,
            Producao.data == hoje,
            Producao.status == "aproveitado"
        ).group_by(Animal.id, Animal.nome, Animal.foto_url).order_by(
            sqlfunc.sum(Producao.quantidade_litros).desc()
        ).limit(5).all()

        ranking = [
            {
                "animal_id": linha.id,
                "animal_nome": linha.nome,
                "foto_url": linha.foto_url,
                "litros": round(float(linha.litros), 2),
            }
            for linha in linhas
        ]

        logger_dash.info(f"Produção por animal consultada | usuário: {usuario.id}")
        return {"data_consulta": hoje, "ranking": ranking}
    except Exception:
        logger_dash.error(f"Erro ao buscar produção por animal | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar produção por animal. Tente novamente."
        )


@roteador.get("/animais-lactacao")
def animais_em_lactacao(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    """
    Animais em lactação com dados consolidados pra tabela do Dashboard:
    produção de hoje, última ordenha registrada e última vacina aplicada.
    """
    try:
        hoje = date.today()

        animais = banco.query(Animal).filter(
            Animal.usuario_id == usuario.id,
            Animal.status == "ativo",
            Animal.status_reprodutivo == "em_lactacao"
        ).all()
        animal_ids = [a.id for a in animais]

        # 3 consultas no TOTAL (não 3 por animal) — antes, cada uma dessas
        # 3 buscas rodava dentro do loop, uma vez por animal; com 50 vacas
        # em lactação isso eram 150 idas ao banco a cada recarregamento do
        # Dashboard (a cada 60s). Agora busca tudo de uma vez e indexa em
        # dicionários por animal_id, pra olhar na memória dentro do loop.
        producoes_hoje_por_animal = {
            p.animal_id: p
            for p in banco.query(Producao).filter(
                Producao.animal_id.in_(animal_ids),
                Producao.data == hoje
            ).all()
        } if animal_ids else {}

        subq_ultima_producao = banco.query(
            Producao.animal_id, sqlfunc.max(Producao.data).label("ultima_data")
        ).filter(Producao.animal_id.in_(animal_ids)).group_by(Producao.animal_id).subquery()
        ultimas_producoes_por_animal = {
            p.animal_id: p
            for p in banco.query(Producao).join(
                subq_ultima_producao,
                (Producao.animal_id == subq_ultima_producao.c.animal_id) &
                (Producao.data == subq_ultima_producao.c.ultima_data)
            ).all()
        } if animal_ids else {}

        subq_ultima_vacina = banco.query(
            Vacina.animal_id, sqlfunc.max(Vacina.data_aplicacao).label("ultima_data")
        ).filter(Vacina.animal_id.in_(animal_ids)).group_by(Vacina.animal_id).subquery()
        ultimas_vacinas_por_animal = {
            v.animal_id: v
            for v in banco.query(Vacina).join(
                subq_ultima_vacina,
                (Vacina.animal_id == subq_ultima_vacina.c.animal_id) &
                (Vacina.data_aplicacao == subq_ultima_vacina.c.ultima_data)
            ).all()
        } if animal_ids else {}

        resultado = []
        for a in animais:
            producao_hoje = producoes_hoje_por_animal.get(a.id)
            ultima_producao = ultimas_producoes_por_animal.get(a.id)
            ultima_vacina = ultimas_vacinas_por_animal.get(a.id)

            resultado.append({
                "animal_id": a.id,
                "nome": a.nome,
                "brinco": a.brinco,
                "raca": a.raca,
                "nascimento": a.nascimento,
                "foto_url": a.foto_url,
                "producao_hoje_litros": round(float(producao_hoje.quantidade_litros), 2) if producao_hoje else None,
                "ultima_ordenha": {
                    "data": ultima_producao.data,
                    "registrada_em": ultima_producao.criado_em,
                } if ultima_producao else None,
                "ultima_vacina": {
                    "nome": ultima_vacina.nome_vacina,
                    "data_aplicacao": ultima_vacina.data_aplicacao,
                } if ultima_vacina else None,
            })

        logger_dash.info(f"Animais em lactação consultados | usuário: {usuario.id}")
        return {"data_consulta": hoje, "total": len(resultado), "animais": resultado}
    except Exception:
        logger_dash.error(f"Erro ao buscar animais em lactação | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar animais em lactação. Tente novamente."
        )


def _gerar_acoes_do_dia(banco: Session, usuario_id: int, hoje: date) -> list[dict]:
    """
    Monta a lista de ações sugeridas pra hoje, com base em dados reais
    (não é uma lista fixa) — cada ação só aparece se a condição dela for
    verdadeira. As duas últimas (produção da manhã e limpeza do tanque)
    são lembretes fixos do dia a dia, sempre presentes.
    """
    acoes = [{
        "chave": "registrar_producao_manha",
        "titulo": "Registrar produção da manhã",
        "subtitulo": "Ordenha inicial do dia",
    }]

    em_tratamento = banco.query(AplicacaoMedicamento).join(Animal).filter(
        Animal.usuario_id == usuario_id,
        AplicacaoMedicamento.carencia_encerra_em >= hoje
    ).count()
    if em_tratamento > 0:
        acoes.append({
            "chave": "verificar_tratamento",
            "titulo": "Verificar animais em tratamento",
            "subtitulo": f"{em_tratamento} animal{'is' if em_tratamento != 1 else ''}",
        })

    vacinas_hoje = banco.query(Vacina).join(Animal).filter(
        Animal.usuario_id == usuario_id,
        Vacina.proxima_dose == hoje
    ).all()
    if vacinas_hoje:
        nomes_distintos = {v.nome_vacina for v in vacinas_hoje}
        sub = f"{next(iter(nomes_distintos))} — vence hoje" if len(nomes_distintos) == 1 else f"{len(vacinas_hoje)} vacinas vencem hoje"
        acoes.append({
            "chave": "aplicar_vacina_hoje",
            "titulo": f"Aplicar vacina em {len(vacinas_hoje)} animal{'is' if len(vacinas_hoje) != 1 else ''}",
            "subtitulo": sub,
        })

    # Inseminações sem diagnóstico ainda, feitas há 25+ dias — já dá pra checar prenhez
    limite_diagnostico = hoje - timedelta(days=25)
    aguardando_diagnostico = banco.query(Reproducao).join(Animal).filter(
        Animal.usuario_id == usuario_id,
        Reproducao.resultado_diagnostico.is_(None),
        Reproducao.data_cobertura.isnot(None),
        Reproducao.data_cobertura <= limite_diagnostico
    ).count()
    if aguardando_diagnostico > 0:
        acoes.append({
            "chave": "verificar_prenhez",
            "titulo": "Verificar prenhez das inseminadas",
            "subtitulo": f"{aguardando_diagnostico} animal{'is' if aguardando_diagnostico != 1 else ''}",
        })

    acoes.append({
        "chave": "limpeza_tanque",
        "titulo": "Limpeza do tanque de leite",
        "subtitulo": "Programado",
    })

    return acoes


@roteador.get("/acoes")
def listar_acoes_do_dia(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    try:
        hoje = date.today()
        acoes = _gerar_acoes_do_dia(banco, usuario.id, hoje)

        concluidas = banco.query(AcaoDiariaConcluida.chave_acao).filter(
            AcaoDiariaConcluida.usuario_id == usuario.id,
            AcaoDiariaConcluida.data == hoje
        ).all()
        chaves_concluidas = {c.chave_acao for c in concluidas}

        for a in acoes:
            a["concluida"] = a["chave"] in chaves_concluidas

        return {"data_consulta": hoje, "acoes": acoes}
    except Exception:
        logger_dash.error(f"Erro ao buscar ações do dia | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar ações do dia. Tente novamente."
        )


@roteador.put("/acoes/{chave_acao}/alternar")
def alternar_acao_do_dia(
    chave_acao: str,
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    """Marca/desmarca uma ação do dia. Idempotente — chamar de novo desfaz."""
    try:
        hoje = date.today()
        existente = banco.query(AcaoDiariaConcluida).filter(
            AcaoDiariaConcluida.usuario_id == usuario.id,
            AcaoDiariaConcluida.data == hoje,
            AcaoDiariaConcluida.chave_acao == chave_acao
        ).first()

        if existente:
            banco.delete(existente)
            banco.commit()
            return {"chave_acao": chave_acao, "concluida": False}

        nova = AcaoDiariaConcluida(usuario_id=usuario.id, data=hoje, chave_acao=chave_acao)
        banco.add(nova)
        banco.commit()
        return {"chave_acao": chave_acao, "concluida": True}
    except Exception:
        banco.rollback()
        logger_dash.error(f"Erro ao alternar ação do dia | usuário: {usuario.id} | chave: {chave_acao}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao atualizar ação do dia. Tente novamente."
        )


@roteador.get("/gestantes")
def listar_gestantes(
    banco: Session = Depends(pegar_banco),
    usuario: Usuario = Depends(pegar_usuario_atual)
):
    """
    Todas as vacas/novilhas atualmente prenhas (status_reprodutivo == "prenha"),
    independente de quão longe está o parto previsto — diferente do alerta de
    "partos próximos" (que só pega os que vencem nos próximos 30 dias). Usado
    pelo widget "Próximos partos" do Dashboard.
    """
    try:
        hoje = date.today()

        prenhas = banco.query(Animal).filter(
            Animal.usuario_id == usuario.id,
            Animal.status == "ativo",
            Animal.status_reprodutivo == "prenha"
        ).order_by(Animal.data_prevista_parto.is_(None), Animal.data_prevista_parto.asc()).all()

        resultado = [
            {
                "animal_id": a.id,
                "animal_nome": a.nome,
                "animal_brinco": a.brinco,
                "foto_url": a.foto_url,
                "data_prevista_parto": a.data_prevista_parto,
                "dias_restantes": (a.data_prevista_parto - hoje).days if a.data_prevista_parto else None,
            }
            for a in prenhas
        ]

        logger_dash.info(f"Gestantes consultadas | usuário: {usuario.id}")
        return {"data_consulta": hoje, "total": len(resultado), "gestantes": resultado}
    except Exception:
        logger_dash.error(f"Erro ao buscar gestantes | usuário: {usuario.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao buscar gestantes. Tente novamente."
        )