"""
Gerenciamento de caminhos do dashboard.
Adaptado para funcionar tanto localmente quanto no Streamlit Cloud.
"""
from pathlib import Path
from typing import Optional


def get_base_dir() -> Path:
    """
    Retorna o diretório base do projeto.
    
    No Streamlit Cloud, usa o diretório de trabalho atual.
    Localmente, usa o diretório do arquivo.
    """
    return Path(__file__).parent.parent.parent


def get_data_dir() -> Path:
    """
    Retorna o diretório de dados.
    
    Tenta encontrar 'data/' relativo ao diretório base.
    """
    base_dir = get_base_dir()
    data_dir = base_dir / "data"
    
    # Se não existir, tenta criar
    if not data_dir.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
    
    return data_dir


def get_db_path() -> Optional[Path]:
    """
    Retorna o caminho do banco de dados SQLite.
    
    Returns:
        Path do banco de dados ou None se não encontrado.
    """
    data_dir = get_data_dir()
    db_path = data_dir / "gamificacao_vendedores.db"
    
    # Debug print para logs do Streamlit Cloud
    # print(f"Procurando banco em: {db_path.absolute()}")
    
    return db_path


def get_config_path() -> Optional[Path]:
    """
    Retorna o caminho do arquivo de configuração.
    
    Returns:
        Path do config.ini ou None se não encontrado.
    """
    base_dir = get_base_dir()
    config_path = base_dir / "config.ini"
    
    return config_path if config_path.exists() else None

