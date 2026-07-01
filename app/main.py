# ─── Carrega variáveis de ambiente ANTES de qualquer import ──────────────────
from dotenv import load_dotenv
load_dotenv(override=True)

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import (
    SQLAlchemyError, IntegrityError, OperationalError, DataError
)
from jose import JWTError
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import time
import os

from app.routers import (
    animais, producoes, vacinas, partos,
    medicamentos, usuarios, reproducao,
    dashboard, relatorios
)
from app.erros import (
    handler_validacao, handler_integridade, handler_operacional,
    handler_dados, handler_sqlalchemy, handler_jwt,
    handler_404, handler_metodo_nao_permitido, handler_generico
)
from app.logger import logger_app
from app.limitador import limitador

# ─── Origens permitidas ───────────────────────────────────────────────────────

AMBIENTE = os.getenv("AMBIENTE", "development")

if AMBIENTE == "production":
    ORIGENS_PERMITIDAS = os.getenv("ALLOWED_ORIGINS", "").split(",")
    ORIGENS_PERMITIDAS = [o.strip() for o in ORIGENS_PERMITIDAS if o.strip()]
    if not ORIGENS_PERMITIDAS:
        raise RuntimeError("ALLOWED_ORIGINS não definido para ambiente de produção.")
else:
    # Em desenvolvimento, lista explícita em vez de "*" — a spec CORS proíbe
    # allow_origins=["*"] combinado com allow_credentials=True, e browsers
    # modernos rejeitam essa combinação silenciosamente. Isso não aparece em
    # testes via Postman/Swagger (que não aplicam CORS), mas quebra quando o
    # frontend React faz requisições com credentials (cookies httpOnly).
    origens_dev = os.getenv("ALLOWED_ORIGINS", "")
    if origens_dev:
        ORIGENS_PERMITIDAS = [o.strip() for o in origens_dev.split(",") if o.strip()]
    else:
        ORIGENS_PERMITIDAS = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]

# ─── Aplicação ────────────────────────────────────────────────────────────────

aplicacao = FastAPI(
    title="Gestão de Gado Leiteiro",
    description="""
API completa para gerenciamento de propriedades leiteiras.

## Funcionalidades
- 🐄 Controle de animais com genealogia e foto
- 🍼 Registro de partos com carência de colostro
- 💉 Calendário de vacinas com alertas
- 💊 Estoque de medicamentos com carência automática
- 🥛 Produção de leite com relatórios financeiros
- 🔬 Reprodução e ocorrências sanitárias
- 📊 Dashboard e alertas consolidados
- 📄 Exportação em PDF e Excel
    """,
    version="2.0.0",
    docs_url="/docs" if AMBIENTE != "production" else None,
    redoc_url="/redoc" if AMBIENTE != "production" else None
)

# ─── Rate Limiting ────────────────────────────────────────────────────────────

aplicacao.state.limiter = limitador
aplicacao.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
aplicacao.add_middleware(SlowAPIMiddleware)

# ─── CORS ─────────────────────────────────────────────────────────────────────

aplicacao.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGENS_PERMITIDAS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)

# ─── Cabeçalhos de segurança HTTP ─────────────────────────────────────────────
#
# Nenhum desses depende de domínio ou hospedagem definidos — são respostas
# que o próprio backend já controla. O Strict-Transport-Security é a única
# exceção parcial: é seguro adicionar já (o navegador simplesmente ignora
# esse cabeçalho quando recebido via HTTP puro, por especificação), mas só
# passa a ter efeito de verdade quando o site for servido via HTTPS.
#
# CSP tem uma exceção pras rotas de documentação (/docs, /redoc,
# /openapi.json): o Swagger UI e o ReDoc carregam o próprio CSS/JS de um
# CDN externo (cdn.jsdelivr.net) pra desenhar a página — com
# default-src 'none' aplicado ali também, o navegador bloqueia esses
# arquivos e a página fica em branco. As rotas de API de verdade (tudo que
# não é doc) continuam com o 'none' rígido, que é o que importa de fato:
# elas só devolvem JSON, não têm motivo nenhum pra carregar recurso externo.

ROTAS_DOCUMENTACAO = ("/docs", "/redoc", "/openapi.json")

CSP_DOCUMENTACAO = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    "img-src 'self' https://fastapi.tiangolo.com data:; "
    "font-src 'self' data:; "
    "frame-ancestors 'none'"
)


@aplicacao.middleware("http")
async def cabecalhos_seguranca(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    if request.url.path in ROTAS_DOCUMENTACAO:
        response.headers["Content-Security-Policy"] = CSP_DOCUMENTACAO
    else:
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"

    return response

# ─── Middleware de log de requisições ─────────────────────────────────────────

@aplicacao.middleware("http")
async def log_requisicoes(request: Request, call_next):
    inicio = time.time()
    logger_app.info(f"→ {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        duracao = round((time.time() - inicio) * 1000, 2)
        logger_app.info(
            f"← {request.method} {request.url.path} | "
            f"Status: {response.status_code} | {duracao}ms"
        )
        return response
    except Exception as exc:
        duracao = round((time.time() - inicio) * 1000, 2)
        logger_app.error(
            f"✗ {request.method} {request.url.path} | "
            f"Erro: {type(exc).__name__} | {duracao}ms"
        )
        raise exc

# ─── Handlers de erro ─────────────────────────────────────────────────────────

aplicacao.add_exception_handler(RequestValidationError, handler_validacao)
aplicacao.add_exception_handler(IntegrityError, handler_integridade)
aplicacao.add_exception_handler(OperationalError, handler_operacional)
aplicacao.add_exception_handler(DataError, handler_dados)
aplicacao.add_exception_handler(SQLAlchemyError, handler_sqlalchemy)
aplicacao.add_exception_handler(JWTError, handler_jwt)
aplicacao.add_exception_handler(404, handler_404)
aplicacao.add_exception_handler(405, handler_metodo_nao_permitido)
aplicacao.add_exception_handler(Exception, handler_generico)

# ─── Routers ──────────────────────────────────────────────────────────────────

aplicacao.include_router(usuarios.roteador)
aplicacao.include_router(animais.roteador)
aplicacao.include_router(partos.roteador)
aplicacao.include_router(vacinas.roteador)
aplicacao.include_router(medicamentos.roteador)
aplicacao.include_router(producoes.roteador)
aplicacao.include_router(reproducao.roteador)
aplicacao.include_router(dashboard.roteador)
aplicacao.include_router(relatorios.roteador)

# ─── Health check ─────────────────────────────────────────────────────────────

@aplicacao.get("/", tags=["Status"])
def status_api():
    return {
        "status": "online",
        "versao": "2.0.0",
        "mensagem": "API de Gestão de Gado Leiteiro funcionando!"
    }