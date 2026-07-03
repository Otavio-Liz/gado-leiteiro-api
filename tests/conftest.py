"""
Fixtures compartilhadas para toda a suíte de testes do projeto.

Decisões de arquitetura (documentadas aqui para não se perderem):

1. MySQL real, não SQLite. Estoque e dose usam Numeric/DECIMAL — SQLite
   não impõe esse tipo da mesma forma que o MySQL, então um teste passando
   no SQLite não garante nada sobre o comportamento real em produção.

2. Isolamento por SAVEPOINT, não por rollback simples. As rotas da API
   chamam `banco.commit()` internamente. Se a sessão de teste estivesse
   numa transação simples, esse commit() encerraria a transação e
   "vazaria" dados entre testes. Com o padrão de SAVOPOINT + listener
   (documentado no próprio SQLAlchemy como "Joining a Session into an
   External Transaction"), cada commit() do código da aplicação fecha
   só o savepoint atual, e um novo é reaberto na hora — a transação
   externa (que a fixture reverte no final do teste) nunca é tocada.

3. Fixtures de autenticação (usuario_autenticado, segundo_usuario_autenticado)
   e fábricas (criar_animal, criar_medicamento) vivem aqui, não em um
   arquivo de teste específico, porque qualquer módulo futuro (Vacinas,
   Partos, Reprodução, Produções, Ocorrências...) vai precisar da mesma
   coisa: um usuário autenticado, um segundo usuário para testes de
   isolamento (Seção 3), e animais de teste. Escrever isso de novo em
   cada arquivo de teste seria exatamente o retrabalho que queremos evitar.
"""
import os
import uuid
from decimal import Decimal

import pytest
from dotenv import load_dotenv

load_dotenv()

# ─── Trava de segurança: nunca rodar testes contra o banco de produção ───────
#
# create_all/drop_all rodam contra o banco resolvido aqui. Se por engano
# DB_NAME do .env apontar para produção, isso teria potencial de apagar
# dados reais. Por isso: o nome do banco de teste É SEMPRE derivado
# (nunca igual ao DB_NAME de produção) e precisa conter "test" no nome —
# sem isso a suíte recusa rodar.

_DB_NAME_PRODUCAO = os.getenv("DB_NAME")
_NOME_BANCO_TESTE = os.getenv("TEST_DB_NAME", f"{_DB_NAME_PRODUCAO}_test")

if _NOME_BANCO_TESTE == _DB_NAME_PRODUCAO:
    raise RuntimeError(
        "TEST_DB_NAME não pode ser igual a DB_NAME. Configure um banco de "
        "teste separado (ex.: TEST_DB_NAME=gado_leiteiro_test no .env) "
        "para evitar rodar create_all/drop_all contra produção."
    )
if "test" not in _NOME_BANCO_TESTE.lower():
    raise RuntimeError(
        f"O nome do banco de teste ('{_NOME_BANCO_TESTE}') precisa conter "
        "'test' — trava de segurança para nunca rodar create_all/drop_all "
        "contra um banco que não seja claramente de teste."
    )

# IMPORTANTE: sobrescrever a env var ANTES de importar qualquer coisa de
# app/* — app/database.py lê DB_NAME no momento do import para montar a
# connection string do engine.
os.environ["DB_NAME"] = _NOME_BANCO_TESTE

from sqlalchemy import create_engine, text, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import app.database as database_app  # noqa: E402
from app.database import Base, pegar_banco  # noqa: E402


