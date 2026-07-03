"""
Testes da Seção 8 — Medicamentos e Carência.

Cobre o checklist original:
- Validar estoque antes de aplicar medicamento.
- Baixar estoque em transação única.
- Restaurar estoque ao deletar aplicação.
- Editar aplicação com ajuste de estoque e recálculo de carência.
- Impedir aplicação em animal inativo.
- Medicamento pertence ao mesmo usuário do animal (isolamento).
- Estoque insuficiente, dose inválida, animal inativo, restauração de estoque.
"""
from datetime import date, timedelta
from decimal import Decimal


def _registrar_aplicacao(cliente, headers, animal_id, medicamento_id, **overrides):
    corpo = {
        "animal_id": animal_id,
        "medicamento_id": medicamento_id,
        "data_aplicacao": str(date.today()),
        "dose_aplicada": "10.00",
        "motivo": "Tratamento de teste",
    }
    corpo.update(overrides)
    return cliente.post("/medicamentos/aplicacoes/", json=corpo, headers=headers)


# ─── Estoque insuficiente ──────────────────────────────────────────────────

def test_registrar_aplicacao_estoque_insuficiente(usuario_autenticado, criar_animal, criar_medicamento):
    cliente, usuario, headers = usuario_autenticado
    animal = criar_animal(usuario.id)
    medicamento = criar_medicamento(usuario.id, estoque_atual=Decimal("5.00"))

    resposta = _registrar_aplicacao(
        cliente, headers, animal.id, medicamento.id, dose_aplicada="10.00"
    )

    assert resposta.status_code == 400
    assert "estoque" in resposta.json()["detail"].lower()


# ─── Dose inválida ──────────────────────────────────────────────────────────

def test_registrar_aplicacao_dose_zero_invalida(usuario_autenticado, criar_animal, criar_medicamento):
    cliente, usuario, headers = usuario_autenticado
    animal = criar_animal(usuario.id)
    medicamento = criar_medicamento(usuario.id)

    resposta = _registrar_aplicacao(
        cliente, headers, animal.id, medicamento.id, dose_aplicada="0"
    )

    assert resposta.status_code == 422


def test_registrar_aplicacao_dose_negativa_invalida(usuario_autenticado, criar_animal, criar_medicamento):
    cliente, usuario, headers = usuario_autenticado
    animal = criar_animal(usuario.id)
    medicamento = criar_medicamento(usuario.id)

    resposta = _registrar_aplicacao(
        cliente, headers, animal.id, medicamento.id, dose_aplicada="-1"
    )

    assert resposta.status_code == 422


# ─── Animal inativo ─────────────────────────────────────────────────────────

def test_registrar_aplicacao_animal_inativo(usuario_autenticado, criar_animal, criar_medicamento):
    cliente, usuario, headers = usuario_autenticado
    animal = criar_animal(usuario.id, status="inativo")
    medicamento = criar_medicamento(usuario.id)

    resposta = _registrar_aplicacao(cliente, headers, animal.id, medicamento.id)

    assert resposta.status_code == 400
    assert "inativo" in resposta.json()["detail"].lower()


# ─── Registro válido debita estoque e calcula carência ─────────────────────

