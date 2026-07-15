"""
Testes da Seção 9 — Vacinas.

Cobre o checklist original:
- Criação e update validam posse do animal.
- Validar intervalo mínimo entre doses.
- Validar vacina vencida.
- Validar próxima dose após data de aplicação.
- Testar animal de outro usuário, animal inativo, dose duplicada e datas inválidas.

Também cobre a correção feita durante a revisão: editar uma vacina não
exige mais que o animal continue ativo (só a criação exige isso),
alinhado com a mesma decisão já tomada em Medicamentos.
"""
from datetime import date, timedelta


def _registrar_vacina(cliente, headers, animal_id, **overrides):
    corpo = {
        "animal_id": animal_id,
        "nome_vacina": "Aftosa",
        "data_aplicacao": str(date.today() - timedelta(days=5)),
    }
    corpo.update(overrides)
    return cliente.post("/vacinas/", json=corpo, headers=headers)


# ─── Posse do animal ────────────────────────────────────────────────────────

def test_criar_vacina_animal_de_outro_usuario_e_bloqueada(
    usuario_autenticado, segundo_usuario_autenticado, criar_animal
):
    _cliente1, usuario1, _headers1 = usuario_autenticado
    cliente2, _usuario2, headers2 = segundo_usuario_autenticado

    animal_do_usuario1 = criar_animal(usuario1.id)

    resposta = _registrar_vacina(cliente2, headers2, animal_do_usuario1.id)
    assert resposta.status_code == 404


def test_editar_vacina_de_outro_usuario_e_bloqueada(
    usuario_autenticado, segundo_usuario_autenticado, criar_animal, criar_vacina
):
    cliente1, usuario1, headers1 = usuario_autenticado
    _cliente2, _usuario2, headers2 = segundo_usuario_autenticado

    animal = criar_animal(usuario1.id)
    vacina = criar_vacina(animal.id)

    resposta = cliente1.put(
        f"/vacinas/{vacina.id}", json={"observacao": "tentativa indevida"}, headers=headers2
    )
    assert resposta.status_code == 404


# ─── Animal inativo ─────────────────────────────────────────────────────────

def test_criar_vacina_animal_inativo_e_bloqueada(usuario_autenticado, criar_animal):
    cliente, usuario, headers = usuario_autenticado
    animal = criar_animal(usuario.id, status="inativo")

    resposta = _registrar_vacina(cliente, headers, animal.id)
    assert resposta.status_code == 400


def test_editar_vacina_permitida_mesmo_com_animal_inativo(
    usuario_autenticado, criar_animal, criar_vacina, sessao_banco
):
    """Correção feita na revisão: editar um registro histórico não deveria
    travar só porque o animal ficou inativo depois — só a CRIAÇÃO exige
    animal ativo, igual à decisão já tomada em Medicamentos."""
    cliente, usuario, headers = usuario_autenticado
    animal = criar_animal(usuario.id, status="ativo")
    vacina = criar_vacina(animal.id, nome_vacina="Aftosa")

    # Animal fica inativo DEPOIS da vacina já registrada
    animal.status = "inativo"
    sessao_banco.commit()

    resposta = cliente.put(
        f"/vacinas/{vacina.id}",
        json={"observacao": "corrigindo lote depois que o animal foi vendido"},
        headers=headers,
    )
    assert resposta.status_code == 200


# ─── Intervalo mínimo entre doses ────────────────────────────────────────────

def test_dose_duplicada_antes_do_intervalo_minimo_e_bloqueada(usuario_autenticado, criar_animal):
    cliente, usuario, headers = usuario_autenticado
    animal = criar_animal(usuario.id)

    data_primeira = date.today() - timedelta(days=25)
    primeira = _registrar_vacina(
        cliente, headers, animal.id, nome_vacina="Aftosa", data_aplicacao=str(data_primeira)
    )
    assert primeira.status_code == 200

    # 15 dias depois da primeira, ainda no passado — menor que o
    # intervalo mínimo de 30 dias entre doses da mesma vacina.
    data_segunda = data_primeira + timedelta(days=15)
    segunda = _registrar_vacina(
        cliente, headers, animal.id, nome_vacina="Aftosa", data_aplicacao=str(data_segunda)
    )
    assert segunda.status_code == 400
    assert "intervalo" in segunda.json()["detail"].lower()


def test_dose_apos_intervalo_minimo_e_permitida(usuario_autenticado, criar_animal):
    cliente, usuario, headers = usuario_autenticado
    animal = criar_animal(usuario.id)

    data_primeira = date.today() - timedelta(days=40)
    primeira = _registrar_vacina(
        cliente, headers, animal.id, nome_vacina="Aftosa", data_aplicacao=str(data_primeira)
    )
    assert primeira.status_code == 200

    data_segunda = date.today() - timedelta(days=5)  # 35 dias depois
    segunda = _registrar_vacina(
        cliente, headers, animal.id, nome_vacina="Aftosa", data_aplicacao=str(data_segunda)
    )
    assert segunda.status_code == 200


def test_intervalo_minimo_nao_se_aplica_a_vacinas_diferentes(usuario_autenticado, criar_animal):
    """O intervalo de 30 dias é por NOME de vacina — duas vacinas diferentes
    no mesmo animal, na mesma semana, não deveriam conflitar entre si."""
    cliente, usuario, headers = usuario_autenticado
    animal = criar_animal(usuario.id)

    hoje = date.today() - timedelta(days=1)
    primeira = _registrar_vacina(
        cliente, headers, animal.id, nome_vacina="Aftosa", data_aplicacao=str(hoje)
    )
    assert primeira.status_code == 200

    segunda = _registrar_vacina(
        cliente, headers, animal.id, nome_vacina="Brucelose", data_aplicacao=str(hoje)
    )
    assert segunda.status_code == 200


# ─── Vacina vencida / próxima dose ───────────────────────────────────────────

def test_vacina_vencida_e_bloqueada(usuario_autenticado, criar_animal):
    cliente, usuario, headers = usuario_autenticado
    animal = criar_animal(usuario.id)

    data_aplicacao = date.today() - timedelta(days=5)
    validade_ja_vencida = data_aplicacao - timedelta(days=1)  # vencida ANTES da aplicação

    resposta = _registrar_vacina(
        cliente, headers, animal.id,
        data_aplicacao=str(data_aplicacao),
        validade_vacina=str(validade_ja_vencida),
    )
    assert resposta.status_code == 422  # bloqueado no schema (field_validator)


def test_proxima_dose_antes_da_aplicacao_e_bloqueada(usuario_autenticado, criar_animal):
    cliente, usuario, headers = usuario_autenticado
    animal = criar_animal(usuario.id)

    data_aplicacao = date.today() - timedelta(days=5)
    proxima_dose_invalida = data_aplicacao - timedelta(days=1)

    resposta = _registrar_vacina(
        cliente, headers, animal.id,
        data_aplicacao=str(data_aplicacao),
        proxima_dose=str(proxima_dose_invalida),
    )
    assert resposta.status_code == 422  # bloqueado no schema (field_validator)


def test_data_aplicacao_futura_e_bloqueada(usuario_autenticado, criar_animal):
    cliente, usuario, headers = usuario_autenticado
    animal = criar_animal(usuario.id)

    data_futura = date.today() + timedelta(days=1)
    resposta = _registrar_vacina(cliente, headers, animal.id, data_aplicacao=str(data_futura))
    assert resposta.status_code == 422