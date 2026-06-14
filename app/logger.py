import logging
import sys
from datetime import datetime
from pathlib import Path

# Criar pasta de logs se não existir
Path("logs").mkdir(exist_ok=True)

# Formato padrão
FORMATO = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
FORMATO_DATA = "%Y-%m-%d %H:%M:%S"


def configurar_logger(nome: str) -> logging.Logger:
    logger = logging.getLogger(nome)
    logger.setLevel(logging.DEBUG)

    # Evitar handlers duplicados
    if logger.handlers:
        return logger

    # ── Handler de console ────────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(FORMATO, FORMATO_DATA))

    # ── Handler de arquivo geral ──────────────────────────────────────────
    arquivo_handler = logging.FileHandler(
        f"logs/app_{datetime.now().strftime('%Y-%m-%d')}.log",
        encoding="utf-8"
    )
    arquivo_handler.setLevel(logging.DEBUG)
    arquivo_handler.setFormatter(logging.Formatter(FORMATO, FORMATO_DATA))

    # ── Handler de arquivo de erros ───────────────────────────────────────
    erro_handler = logging.FileHandler(
        f"logs/erros_{datetime.now().strftime('%Y-%m-%d')}.log",
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