def test_registrar_aplicacao_debita_estoque_e_calcula_carencia(usuario_autenticado, criar_animal, criar_medicamento):
    cliente, usuario, headers = usuario_autenticado
    animal = criar_animal(usuario.id)
    medicamento = criar_medicamento(usuario.id, estoque_atual=Decimal("100.00"), dias_carencia=7)
    hoje = date.today()

    resposta = _registrar_aplicacao(
        cliente, headers, animal.id, medicamento.id,
        dose_aplicada="10.00", data_aplicacao=str(hoje)
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["dias_carencia"] == 7
    assert corpo["carencia_encerra_em"] == str(hoje + timedelta(days=7))

    # Confirma que o estoque foi debitado de fato no banco, não só na resposta.
    consulta = cliente.get("/medicamentos/", headers=headers)
    medicamento_atualizado = next(m for m in consulta.json() if m["id"] == medicamento.id)
    assert Decimal(str(medicamento_atualizado["estoque_atual"])) == Decimal("90.00")


# ─── DELETE restaura estoque ─────────────────────────────────────────────────

def test_deletar_aplicacao_restaura_estoque(usuario_autenticado, criar_animal, criar_medicamento):
    cliente, usuario, headers = usuario_autenticado
    animal = criar_animal(usuario.id)
    medicamento = criar_medicamento(usuario.id, estoque_atual=Decimal("100.00"))

    aplicacao = _registrar_aplicacao(
        cliente, headers, animal.id, medicamento.id, dose_aplicada="15.00"
    ).json()

    resposta_delete = cliente.delete(f"/medicamentos/aplicacoes/{aplicacao['id']}", headers=headers)
    assert resposta_delete.status_code == 200

    consulta = cliente.get("/medicamentos/", headers=headers)
    medicamento_atualizado = next(m for m in consulta.json() if m["id"] == medicamento.id)
    assert Decimal(str(medicamento_atualizado["estoque_atual"])) == Decimal("100.00")


def test_deletar_aplicacao_inexistente_retorna_404(usuario_autenticado):
    cliente, usuario, headers = usuario_autenticado
    resposta = cliente.delete("/medicamentos/aplicacoes/999999", headers=headers)
    assert resposta.status_code == 404


# ─── PUT: ajuste de estoque por diferença de dose ───────────────────────────

def test_atualizar_aplicacao_aumentando_dose_debita_diferenca(usuario_autenticado, criar_animal, criar_medicamento):
    cliente, usuario, headers = usuario_autenticado
    animal = criar_animal(usuario.id)
    medicamento = criar_medicamento(usuario.id, estoque_atual=Decimal("100.00"))

    aplicacao = _registrar_aplicacao(
        cliente, headers, animal.id, medicamento.id, dose_aplicada="10.00"
    ).json()
    # estoque agora: 90.00

    resposta_put = cliente.put(
        f"/medicamentos/aplicacoes/{aplicacao['id']}",
        json={"dose_aplicada": "25.00"},  # diferença de +15
        headers=headers,
    )
    assert resposta_put.status_code == 200
    assert Decimal(str(resposta_put.json()["dose_aplicada"])) == Decimal("25.00")

    consulta = cliente.get("/medicamentos/", headers=headers)
    medicamento_atualizado = next(m for m in consulta.json() if m["id"] == medicamento.id)
    assert Decimal(str(medicamento_atualizado["estoque_atual"])) == Decimal("75.00")  # 90 - 15


def test_atualizar_aplicacao_diminuindo_dose_devolve_diferenca(usuario_autenticado, criar_animal, criar_medicamento):
    cliente, usuario, headers = usuario_autenticado
    animal = criar_animal(usuario.id)
    medicamento = criar_medicamento(usuario.id, estoque_atual=Decimal("100.00"))

    aplicacao = _registrar_aplicacao(
        cliente, headers, animal.id, medicamento.id, dose_aplicada="30.00"
    ).json()
    # estoque agora: 70.00

    resposta_put = cliente.put(
        f"/medicamentos/aplicacoes/{aplicacao['id']}",
        json={"dose_aplicada": "10.00"},  # diferença de -20
        headers=headers,
    )
    assert resposta_put.status_code == 200

    consulta = cliente.get("/medicamentos/", headers=headers)
    medicamento_atualizado = next(m for m in consulta.json() if m["id"] == medicamento.id)
    assert Decimal(str(medicamento_atualizado["estoque_atual"])) == Decimal("90.00")  # 70 + 20


def test_atualizar_aplicacao_aumento_sem_estoque_suficiente_e_atomico(usuario_autenticado, criar_animal, criar_medicamento):
    """Ponto crítico: se o aumento de dose falha por falta de estoque, NADA
    pode ter sido alterado — nem a dose da aplicação, nem o estoque."""
    cliente, usuario, headers = usuario_autenticado
    animal = criar_animal(usuario.id)
    medicamento = criar_medicamento(usuario.id, estoque_atual=Decimal("20.00"))

    aplicacao = _registrar_aplicacao(
        cliente, headers, animal.id, medicamento.id, dose_aplicada="10.00"
    ).json()
    # estoque agora: 10.00

    resposta_put = cliente.put(
        f"/medicamentos/aplicacoes/{aplicacao['id']}",
        json={"dose_aplicada": "50.00"},  # precisaria de +40, só há 10
        headers=headers,
    )
    assert resposta_put.status_code == 400

    # Nada deve ter mudado: dose continua 10, estoque continua 10.
    consulta_medicamento = cliente.get("/medicamentos/", headers=headers)
    medicamento_atualizado = next(m for m in consulta_medicamento.json() if m["id"] == medicamento.id)
    assert Decimal(str(medicamento_atualizado["estoque_atual"])) == Decimal("10.00")

    consulta_aplicacoes = cliente.get(f"/medicamentos/aplicacoes/animal/{animal.id}", headers=headers)
    aplicacao_atual = next(a for a in consulta_aplicacoes.json() if a["id"] == aplicacao["id"])
    assert Decimal(str(aplicacao_atual["dose_aplicada"])) == Decimal("10.00")


# ─── PUT: recálculo de carência ao mudar a data ─────────────────────────────

def test_atualizar_aplicacao_mudando_data_recalcula_carencia(usuario_autenticado, criar_animal, criar_medicamento):
    cliente, usuario, headers = usuario_autenticado
    animal = criar_animal(usuario.id)
    medicamento = criar_medicamento(usuario.id, dias_carencia=10)

    data_original = date.today() - timedelta(days=5)
    aplicacao = _registrar_aplicacao(
        cliente, headers, animal.id, medicamento.id, data_aplicacao=str(data_original)
    ).json()
    assert aplicacao["carencia_encerra_em"] == str(data_original + timedelta(days=10))

    nova_data = date.today() - timedelta(days=2)
    resposta_put = cliente.put(
        f"/medicamentos/aplicacoes/{aplicacao['id']}",
        json={"data_aplicacao": str(nova_data)},
        headers=headers,
    )
    assert resposta_put.status_code == 200
    corpo = resposta_put.json()
    # dias_carencia é o snapshot original (10) — só a data final muda.
    assert corpo["dias_carencia"] == 10
    assert corpo["carencia_encerra_em"] == str(nova_data + timedelta(days=10))


def test_atualizar_aplicacao_data_futura_e_bloqueada(usuario_autenticado, criar_animal, criar_medicamento):
    cliente, usuario, headers = usuario_autenticado
    animal = criar_animal(usuario.id)
    medicamento = criar_medicamento(usuario.id)

    aplicacao = _registrar_aplicacao(cliente, headers, animal.id, medicamento.id).json()

    data_futura = date.today() + timedelta(days=1)
    resposta_put = cliente.put(
        f"/medicamentos/aplicacoes/{aplicacao['id']}",
        json={"data_aplicacao": str(data_futura)},
        headers=headers,
    )
    assert resposta_put.status_code == 422


# ─── Isolamento entre usuários ──────────────────────────────────────────────

def test_usuario_nao_ve_aplicacao_de_outro_usuario(usuario_autenticado, segundo_usuario_autenticado, criar_animal, criar_medicamento):
    cliente1, usuario1, headers1 = usuario_autenticado
    _cliente2, usuario2, headers2 = segundo_usuario_autenticado

    animal1 = criar_animal(usuario1.id)
    medicamento1 = criar_medicamento(usuario1.id)
    aplicacao = _registrar_aplicacao(cliente1, headers1, animal1.id, medicamento1.id).json()

    # usuario2 tenta acessar a aplicação do usuario1 pelo mesmo cliente
    # (a fixture `cliente` é compartilhada entre os dois usuários dentro
    # do mesmo teste — o que muda é o header de autenticação).
    resposta_get = cliente1.get(f"/medicamentos/aplicacoes/animal/{animal1.id}", headers=headers2)
    assert resposta_get.status_code == 404  # animal não é do usuario2

    resposta_put = cliente1.put(
        f"/medicamentos/aplicacoes/{aplicacao['id']}",
        json={"dose_aplicada": "99.00"},
        headers=headers2,
    )
    assert resposta_put.status_code == 404

    resposta_delete = cliente1.delete(f"/medicamentos/aplicacoes/{aplicacao['id']}", headers=headers2)
    assert resposta_delete.status_code == 404

    # Confirma que nada foi alterado pela tentativa do usuario2.
    consulta = cliente1.get(f"/medicamentos/aplicacoes/animal/{animal1.id}", headers=headers1)
    assert len(consulta.json()) == 1
    assert Decimal(str(consulta.json()[0]["dose_aplicada"])) == Decimal("10.00")