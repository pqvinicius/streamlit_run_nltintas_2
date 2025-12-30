from __future__ import annotations

from configparser import ConfigParser
from functools import lru_cache
from pathlib import Path
import sys
import os
from typing import Dict, Any
from datetime import date

from src.logger import get_logger


def get_base_dir() -> Path:
    """
    Retorna o diretório base do projeto.
    - Quando empacotado (.exe), prioriza a pasta onde o executável está.
    - Em desenvolvimento, usa a raiz do repositório.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _resolve_config_path() -> Path:
    """
    Resolve o caminho do config.ini priorizando a pasta do executável.
    Ordem de busca:
      1) Diretório do executável (quando congelado - PyInstaller) - PRIORIDADE MÁXIMA
      2) Diretório de trabalho atual (onde o usuário executa o .exe)
      3) Raiz do projeto (fallback durante desenvolvimento)
    """
    # 1) diretório do executável (quando frozen) - PRIORIDADE MÁXIMA para .exe
    try:
        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).parent
            exe_path = exe_dir / "config.ini"
            if exe_path.exists():
                return exe_path
    except Exception:
        pass
    
    # 2) cwd (diretório de trabalho atual)
    cwd_path = Path.cwd() / "config.ini"
    if cwd_path.exists():
        return cwd_path
    
    # 3) fallback: raiz do projeto (repo) - apenas para desenvolvimento
    return get_base_dir() / "config.ini"


CONFIG_PATH = _resolve_config_path()


def get_execution_mode() -> str:
    """
    Detecta o modo de execução:
    1. Verifica variável de ambiente EXECUTION_MODE
    2. Fallback para horário local (BATCH: 20h às 06h)
    3. Padrão: INTERACTIVE
    """
    override = os.getenv("EXECUTION_MODE")
    if override and override.strip():
        # Ignora se for algo como "None" ou vazio
        mode = override.strip().upper()
        if mode not in ["NONE", "FALSE", "0", ""]:
            return mode

    from datetime import datetime
    now = datetime.now()
    # BATCH automático apenas na madrugada (20h até às 06h)
    if now.hour >= 20 or now.hour < 6:
        return "BATCH"
        
    return "INTERACTIVE"


@lru_cache(maxsize=1)
def _load_config() -> ConfigParser:
    parser = ConfigParser()
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Arquivo de configuração não encontrado: {CONFIG_PATH}")
    parser.read(CONFIG_PATH, encoding="utf-8")
    return parser


def get_web_config() -> Dict[str, object]:
    config = _load_config()
    if not config.has_section("web"):
        raise KeyError("Seção 'web' não encontrada no arquivo de configuração.")
    web_section = config["web"]
    return {
        "url_site": web_section.get("url_site", ""),
        "default_wait_seconds": web_section.getint("default_wait_seconds", fallback=15),
        "post_download_wait": web_section.getint("post_download_wait", fallback=30),
        "downloads_dir": web_section.get("downloads_dir", ""),  # opcional
        "output_dir": web_section.get("output_dir", ""),        # opcional (destino/montagem)
        "baixar_meta_vendedor": web_section.getboolean("baixar_meta_vendedor", fallback=True),
        "headless": web_section.getboolean("headless", fallback=False),
    }


def _ensure_directory(path_str: str) -> str:
    """
    Garante que o diretório existe quando um caminho é fornecido.
    Retorna a string original para facilitar serialização posterior.
    """
    if not path_str:
        return ""
    try:
        path = Path(path_str).expanduser()
        if not path.is_absolute():
            path = get_base_dir() / path
        path = path.resolve()
        path.mkdir(parents=True, exist_ok=True)
        return str(path)
    except Exception as exc:
        raise RuntimeError(f"Falha ao preparar diretório '{path_str}': {exc}") from exc


def get_paths() -> Dict[str, str]:
    """
    Lê caminhos de diretórios relevantes do config.ini.
    Se ausentes, retorna strings vazias para que o chamador aplique defaults.
    """
    config = _load_config()
    sec = "paths"
    if not config.has_section(sec):
        return {
            "downloads_dir": "",
            "output_dir": "",
            "pdf_output_dir": "",
            "data_dir": "",
        }
    s = config[sec]
    return {
        "downloads_dir": _ensure_directory(s.get("downloads_dir", "").strip()),
        "output_dir": _ensure_directory(s.get("output_dir", "").strip()),
        "pdf_output_dir": _ensure_directory(s.get("pdf_output_dir", "").strip()),
        "data_dir": _ensure_directory(s.get("data_dir", "").strip()),
    }


def get_column_types() -> Dict[str, str]:
    config = _load_config()
    if not config.has_section("column_types"):
        return {}
    return dict(config.items("column_types"))


def get_feriados_customizados() -> list[date]:
    """
    Lê feriados customizados do config.ini.
    """
    from datetime import datetime
    
    logger = get_logger(__name__)
    config = _load_config()
    if not config.has_section("feriados"):
        return []
    
    feriados_str = config.get("feriados", "feriados_customizados", fallback="")
    if not feriados_str or not feriados_str.strip():
        return []
    
    feriados: list[date] = []
    for item in feriados_str.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            data = datetime.strptime(item, "%d/%m/%Y").date()
            feriados.append(data)
        except ValueError:
            logger.warning("Formato de feriado inválido no config.ini: %s", item)
    
    return feriados


def get_mes_comercial_config() -> Dict[str, int]:
    config = _load_config()
    if not config.has_section("mes_comercial"):
        return {"dia_inicio": 26, "dia_fim": 25}
    sec = config["mes_comercial"]
    return {
        "dia_inicio": sec.getint("dia_inicio", fallback=26),
        "dia_fim": sec.getint("dia_fim", fallback=25),
    }


def get_gamificacao_config() -> Dict[str, Any]:
    config = _load_config()
    if not config.has_section("gamificacao"):
        return {
            "lojas_ignoradas": ["18", "30"],
            "faixa_dentro_media": 0.9,
            "company_name": "Nossa Loja",
            "producer_signature": "Produzido por Vinicius Xavier",
        }
    sec = config["gamificacao"]
    lojas_str = sec.get("lojas_ignoradas", fallback="18, 30")
    lojas_ignoradas = [loja.strip() for loja in lojas_str.split(",") if loja.strip()]
    return {
        "lojas_ignoradas": lojas_ignoradas,
        "faixa_dentro_media": sec.getfloat("faixa_dentro_media", fallback=0.9),
        "company_name": sec.get("company_name", fallback="Nossa Loja"),
        "producer_signature": sec.get("producer_signature", fallback="Produzido por Vinicius Xavier"),
    }


def get_horario_comercial_config() -> Dict[str, int]:
    config = _load_config()
    if not config.has_section("horario_comercial"):
        return {"hora_inicio": 8, "hora_fim": 18, "incremento_por_hora": 10}
    sec = config["horario_comercial"]
    return {
        "hora_inicio": sec.getint("hora_inicio", fallback=8),
        "hora_fim": sec.getint("hora_fim", fallback=18),
        "incremento_por_hora": sec.getint("incremento_por_hora", fallback=10),
    }


def get_ranking_config() -> Dict[str, Any]:
    config = _load_config()
    if not config.has_section("ranking"):
        return {
            "viewport_largura": 1080,
            "viewport_altura": 1080,
            "ranking_diario_nome": "ranking_diario.png",
            "ranking_semanal_nome": "ranking_semanal.png",
            "ranking_mensal_nome": "ranking_mensal.png",
            "ranking_vendedor_nome": "ranking_vendedor.png",
            "lojas_por_pagina_semanal": 20,
            "lojas_por_pagina_mensal": 20,
            "lojas_por_pagina_diario": 14,
        }
    sec = config["ranking"]
    return {
        "viewport_largura": sec.getint("viewport_largura", fallback=1080),
        "viewport_altura": sec.getint("viewport_altura", fallback=1080),
        "ranking_diario_nome": sec.get("ranking_diario_nome", fallback="ranking_diario.png"),
        "ranking_semanal_nome": sec.get("ranking_semanal_nome", fallback="ranking_semanal.png"),
        "ranking_mensal_nome": sec.get("ranking_mensal_nome", fallback="ranking_mensal.png"),
        "ranking_vendedor_nome": sec.get("ranking_vendedor_nome", fallback="ranking_vendedor.png"),
        "lojas_por_pagina_semanal": sec.getint("lojas_por_pagina_semanal", fallback=20),
        "lojas_por_pagina_mensal": sec.getint("lojas_por_pagina_mensal", fallback=20),
        "lojas_por_pagina_diario": sec.getint("lojas_por_pagina_diario", fallback=sec.getint("max_lojas_ranking_diario", fallback=14)),
    }





def get_whatsapp_config() -> Dict[str, Any]:
    """
    Lê configurações de WhatsApp do config.ini.
    
    Returns:
        Dicionário com configurações de WhatsApp
    """
    config = _load_config()
    if not config.has_section("whatsapp"):
        return {
            "enviar_whatsapp": False,
            "group_id": "",
            "intervalo_entre_envios": 15,
            "wait_time": 15,
            "tab_close": True,
            "enviar_ranking_diario": True,
            "enviar_ranking_vendedores": True,
        }
    
    sec = config["whatsapp"]
    
    def get_bool(key: str, default: bool) -> bool:
        val = sec.get(key, str(default)).lower()
        return val in ("true", "1", "yes", "sim")
    
    nome_grupo_raw = sec.get("nome_grupo", "Informações Comercial NL")
    nome_grupos = [g.strip() for g in nome_grupo_raw.split(",") if g.strip()]
    
    return {
        "enviar_whatsapp": get_bool("enviar_whatsapp", False),
        "nome_grupo": nome_grupos[0] if nome_grupos else "Informações Comercial NL",
        "nome_grupos": nome_grupos,
        "group_id": sec.get("group_id", ""),
        "intervalo_entre_envios": sec.getint("intervalo_entre_envios", fallback=15),
        "wait_time": sec.getint("wait_time", fallback=15),
        "tab_close": get_bool("tab_close", True),
        "enviar_ranking_diario": get_bool("enviar_ranking_diario", True),
        "enviar_ranking_vendedores": get_bool("enviar_ranking_vendedores", True),
        "enviar_individual": get_bool("enviar_individual", True),
        "usar_perfil_real": get_bool("usar_perfil_real", True),
    }


def get_calculo_meta_config() -> Dict[str, int]:
    config = _load_config()
    if not config.has_section("calculo_meta"):
        return {"dias_uteis": 22, "dias_passados": 5}
    sec = config["calculo_meta"]
    return {
        "dias_uteis": sec.getint("dias_uteis", fallback=22),
        "dias_passados": sec.getint("dias_passados", fallback=5),
    }




