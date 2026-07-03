"""
Testes básicos da API — status, cadastro, login, animais e validações gerais.

Reescrito a partir da versão original do template, que testava um
contrato antigo (username/password form-encoded, sem verificação de
e-mail) que não corresponde mais à API atual:
- Cadastro e login usam JSON com email/senha (LoginRequest/UsuarioCreate),
  não form-encoded username/password.
- Login exige usuario.ativo == True, que só acontece após confirmar o
  código de verificação por e-mail — não é automático no cadastro.
- Usa o fixture `cliente` (isolado por SAVEPOINT, ver conftest.py) em vez
  de um TestClient global — evita que dados de uma execução vazem para a
  próxima.
"""
from datetime import date, timedelta

SENHA_VALIDA = "senha@123"


# ─── Status ─────────────────────────────────────────────────────────────────

def test_api_online(cliente):
    resposta = cliente.get("/")
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "online"


# ─── Cadastro ─────────────────────────────────────────────────────────────────

def test_cadastrar_usuario(cliente):
    resposta = cliente.post("/usuarios/cadastrar", json={
        "nome": "Usuário de Teste",
        "email": "teste.cadastro@leitetech.example",
        "senha": SENHA_VALIDA,
    })
    assert resposta.status_code == 200
    assert resposta.json()["email"] == "teste.cadastro@leitetech.example"


def test_cadastrar_usuario_duplicado(cliente, criar_usuario):
    # Precisa ser uma conta JÁ ATIVA: cadastrar de novo um e-mail com
    # cadastro pendente (nunca confirmado) apenas reenvia o código e
    # retorna 200 — não é tratado como duplicidade. Ver
    # app/routers/usuarios.py:cadastrar.
    usuario_existente = criar_usuario(email="duplicado@leitetech.example", senha=SENHA_VALIDA)

    resposta = cliente.post("/usuarios/cadastrar", json={
        "nome": "Outro Nome",
        "email": usuario_existente.email,
        "senha": SENHA_VALIDA,
    })
    assert resposta.status_code == 400


# ─── Login ────────────────────────────────────────────────────────────────────

def test_login_sucesso(cliente, criar_usuario):
    criar_usuario(email="login.sucesso@leitetech.example", senha=SENHA_VALIDA)

    resposta = cliente.post("/usuarios/login", json={
        "email": "login.sucesso@leitetech.example",
        "senha": SENHA_VALIDA,
    })
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert "access_token" in corpo
    assert "refresh_token" in corpo


def test_login_senha_errada(cliente, criar_usuario):
    criar_usuario(email="login.senhaerrada@leitetech.example", senha=SENHA_VALIDA)

    resposta = cliente.post("/usuarios/login", json={
        "email": "login.senhaerrada@leitetech.example",
        "senha": "senhaerrada@1",
    })
    assert resposta.status_code == 401


def test_login_usuario_inexistente(cliente):
    resposta = cliente.post("/usuarios/login", json={
        "email": "nao.existe@leitetech.example",
        "senha": SENHA_VALIDA,
    })
    assert resposta.status_code == 401


def test_login_conta_nao_verificada(cliente):
    """Cadastro sem confirmar o código por e-mail não pode logar — regra
    ausente no template antigo, que não conhecia esse fluxo."""
    cliente.post("/usuarios/cadastrar", json={
        "nome": "Pendente",
        "email": "pendente@leitetech.example",
        "senha": SENHA_VALIDA,
    })
    resposta = cliente.post("/usuarios/login", json={
        "email": "pendente@leitetech.example",
        "senha": SENHA_VALIDA,
    })
    assert resposta.status_code == 403


# ─── Validação de senha no cadastro ───────────────────────────────────────────

def _cadastro_com_senha(sufixo_email: str, senha: str) -> dict:
    return {
        "nome": "Teste Senha",
        "email": f"senha.{sufixo_email}@leitetech.example",
        "senha": senha,
    }


def test_senha_curta(cliente):
    resposta = cliente.post("/usuarios/cadastrar", json=_cadastro_com_senha("curta", "a@1"))
    assert resposta.status_code == 422


def test_senha_sem_simbolo(cliente):
    resposta = cliente.post("/usuarios/cadastrar", json=_cadastro_com_senha("semsimbolo", "senha1234"))
    assert resposta.status_code == 422


def test_senha_sem_numero(cliente):
    resposta = cliente.post("/usuarios/cadastrar", json=_cadastro_com_senha("semnumero", "senha@abc"))
    assert resposta.status_code == 422


def test_senha_sem_minuscula(cliente):
    resposta = cliente.post("/usuarios/cadastrar", json=_cadastro_com_senha("semminuscula", "SENHA@123"))
    assert resposta.status_code == 422


# ─── Animais ──────────────────────────────────────────────────────────────────

def test_criar_animal(usuario_autenticado):
    cliente, _usuario, headers = usuario_autenticado
    resposta = cliente.post("/animais/", json={
        "nome": "Mimosa",
        "brinco": "BR-001",
        "sexo": "F",
        "status": "ativo",
    }, headers=headers)
    assert resposta.status_code == 200
    assert resposta.json()["nome"] == "Mimosa"


def test_criar_animal_sem_autenticacao(cliente):
    resposta = cliente.post("/animais/", json={
        "nome": "Mimosa",
        "brinco": "BR-001",
        "sexo": "F",
    })
    assert resposta.status_code == 401


def test_macho_nao_pode_ter_producao(usuario_autenticado):
    cliente, _usuario, headers = usuario_autenticado
    resposta = cliente.post("/animais/", json={
        "nome": "Touro",
        "brinco": "BR-002",
        "sexo": "M",
        "producao_diaria_litros": 10,
    }, headers=headers)
    assert resposta.status_code == 400


def test_data_nascimento_futura(usuario_autenticado):
    cliente, _usuario, headers = usuario_autenticado
    data_futura = date.today() + timedelta(days=1)
    resposta = cliente.post("/animais/", json={
        "nome": "Futura",
        "brinco": "BR-003",
        "sexo": "F",
        "nascimento": str(data_futura),
    }, headers=headers)
    assert resposta.status_code == 400


def test_listar_animais_sem_autenticacao(cliente):
    resposta = cliente.get("/animais/")
    assert resposta.status_code == 401


# ─── Validações gerais ─────────────────────────────────────────────────────────

def test_rota_inexistente(cliente):
    resposta = cliente.get("/rota-que-nao-existe")
    assert resposta.status_code == 404


def test_token_invalido(cliente):
    resposta = cliente.get("/animais/", headers={"Authorization": "Bearer token_invalido"})
    assert resposta.status_code == 401