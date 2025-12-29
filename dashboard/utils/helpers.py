"""
Funções auxiliares e utilitárias.
"""
from typing import Optional


def get_medal_icon(tipo: str) -> str:
    """
    Retorna o ícone emoji correspondente ao tipo de medalha.
    
    Args:
        tipo: Tipo de troféu (OURO, PRATA, BRONZE, etc.).
    
    Returns:
        String com emoji do ícone.
    """
    tipo_upper = tipo.upper()
    if "OURO" in tipo_upper:
        return "🥇"
    if "PRATA" in tipo_upper:
        return "🥈"
    if "BRONZE" in tipo_upper:
        return "🥉"
    return "🎖️"


def format_date(date_str: str, format_in: str = "%Y-%m-%d", format_out: str = "%d/%m/%Y") -> Optional[str]:
    """
    Formata uma data de um formato para outro.
    
    Args:
        date_str: String da data no formato de entrada.
        format_in: Formato de entrada (padrão: YYYY-MM-DD).
        format_out: Formato de saída (padrão: DD/MM/YYYY).
    
    Returns:
        String formatada ou None em caso de erro.
    """
    try:
        from datetime import datetime
        dt = datetime.strptime(date_str, format_in)
        return dt.strftime(format_out)
    except Exception:
        return None


def validate_vendedor(vendedor: Optional[str]) -> bool:
    """
    Valida se um nome de vendedor é válido.
    
    Args:
        vendedor: Nome do vendedor.
    
    Returns:
        True se válido, False caso contrário.
    """
    return vendedor is not None and len(vendedor.strip()) > 0

