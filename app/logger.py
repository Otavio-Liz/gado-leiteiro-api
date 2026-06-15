import logging
import sys
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
import os

# Criar pasta de logs se não existir
Path("logs").mkdir(exist_ok=True)

# Formato padrão
FORMATO = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
FORMATO_DATA = "%Y-%m-%d %H:%M:%S"

# Nível baseado no ambiente
AMBIENTE = os.getenv("AMBIENTE", "development")
NIVEL_ARQUIVO = logging.DEBUG if AMBIENTE == "development" else logging.INFO


def configurar_logger(nome: str) -> logging.Logger:
    logger = logging.getLogger(nome)
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    # ── Handler de console ────────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(FORMATO, FORMATO_DATA))

    # ── Handler de arquivo geral com rotação ──────────────────────────────
    arquivo_handler = RotatingFileHandler(
        f"logs/app_{datetime.now().strftime('%Y-%m-%d')}.log",
        maxBytes=5 * 1024 * 1024,  # 5MB por arquivo
        backupCount=7,              # mantém 7 arquivos antigos
        encoding="utf-8"
    )
    arquivo_handler.setLevel(NIVEL_ARQUIVO)
    arquivo_handler.setFormatter(logging.Formatter(FORMATO, FORMATO_DATA))

    # ── Handler de arquivo de erros com rotação ───────────────────────────
    erro_handler = RotatingFileHandler(
        f"logs/erros_{datetime.now().strftime('%Y-%m-%d')}.log",
        maxBytes=5 * 1024 * 1024,  # 5MB por arquivo
        backupCount=7,              # mantém 7 arquivos antigos
        encoding="utf-8"
    )
    erro_handler.setLevel(logging.ERROR)
    erro_handler.setFormatter(logging.Formatter(FORMATO, FORMATO_DATA))

    logger.addHandler(console_handler)
    logger.addHandler(arquivo_handler)
    logger.addHandler(erro_handler)

    return logger


# Loggers por módulo
logger_app      = configurar_logger("app")
logger_auth     = configurar_logger("auth")
logger_animais  = configurar_logger("animais")
logger_partos   = configurar_logger("partos")
logger_vacinas  = configurar_logger("vacinas")
logger_med      = configurar_logger("medicamentos")
logger_prod     = configurar_logger("producoes")
logger_rep      = configurar_logger("reproducao")
logger_dash     = configurar_logger("dashboard")
logger_rel      = configurar_logger("relatorios")
logger_usuario  = configurar_logger("usuarios")