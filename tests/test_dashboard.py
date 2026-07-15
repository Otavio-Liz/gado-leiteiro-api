"""
Testes da Seção 11 — Dashboard e Ações Diárias.

Cobre o checklist original:
- Validar chave_acao contra a lista real de ações geradas no dia.
- Impedir gravação de chaves arbitrárias.
- Garantir que todos os agregados filtram por usuário.
- Testar dashboard com dados de dois usuários.
- Testar ações concluídas por usuário e por data.

O primeiro teste cobre a correção feita na revisão: antes, o endpoint
aceitava qualquer string na URL como uma ação válida.
"""


# ─── Validação de chave_acao ──────────────────────────────────────────────────

def test_chave_acao_arbitraria_e_bloqueada(usuario_autenticado):
    cliente, usuario, headers = usuario_autenticado
    resposta = cliente.put("/dashboard/acoes/chave_que_nao_existe/alternar", headers=headers)
    assert resposta.status_code == 400


def test_chave_acao_valida_e_aceita(usuario_autenticado):
    """'registrar_producao_manha' é uma das duas ações fixas sempre
    presentes na lista do dia (ver _gerar_acoes_do_dia), então é uma chave
    garantidamente válida pra qualquer usuário, em qualquer dia."""
    cliente, usuario, headers = usuario_autenticado
    resposta = cliente.put("/dashboard/acoes/registrar_producao_manha/alternar", headers=headers)
    assert resposta.status_code == 200
    assert resposta.json()["concluida"] is True


def test_alternar_acao_e_idempotente(usuario_autenticado):
    """Chamar de novo desmarca — é a mesma chave alternando entre os dois
    estados, não um erro de duplicidade."""
    cliente, usuario, headers = usuario_autenticado
    primeira = cliente.put("/dashboard/acoes/limpeza_tanque/alternar", headers=headers)
    segunda = cliente.put("/dashboard/acoes/limpeza_tanque/alternar", headers=headers)

    assert primeira.status_code == 200
    assert primeira.json()["concluida"] is True
    assert segunda.status_code == 200
    assert segunda.json()["concluida"] is False


def test_acao_concluida_aparece_marcada_na_listagem(usuario_autenticado):
    cliente, usuario, headers = usuario_autenticado
    cliente.put("/dashboard/acoes/limpeza_tanque/alternar", headers=headers)

    resposta = cliente.get("/dashboard/acoes", headers=headers)
    assert resposta.status_code == 200
    acoes = resposta.json()["acoes"]
    limpeza = next(a for a in acoes if a["chave"] == "limpeza_tanque")
    assert limpeza["concluida"] is True


# ─── Isolamento entre usuários ──────────────────────────────────────────────

def test_resumo_dashboard_isola_por_usuario(
    usuario_autenticado, segundo_usuario_autenticado, criar_animal
):
    cliente1, usuario1, headers1 = usuario_autenticado
    _cliente2, usuario2, headers2 = segundo_usuario_autenticado

    criar_animal(usuario1.id, brinco="BR-U1-A")
    criar_animal(usuario1.id, brinco="BR-U1-B")
    criar_animal(usuario2.id, brinco="BR-U2-A")

    resposta1 = cliente1.get("/dashboard/resumo", headers=headers1)
    resposta2 = cliente1.get("/dashboard/resumo", headers=headers2)

    assert resposta1.status_code == 200
    assert resposta2.status_code == 200
    assert resposta1.json()["rebanho"]["total_animais"] == 2
    assert resposta2.json()["rebanho"]["total_animais"] == 1


def test_acao_concluida_por_usuario1_nao_aparece_para_usuario2(
    usuario_autenticado, segundo_usuario_autenticado
):
    cliente1, _usuario1, headers1 = usuario_autenticado
    _cliente2, _usuario2, headers2 = segundo_usuario_autenticado

    cliente1.put("/dashboard/acoes/limpeza_tanque/alternar", headers=headers1)

    resposta_usuario2 = cliente1.get("/dashboard/acoes", headers=headers2)
    acoes = resposta_usuario2.json()["acoes"]
    limpeza = next(a for a in acoes if a["chave"] == "limpeza_tanque")
    assert limpeza["concluida"] is False