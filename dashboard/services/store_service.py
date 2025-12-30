"""
Serviço de Lojas.
Gerencia lógica de negócio relacionada a performance de lojas e comparações.
"""
import pandas as pd
from typing import List, Optional
import streamlit as st

from dashboard.database import queries


class StoreService:
    """Serviço para operações relacionadas a lojas."""
    
    @st.cache_data(ttl=60, show_spinner=True)
    def get_all_lojas(_self) -> List[str]:
        """Retorna lista de todas as lojas ativas."""
        df = queries.get_all_lojas()
        if df.empty: return []
        return df['loja'].tolist()

    @st.cache_data(ttl=60, show_spinner=True)
    def get_store_overview(_self, loja: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Carrega resumo de uma loja."""
        return queries.load_store_overview(loja, start_date, end_date)

    @st.cache_data(ttl=60, show_spinner=True)
    def get_store_sellers(_self, loja: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Carrega ranking de vendedores de uma loja."""
        return queries.load_store_sellers(loja, start_date, end_date)

    @st.cache_data(ttl=60, show_spinner=True)
    def get_store_evolution(_self, loja: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Carrega evolução diária (ganho e acumulado) de uma loja."""
        df = queries.load_store_evolution(loja, start_date, end_date)
        if not df.empty:
            df['data'] = pd.to_datetime(df['data'])
            df['pontos_acumulados'] = df['pontos_dia'].cumsum()
        return df

    @st.cache_data(ttl=60, show_spinner=True)
    def get_stores_comparison(_self, lojas: list, start_date: str, end_date: str) -> pd.DataFrame:
        """Carrega evolução comparativa de múltiplas lojas."""
        if not lojas: return pd.DataFrame()
        df = queries.load_stores_comparison_evolution(lojas, start_date, end_date)
        if not df.empty:
            df['data'] = pd.to_datetime(df['data'])
            # Calcula acumulado por loja
            df = df.sort_values(['loja', 'data'])
            df['pontos_acumulados'] = df.groupby('loja')['pontos_dia'].cumsum()
        return df

    @st.cache_data(ttl=60, show_spinner=True)
    def get_normalized_ranking(_self, start_date: str, end_date: str) -> pd.DataFrame:
        """Retorna o ranking de eficiência das lojas."""
        return queries.load_normalized_store_ranking(start_date, end_date)


def get_store_service():
    return StoreService()
