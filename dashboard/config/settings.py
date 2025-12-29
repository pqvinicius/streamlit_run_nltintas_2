"""
Configurações centralizadas do dashboard.
Lê config.ini com fallback para valores padrão.
"""
from configparser import ConfigParser
from pathlib import Path
from typing import Dict, Optional
from functools import lru_cache

from dashboard.config.paths import get_config_path


@lru_cache(maxsize=1)
def get_mes_comercial_config() -> Dict[str, int]:
    """
    Lê configuração do mês comercial do config.ini.
    
    Returns:
        Dict com 'dia_inicio' e 'dia_fim' (padrão: 26 e 25).
    """
    config_path = get_config_path()
    
    if config_path is None:
        return {"dia_inicio": 26, "dia_fim": 25}
    
    try:
        parser = ConfigParser()
        parser.read(config_path, encoding="utf-8")
        
        if not parser.has_section("mes_comercial"):
            return {"dia_inicio": 26, "dia_fim": 25}
        
        sec = parser["mes_comercial"]
        return {
            "dia_inicio": sec.getint("dia_inicio", fallback=26),
            "dia_fim": sec.getint("dia_fim", fallback=25),
        }
    except Exception:
        # Em caso de erro, retorna defaults
        return {"dia_inicio": 26, "dia_fim": 25}


class AppSettings:
    """Classe para centralizar configurações da aplicação."""
    
    def __init__(self):
        self._mes_comercial = None
    
    @property
    def mes_comercial(self) -> Dict[str, int]:
        """Configuração do mês comercial."""
        if self._mes_comercial is None:
            self._mes_comercial = get_mes_comercial_config()
        return self._mes_comercial
    
    def clear_cache(self):
        """Limpa o cache de configurações."""
        self._mes_comercial = None
        get_mes_comercial_config.cache_clear()

