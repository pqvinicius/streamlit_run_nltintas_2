from __future__ import annotations
from pathlib import Path
from src.services.ranking_service import get_ranking_service

# Facade module for backward compatibility and Main integration

def gerar_ranking_vendedores(meta_arquivo: Path, destino_dir: Path, send_whatsapp: bool = True) -> Path:
    """
    Fachada para o novo RankingService.
    Gera o Ranking de Vendedores (Diário/Semanal/Mensal) e notifica via WhatsApp.
    """
    service = get_ranking_service()
    return service.execute(meta_arquivo, destino_dir, send_whatsapp=send_whatsapp)