def _criar_banco_teste_se_nao_existir():
    """Conecta no servidor MySQL sem especificar banco e cria o schema de
    teste se ainda não existir. Usa as mesmas credenciais do .env — o
    usuário do banco precisa ter privilégio de CREATE DATABASE."""
    servidor = os.getenv("DB_HOST")
    porta = os.getenv("DB_PORT")
    usuario_db = os.getenv("DB_USER")
    senha_db = os.getenv("DB_PASSWORD")
    url_servidor = f"mysql+pymysql://{usuario_db}:{senha_db}@{servidor}:{porta}/"
    motor_servidor = create_engine(url_servidor)
    with motor_servidor.connect() as conexao:
        conexao.execute(text(
            f"CREATE DATABASE IF NOT EXISTS `{_NOME_BANCO_TESTE}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        ))
        conexao.commit()
    motor_servidor.dispose()


@pytest.fixture(scope="session")
def motor_teste():
    """Cria o schema de teste (se preciso) e todas as tabelas do projeto.

    IMPORTANTE: os models são importados aqui de forma EXPLÍCITA, um por
    um — não basta importar app.main. Alguns models (ex: TentativaLogin)
    só são importados dentro do corpo de funções em app/auth.py (import
    tardio, não no topo do módulo), então nunca chegam a se registrar em
    Base.metadata só por importar os routers. Uma tabela "invisível" pro
    create_all vira erro só em runtime, na primeira query — foi assim que
    o bug de tentativas_login apareceu.

    Lista mantida manualmente porque é mais simples e mais óbvia de
    revisar do que qualquer forma de descoberta automática de arquivo, e
    o custo de manter é baixo: um model novo = uma linha nova aqui.
    Confirmada contra os 9 arquivos reais em app/models/ (11 classes)."""
    _criar_banco_teste_se_nao_existir()

    from app.models import usuario           # noqa: F401 — Usuario
    from app.models import animal            # noqa: F401 — Animal
    from app.models import parto             # noqa: F401 — Parto
    from app.models import vacina            # noqa: F401 — Vacina
    from app.models import medicamento       # noqa: F401 — Medicamento, AplicacaoMedicamento
    from app.models import producao          # noqa: F401 — Producao, PrecoLeite
    from app.models import reproducao        # noqa: F401 — Reproducao, Ocorrencia
    from app.models import tentativa_login   # noqa: F401 — TentativaLogin (import tardio no app real)
    from app.models import refresh_token_valido  # noqa: F401 — RefreshTokenValido

    import app.main  # noqa: F401 — garante que os routers (e handlers de erro) também estejam carregados

    Base.metadata.create_all(bind=database_app.motor)
    yield database_app.motor
    Base.metadata.drop_all(bind=database_app.motor)


@pytest.fixture()
def sessao_banco(motor_teste):
    """Uma sessão por teste, isolada via SAVEPOINT (ver docstring do
    módulo). Nada que o teste gravar sobrevive além dele."""
    conexao = motor_teste.connect()
    transacao_externa = conexao.begin()
    SessaoTeste = sessionmaker(autocommit=False, autoflush=False, bind=conexao)
    sessao = SessaoTeste()

    savepoint = conexao.begin_nested()

    @event.listens_for(sessao, "after_transaction_end")
    def _reabrir_savepoint(sessao_evento, transacao_evento):
        nonlocal savepoint
        if not savepoint.is_active:
            savepoint = conexao.begin_nested()

    try:
        yield sessao
    finally:
        sessao.close()
        transacao_externa.rollback()
        conexao.close()


@pytest.fixture()
def cliente(sessao_banco):
    """TestClient com pegar_banco substituído pela sessão de teste acima —
    tudo que a API fizer durante o teste acontece dentro da mesma
    transação, que é revertida ao final."""
    from fastapi.testclient import TestClient
    from app.main import aplicacao

    def _pegar_banco_teste():
        yield sessao_banco

    aplicacao.dependency_overrides[pegar_banco] = _pegar_banco_teste
    with TestClient(aplicacao) as c:
        yield c
    aplicacao.dependency_overrides.pop(pegar_banco, None)


# ─── Fábricas de dados de teste ───────────────────────────────────────────────

def _criar_usuario(sessao_banco, email: str, senha: str = "SenhaForte123!", **overrides):
    from app.models.usuario import Usuario
    from app.security import gerar_hash_senha

    dados = {
        "nome": "Usuário Teste",
        "email": email,
        "senha_hash": gerar_hash_senha(senha),
        "ativo": True,  # obrigatório: pegar_usuario_atual devolve 403 se False
    }
    dados.update(overrides)
    usuario = Usuario(**dados)
    sessao_banco.add(usuario)
    sessao_banco.commit()
    sessao_banco.refresh(usuario)
    return usuario


@pytest.fixture()
def criar_usuario(sessao_banco):
    """Fábrica de usuário ATIVO direto no banco, com senha em texto puro
    escolhida pelo teste — diferente de usuario_autenticado (que gera um
    token pronto sem passar pelo login), esta fixture existe para testes
    que precisam chamar POST /usuarios/login de verdade, com uma senha
    conhecida. Uso: `criar_usuario(email="x@y.com", senha="Abc@123")`."""
    def _fabrica(email: str, senha: str = "SenhaForte123!", **overrides):
        return _criar_usuario(sessao_banco, email=email, senha=senha, **overrides)
    return _fabrica


@pytest.fixture()
def usuario_autenticado(sessao_banco, cliente):
    """Usuário real no banco + token de acesso válido, gerado direto via
    auth.criar_token — sem passar pelo fluxo de login/verificação de
    e-mail, que é lento e não é o que este fixture existe para testar.

    Retorna (cliente, usuario, headers). Uso típico num teste:
        def test_algo(usuario_autenticado):
            cliente, usuario, headers = usuario_autenticado
            resposta = cliente.get("/animais/", headers=headers)
    """
    from app.auth import criar_token

    usuario = _criar_usuario(sessao_banco, email=f"usuario1.{uuid.uuid4().hex[:8]}@leitetech.example")
    token = criar_token(usuario)
    headers = {"Authorization": f"Bearer {token}"}
    return cliente, usuario, headers


@pytest.fixture()
def segundo_usuario_autenticado(sessao_banco, cliente):
    """Segundo usuário independente, para testes de isolamento (Seção 3):
    provar que usuário A não lê, altera ou deleta dados do usuário B.
    Reaproveitável por qualquer módulo, não só Medicamentos."""
    from app.auth import criar_token

    usuario = _criar_usuario(sessao_banco, email=f"usuario2.{uuid.uuid4().hex[:8]}@leitetech.example")
    token = criar_token(usuario)
    headers = {"Authorization": f"Bearer {token}"}
    return cliente, usuario, headers


@pytest.fixture()
def criar_animal(sessao_banco):
    """Fábrica de Animal. Uso: `animal = criar_animal(usuario.id)` ou
    `criar_animal(usuario.id, status="inativo", sexo="M")` para casos
    específicos (animal inativo, macho, fora de lactação etc.)."""
    def _fabrica(usuario_id: int, **overrides):
        from app.models.animal import Animal

        dados = {
            "usuario_id": usuario_id,
            "nome": "Mimosa",
            "brinco": f"BR-{uuid.uuid4().hex[:8]}",
            "sexo": "F",
            "status": "ativo",
            "status_reprodutivo": "em_lactacao",
        }
        dados.update(overrides)
        animal = Animal(**dados)
        sessao_banco.add(animal)
        sessao_banco.commit()
        sessao_banco.refresh(animal)
        return animal
    return _fabrica


@pytest.fixture()
def criar_medicamento(sessao_banco):
    """Fábrica de Medicamento. Uso: `med = criar_medicamento(usuario.id)`
    ou `criar_medicamento(usuario.id, estoque_atual=Decimal("5.00"))`
    para casos de estoque específico."""
    def _fabrica(usuario_id: int, **overrides):
        from app.models.medicamento import Medicamento

        dados = {
            "usuario_id": usuario_id,
            "nome": "Oxitetraciclina",
            "dias_carencia": 7,
            "estoque_atual": Decimal("100.00"),
            "estoque_minimo": Decimal("10.00"),
            "unidade": "ml",
        }
        dados.update(overrides)
        medicamento = Medicamento(**dados)
        sessao_banco.add(medicamento)
        sessao_banco.commit()
        sessao_banco.refresh(medicamento)
        return medicamento
    return _fabrica