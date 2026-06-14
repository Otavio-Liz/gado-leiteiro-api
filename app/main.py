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
    docs_url="/docs",
    redoc_url="/redoc"
)

# ─── Rate Limiting ────────────────────────────────────────────────────────────

aplicacao.state.limiter = limitador
aplicacao.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
aplicacao.add_middleware(SlowAPIMiddleware)

# ─── CORS ─────────────────────────────────────────────────────────────────────

aplicacao.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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