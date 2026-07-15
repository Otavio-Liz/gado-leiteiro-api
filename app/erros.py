from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import (
    SQLAlchemyError, IntegrityError, OperationalError,
    DataError, ProgrammingError
)
from jose import JWTError
from app.logger import logger_app


# ─── Formato padrão de erro ───────────────────────────────────────────────────

def erro_response(status_code: int, mensagem: str, detalhes=None):
    corpo = {
        "erro": True,
        "status_code": status_code,
        "mensagem": mensagem
    }
    if detalhes:
        corpo["detalhes"] = detalhes
    return JSONResponse(status_code=status_code, content=corpo)


# ─── Handlers ─────────────────────────────────────────────────────────────────

def _valor_serializavel(valor):
    """Alguns erros de validação do Pydantic incluem o corpo cru (bytes) em
    'input' quando o corpo da requisição nem chega a ser interpretado como
    dict/JSON — por exemplo, um corpo form-encoded ou binário enviado para
    um endpoint que espera JSON. bytes não é serializável em JSON, e sem
    esse tratamento QUALQUER requisição malformada nesse formato derruba
    este handler com 500 em vez do 422 esperado (bug real, não só em login:
    qualquer endpoint que receba um corpo não-JSON está exposto a isso)."""
    if isinstance(valor, bytes):
        try:
            return valor.decode("utf-8", errors="replace")
        except Exception:
            return repr(valor)
    return valor


async def handler_validacao(request: Request, exc: RequestValidationError):
    """Erros de validação do Pydantic — campos inválidos, tipos errados, etc."""
    erros = []
    for erro in exc.errors():
        campo = " → ".join(str(x) for x in erro["loc"] if x != "body")
        erros.append({
            "campo": campo,
            "mensagem": erro["msg"],
            "valor_recebido": _valor_serializavel(erro.get("input"))
        })

    logger_app.warning(
        f"Erro de validação | {request.method} {request.url.path} | {len(erros)} erro(s)"
    )

    return erro_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        mensagem="Dados inválidos. Verifique os campos enviados.",
        detalhes=erros
    )


async def handler_integridade(request: Request, exc: IntegrityError):
    """Erros de integridade do banco — chave duplicada, FK violada, etc."""
    logger_app.error(
        f"Erro de integridade | {request.method} {request.url.path} | {str(exc.orig)}"
    )

    mensagem = "Erro de integridade no banco de dados."

    erro_str = str(exc.orig).lower()
    if "duplicate entry" in erro_str:
        mensagem = "Registro duplicado. Já existe um registro com esses dados."
    elif "foreign key" in erro_str or "cannot add or update a child row" in erro_str:
        mensagem = "Operação inválida. O registro referenciado não existe."
    elif "cannot delete or update a parent row" in erro_str:
        mensagem = "Não é possível excluir. Existem registros vinculados a este item."

    return erro_response(
        status_code=status.HTTP_409_CONFLICT,
        mensagem=mensagem
    )


async def handler_operacional(request: Request, exc: OperationalError):
    """Erros operacionais do banco — conexão perdida, timeout, etc."""
    logger_app.critical(
        f"Erro operacional no banco | {request.method} {request.url.path} | {str(exc)}"
    )
    return erro_response(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        mensagem="Serviço temporariamente indisponível. Tente novamente em alguns instantes."
    )


async def handler_dados(request: Request, exc: DataError):
    """Erros de dados — valor muito longo, tipo inválido, etc."""
    logger_app.error(
        f"Erro de dados | {request.method} {request.url.path} | {str(exc.orig)}"
    )
    return erro_response(
        status_code=status.HTTP_400_BAD_REQUEST,
        mensagem="Dados inválidos para o banco de dados. Verifique os valores enviados."
    )


async def handler_sqlalchemy(request: Request, exc: SQLAlchemyError):
    """Erro genérico do SQLAlchemy."""
    logger_app.error(
        f"Erro SQLAlchemy | {request.method} {request.url.path} | {str(exc)}"
    )
    return erro_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        mensagem="Erro interno no banco de dados. Tente novamente."
    )


async def handler_jwt(request: Request, exc: JWTError):
    """Erros de token JWT."""
    logger_app.warning(
        f"Erro JWT | {request.method} {request.url.path} | {str(exc)}"
    )
    return erro_response(
        status_code=status.HTTP_401_UNAUTHORIZED,
        mensagem="Token inválido ou expirado. Faça login novamente."
    )


async def handler_404(request: Request, exc: Exception):
    """
    Tratador registrado por CÓDIGO DE STATUS (404), não por tipo de
    exceção — isso significa que ele intercepta TANTO uma URL sem rota
    correspondente QUANTO qualquer `raise HTTPException(404, detail=...)`
    que o próprio código de negócio levante em qualquer router (ex:
    "Animal não encontrado.", "Sem dados de produção para o período...").

    Antes, os dois casos eram tratados como se fossem o mesmo problema, e
    a mensagem original de negócio era descartada e substituída por
    "Rota não encontrada." — o status code ficava certo, mas o frontend
    nunca via a mensagem de verdade. Distingue os dois aqui: Starlette usa
    detail="Not Found" (ou None) pra rota genuinamente inexistente; um
    HTTPException levantado pelo código de negócio sempre tem uma
    mensagem específica diferente disso.
    """
    detail = getattr(exc, "detail", None)
    if detail and detail != "Not Found":
        logger_app.warning(
            f"Recurso não encontrado | {request.method} {request.url.path} | {detail}"
        )
        return erro_response(
            status_code=status.HTTP_404_NOT_FOUND,
            mensagem=detail
        )

    logger_app.warning(
        f"Rota não encontrada | {request.method} {request.url.path}"
    )
    return erro_response(
        status_code=status.HTTP_404_NOT_FOUND,
        mensagem="Rota não encontrada."
    )


async def handler_metodo_nao_permitido(request: Request, exc: Exception):
    """Método HTTP não permitido."""
    logger_app.warning(
        f"Método não permitido | {request.method} {request.url.path}"
    )
    return erro_response(
        status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
        mensagem="Método não permitido para esta rota."
    )


async def handler_generico(request: Request, exc: Exception):
    """Qualquer erro não tratado — último recurso."""
    logger_app.critical(
        f"Erro inesperado | {request.method} {request.url.path} | "
        f"{type(exc).__name__}: {str(exc)}",
        exc_info=True
    )
    return erro_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        mensagem="Erro interno do servidor. Nossa equipe foi notificada."
    )