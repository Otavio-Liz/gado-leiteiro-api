"""
Testes básicos da API de Gestão de Gado Leiteiro.
Execute com: pytest tests/ -v
"""
import pytest
from fastapi.testclient import TestClient
from app.main import aplicacao

client = TestClient(aplicacao)

# Senha válida seguindo as novas regras de segurança
SENHA_VALIDA = "senha@123"


# ─── Status ───────────────────────────────────────────────────────────────────

def test_api_online():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "online"


# ─── Usuários ─────────────────────────────────────────────────────────────────

def test_cadastrar_usuario():
    response = client.post("/usuarios/cadastrar", json={
        "username": "teste_usuario",
        "senha": SENHA_VALIDA,
        "nome_completo": "Usuário de Teste"
    })
    assert response.status_code == 200
    assert response.json()["username"] == "teste_usuario"


def test_cadastrar_usuario_duplicado():
    client.post("/usuarios/cadastrar", json={
        "username": "duplicado",
        "senha": SENHA_VALIDA
    })
    response = client.post("/usuarios/cadastrar", json={
        "username": "duplicado",
        "senha": SENHA_VALIDA
    })
    assert response.status_code == 400


def test_login_sucesso():
    client.post("/usuarios/cadastrar", json={
        "username": "login_teste",
        "senha": SENHA_VALIDA
    })
    response = client.post("/usuarios/login", data={
        "username": "login_teste",
        "password": SENHA_VALIDA
    })
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()


def test_login_senha_errada():
    client.post("/usuarios/cadastrar", json={
        "username": "senha_errada",
        "senha": SENHA_VALIDA
    })
    response = client.post("/usuarios/login", data={
        "username": "senha_errada",
        "password": "senhaerrada"
    })
    assert response.status_code == 401


def test_login_usuario_inexistente():
    response = client.post("/usuarios/login", data={
        "username": "naoexiste",
        "password": SENHA_VALIDA
    })
    assert response.status_code == 401


def test_senha_curta():
    response = client.post("/usuarios/cadastrar", json={
        "username": "teste_senha",
        "senha": "123"
    })
    assert response.status_code == 422


def test_senha_sem_simbolo():
    response = client.post("/usuarios/cadastrar", json={
        "username": "teste_simbolo",
        "senha": "senha1234"
    })
    assert response.status_code == 422


def test_senha_sem_numero():
    response = client.post("/usuarios/cadastrar", json={
        "username": "teste_numero",
        "senha": "senha@abc"
    })
    assert response.status_code == 422


# ─── Animais ──────────────────────────────────────────────────────────────────

@pytest.fixture
def token():
    """Fixture que garante usuário criado e retorna token válido."""
    client.post("/usuarios/cadastrar", json={
        "username": "animal_teste",
        "senha": SENHA_VALIDA
    })
    response = client.post("/usuarios/login", data={
        "username": "animal_teste",
        "password": SENHA_VALIDA
    })
    return response.json()["access_token"]


def test_criar_animal(token):
    response = client.post("/animais/", json={
        "nome": "Mimosa",
        "brinco": "001",
        "sexo": "F",
        "status": "ativo"
    }, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["nome"] == "Mimosa"


def test_criar_animal_sem_autenticacao():
    response = client.post("/animais/", json={
        "nome": "Mimosa",
        "brinco": "001",
        "sexo": "F"
    })
    assert response.status_code == 401


def test_macho_nao_pode_ter_producao(token):
    response = client.post("/animais/", json={
        "nome": "Touro",
        "brinco": "002",
        "sexo": "M",
        "producao_diaria_litros": 10
    }, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 400


def test_data_nascimento_futura(token):
    response = client.post("/animais/", json={
        "nome": "Futura",
        "brinco": "003",
        "sexo": "F",
        "nascimento": "2099-01-01"
    }, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 400


def test_listar_animais_sem_autenticacao():
    response = client.get("/animais/")
    assert response.status_code == 401


# ─── Validações gerais ────────────────────────────────────────────────────────

def test_rota_inexistente():
    response = client.get("/rota-que-nao-existe")
    assert response.status_code == 404


def test_token_invalido():
    response = client.get("/animais/", headers={
        "Authorization": "Bearer token_invalido"
    })
    assert response.status_code == 401