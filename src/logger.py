from __future__ import annotations

import io
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# SINGLETON GLOBAL
_LOGGER: logging.Logger | None = None


def _get_logs_directory() -> Path:
    """
    Retorna o diretório onde os logs devem ser salvos.
    Prioridade:
    1. Pasta do executável (quando frozen)
    2. Pasta do projeto (raiz onde está main.py)
    """
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        logs_dir = exe_dir / "logs"
    else:
        # Durante desenvolvimento (assumindo src/logger.py -> src -> raiz)
        project_root = Path(__file__).resolve().parent.parent
        logs_dir = project_root / "logs"
    
    logs_dir.mkdir(exist_ok=True)
    return logs_dir


def _get_app_name() -> str:
    """Retorna o nome da aplicação."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).stem.upper()
    return "CRIARTEMPLATE"


def get_logger(nome: str = "ranking_vendedores", modo: str = "DEV") -> logging.Logger:
    """
    Recupera ou inicializa o logger (Singleton).
    Apenas a primeira chamada configura os handlers.
    Chamadas subsequentes retornam a instância configurada.
    """
    global _LOGGER

    # Retorna instância existente imediatamente
    if _LOGGER:
        return _LOGGER

    # Configuração Inicial (Executada apenas uma vez)
    logger = logging.getLogger(nome)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Impede duplicação na raiz

    # Remove handlers existentes para evitar acumulação em reloads
    if logger.handlers:
        logger.handlers.clear()

    # Caminho do arquivo de log
    log_dir = _get_logs_directory()
    log_file = log_dir / f"{_get_app_name()}_{datetime.now():%Y%m%d_%H%M%S}.log"

    # Formatter
    formatter_file = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    formatter_console = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S"
    )

    # Handler Console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter_console)
    console_handler.setLevel(logging.INFO)

    # Handler Arquivo
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter_file)
    file_handler.setLevel(logging.DEBUG)  # Arquivo sempre detalhado

    # Adiciona Handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    # Header de Inicialização Único
    logger.info("=" * 75)
    logger.info(f"PIPELINE | Sistema de Logging Iniciado: {log_file}")
    logger.info(f"PIPELINE | Modo: {modo}")
    logger.info("=" * 75)

    _LOGGER = logger
    return logger


def setup_logger(name: str | None = None, level: int = logging.INFO) -> logging.Logger:
    """Compatibilidade com chamadas legadas."""
    return get_logger()
