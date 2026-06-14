from fastapi import FastAPI
from app.routers import animais
from app.routers import producoes
from app.routers import vacinas
from app.routers import partos
from app.routers import medicamentos
from app.routers import usuarios

aplicacao = FastAPI(
    title="Gestão de Gado Leiteiro",
    description="API para gerenciamento de gado leiteiro",
    version="1.0.0"
)

aplicacao.include_router(animais.roteador)
aplicacao.include_router(producoes.roteador)
aplicacao.include_router(vacinas.roteador)
aplicacao.include_router(partos.roteador)
aplicacao.include_router(medicamentos.roteador)
aplicacao.include_router(usuarios.roteador)