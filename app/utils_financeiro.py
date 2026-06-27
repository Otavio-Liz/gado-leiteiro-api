from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.producao import PrecoLeite


def construir_tabela_precos(usuario_id: int, banco: Session):
    """
    Busca todos os preços do leite cadastrados pelo usuário UMA VEZ (evita
    uma consulta por dia) e devolve uma função que acha o preço vigente
    pra qualquer data dentro de um período.

    Corrige um bug real: relatórios que cobrem mais de um dia (semanal,
    mensal) buscavam o preço vigente só na ÚLTIMA data do período e
    aplicavam esse único valor a todos os dias — se o preço do leite
    mudasse no meio do mês, a receita de TODOS os dias saía calculada com
    o preço errado (o mais novo, não o que estava vigente quando aquele
    litro específico foi de fato produzido/vendido).
    """
    precos = banco.query(PrecoLeite).filter(
        PrecoLeite.usuario_id == usuario_id
    ).order_by(PrecoLeite.vigente_a_partir.asc()).all()

    def preco_em(data_ref: date) -> Decimal:
        aplicavel = None
        for p in precos:
            if p.vigente_a_partir <= data_ref:
                aplicavel = p
            else:
                break
        if aplicavel:
            return aplicavel.preco_litro
        # Dia anterior ao primeiro preço já cadastrado (ex: produção
        # registrada antes de o usuário ter cadastrado preço nenhum) —
        # usa o primeiro preço conhecido em vez de zero. Zero faria a
        # receita do período sair menor do que devia, só porque o
        # cadastro de preço começou depois da produção.
        if precos:
            return precos[0].preco_litro
        return Decimal("0")  # nenhum preço cadastrado ainda, em nenhuma data

    return preco_em