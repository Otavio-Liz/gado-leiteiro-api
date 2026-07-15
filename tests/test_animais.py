"""
Testes da Seção 10 — Animais.

Cobre o checklist original:
- Validar duplicidade de nome e brinco por usuário.
- Impedir regras incoerentes (macho em lactação/prenha/produção).
- Revisar se DELETE continua sendo soft delete.
- Testar alteração de sexo/status quando já existem produções, partos ou
  reproduções ligadas.

Os três últimos testes de "troca de sexo com histórico" cobrem a correção
feita na revisão: antes, nada impedia transformar uma fêmea com histórico
real em "macho" via PUT.
"""


def _corpo_animal(**overrides):
    corpo = {
        "nome": "Mimosa",
        "brinco": "BR-100",
        "sexo": "F",
        "status": "ativo",
    }
    corpo.update(overrides)
    return corpo


# ─── Duplicidade de nome e brinco ────────────────────────────────────────────

def test_brinco_duplicado_mesmo_usuario_e_bloqueado(usuario_autenticado):
    cliente, usuario, headers = usuario_autenticado
    cliente.post("/animais/", json=_corpo_animal(nome="Mimosa", brinco="BR-100"), headers=headers)

    resposta = cliente.post(
        "/animais/", json=_corpo_animal(nome="Outra Vaca", brinco="BR-100"), headers=headers
    )
    assert resposta.status_code == 400
    assert "brinco" in str(resposta.json()["detail"]).lower()


def test_nome_duplicado_mesmo_usuario_e_bloqueado_case_insensitive(usuario_autenticado):
    cliente, usuario, headers = usuario_autenticado
    cliente.post("/animais/", json=_corpo_animal(nome="Mimosa", brinco="BR-100"), headers=headers)

    resposta = cliente.post(
        "/animais/", json=_corpo_animal(nome="MIMOSA", brinco="BR-200"), headers=headers
    )
    assert resposta.status_code == 400
    assert "nome" in str(resposta.json()["detail"]).lower()


def test_brinco_igual_em_usuarios_diferentes_e_permitido(
    usuario_autenticado, segundo_usuario_autenticado
):
    cliente1, _usuario1, headers1 = usuario_autenticado
    cliente2, _usuario2, headers2 = segundo_usuario_autenticado

    resposta1 = cliente1.post("/animais/", json=_corpo_animal(brinco="BR-100"), headers=headers1)
    resposta2 = cliente2.post("/animais/", json=_corpo_animal(brinco="BR-100"), headers=headers2)

    assert resposta1.status_code == 200
    assert resposta2.status_code == 200


# ─── Regras incoerentes de sexo ──────────────────────────────────────────────

def test_macho_com_producao_diaria_e_bloqueado(usuario_autenticado):
    cliente, usuario, headers = usuario_autenticado
    resposta = cliente.post(
        "/animais/",
        json=_corpo_animal(nome="Touro", brinco="BR-300", sexo="M", producao_diaria_litros=10),
        headers=headers,
    )
    assert resposta.status_code == 400


def test_macho_com_status_reprodutivo_feminino_e_bloqueado(usuario_autenticado):
    cliente, usuario, headers = usuario_autenticado
    resposta = cliente.post(
        "/animais/",
        json=_corpo_animal(nome="Touro", brinco="BR-300", sexo="M", status_reprodutivo="em_lactacao"),
        headers=headers,
    )
    assert resposta.status_code == 400


# ─── Troca de sexo com histórico vinculado (correção da revisão) ────────────
#
# Nos três testes abaixo, o animal é criado com status_reprodutivo=
# "nao_aplicavel" de propósito — o padrão da fábrica é "em_lactacao", que
# por si só já dispara a regra ANTIGA ("status reprodutivo feminino não
# se aplica a macho") antes mesmo de chegar na regra NOVA que queremos
# testar aqui. Sem isolar isso, o teste passaria mesmo que a checagem de
# histórico não existisse — mesmo tipo de falso positivo que já apareceu
# antes nesta suíte.

def test_trocar_sexo_com_producao_vinculada_e_bloqueado(
    usuario_autenticado, criar_animal, criar_producao
):
    cliente, usuario, headers = usuario_autenticado
    animal = criar_animal(usuario.id, sexo="F", status_reprodutivo="nao_aplicavel")
    criar_producao(animal.id)

    resposta = cliente.put(f"/animais/{animal.id}", json={"sexo": "M"}, headers=headers)
    assert resposta.status_code == 400
    assert "produç" in resposta.json()["detail"].lower() or "histórico" in resposta.json()["detail"].lower()


def test_trocar_sexo_com_parto_vinculado_e_bloqueado(
    usuario_autenticado, criar_animal, criar_parto
):
    cliente, usuario, headers = usuario_autenticado
    animal = criar_animal(usuario.id, sexo="F", status_reprodutivo="nao_aplicavel")
    criar_parto(animal.id)

    resposta = cliente.put(f"/animais/{animal.id}", json={"sexo": "M"}, headers=headers)
    assert resposta.status_code == 400
    assert "parto" in resposta.json()["detail"].lower() or "histórico" in resposta.json()["detail"].lower()


def test_trocar_sexo_com_reproducao_vinculada_e_bloqueado(
    usuario_autenticado, criar_animal, criar_reproducao
):
    cliente, usuario, headers = usuario_autenticado
    animal = criar_animal(usuario.id, sexo="F", status_reprodutivo="nao_aplicavel")
    criar_reproducao(animal.id)

    resposta = cliente.put(f"/animais/{animal.id}", json={"sexo": "M"}, headers=headers)
    assert resposta.status_code == 400
    assert "reproduç" in resposta.json()["detail"].lower() or "histórico" in resposta.json()["detail"].lower()


def test_trocar_sexo_sem_historico_e_permitido(usuario_autenticado, criar_animal):
    """Sem nenhum registro real vinculado, trocar o sexo é só uma correção
    de cadastro — não deveria ser bloqueado. status_reprodutivo neutro
    pelo mesmo motivo dos três testes acima."""
    cliente, usuario, headers = usuario_autenticado
    animal = criar_animal(usuario.id, sexo="F", status_reprodutivo="nao_aplicavel")

    resposta = cliente.put(f"/animais/{animal.id}", json={"sexo": "M"}, headers=headers)
    assert resposta.status_code == 200
    assert resposta.json()["sexo"] == "M"


def test_editar_outros_campos_sem_mudar_sexo_nao_e_afetado(
    usuario_autenticado, criar_animal, criar_producao
):
    """A checagem de histórico só deve disparar quando o sexo MUDA de
    verdade — editar outro campo num animal com histórico não pode travar."""
    cliente, usuario, headers = usuario_autenticado
    animal = criar_animal(usuario.id, sexo="F")
    criar_producao(animal.id)

    resposta = cliente.put(
        f"/animais/{animal.id}", json={"observacao": "correção de cadastro"}, headers=headers
    )
    assert resposta.status_code == 200


# ─── Soft delete ──────────────────────────────────────────────────────────────

def test_delete_e_soft_delete(usuario_autenticado, criar_animal):
    cliente, usuario, headers = usuario_autenticado
    animal = criar_animal(usuario.id, status="ativo")

    resposta_delete = cliente.delete(f"/animais/{animal.id}", headers=headers)
    assert resposta_delete.status_code == 200

    # O registro continua existindo — só o status muda.
    resposta_get = cliente.get(f"/animais/{animal.id}", headers=headers)
    assert resposta_get.status_code == 200
    assert resposta_get.json()["status"] == "inativo"