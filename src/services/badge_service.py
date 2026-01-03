import pandas as pd
import logging
from typing import Any
from src.gamificacao_vendedores import get_engine

logger = logging.getLogger(__name__)

class BadgeService:
    def __init__(self):
        self.engine = get_engine()
        self._badges_config = self._load_badges_config()

    def _load_badges_config(self) -> pd.DataFrame:
        """Carrega regras de badges ativos do banco."""
        try:
            conn = self.engine._get_connection()
            query = """
                SELECT nome, icone, min_posicao, max_posicao 
                FROM config_ranking_badges 
                WHERE ativo = 1 
                ORDER BY min_posicao ASC
            """
            df = pd.read_sql(query, conn)
            conn.close()
            return df
        except Exception as e:
            logger.error(f"BADGES | Erro ao carregar config: {e}")
            return pd.DataFrame()

    def aplicar_badges(self, df_ranking: pd.DataFrame, pontuacao_col: str = "pontos") -> pd.DataFrame:
        """
        Aplica ícones de medalha/badge em um DataFrame de ranking.
        O DataFrame deve vir ordenado.
        Adiciona coluna 'badge_icon' (str).
        """
        if df_ranking.empty:
            return df_ranking

        # Garante que temos uma coluna de posição explícita baseada no índice atual
        # Assume que o DF já está ordenado por pontos
        df = df_ranking.copy()
        
        # Se não tiver coluna de rank explícita, cria baseada na linha
        if 'rank' not in df.columns:
            df['rank'] = range(1, len(df) + 1)
            
        df['badge_icon'] = "" # Default empty

        if self._badges_config.empty:
            return df

        # Itera sobre regras e aplica
        for _, rule in self._badges_config.iterrows():
            mask = (df['rank'] >= rule['min_posicao']) & (df['rank'] <= rule['max_posicao'])
            df.loc[mask, 'badge_icon'] = rule['icone']

        return df

    def get_top_badge(self, rank: int) -> str:
        """Retorna apenas o ícone para um dado rank específico (útil para cards isolados)."""
        if self._badges_config.empty: return ""
        
        for _, rule in self._badges_config.iterrows():
            if rule['min_posicao'] <= rank <= rule['max_posicao']:
                return rule['icone']
        return ""
