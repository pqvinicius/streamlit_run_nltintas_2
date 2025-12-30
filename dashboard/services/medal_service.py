"""
Serviço de medalhas e conquistas.
Gerencia lógica de negócio relacionada a medalhas e rankings.
"""
import pandas as pd
from typing import List

import streamlit as st

from dashboard.database import queries


class MedalService:
    """Serviço para operações relacionadas a medalhas."""
    
    @st.cache_data(ttl=60, show_spinner=True)
    def get_medal_table(
        _self, 
        start_date: str, 
        end_date: str
    ) -> pd.DataFrame:
        """
        Carrega tabela de medalhas (quadro geral).
        Ordenação (User Request 30/12/2024):
        1. Pontos (filtro de data) - Decrescente
        2. % Meta Mensal (Current Status) - Decrescente
        3. Nome - Crescente
        """
        # 1. Carrega dados base (Pontos/Medalhas no período selecionado)
        df = queries.load_medal_table(start_date, end_date)
        
        if df.empty:
            return df

        # 2. Busca dados de Alcance Mensal (via GamificacaoDB para consistência)
        # Precisamos do % de alcance mensal atual para desempatar
        from src.gamificacao_vendedores import GamificacaoDB
        from datetime import date
        
        try:
            db = GamificacaoDB()
            # Reaproveita a lógica de cálculo mensal do ranking oficial
            # Ranking oficial já retorna calculado e sorted, mas precisamos mapear para o DF atual
            rank_oficial = db.get_ranking_pontos(date.today())
            
            # Cria mapa {nome: alcance_mensal}
            mapa_alcance = {item['nome']: item.get('_alcance_mensal', 0.0) for item in rank_oficial}
            
            # 3. Enriquece DF
            df['_alcance_mensal'] = df['Vendedor'].map(mapa_alcance).fillna(0.0)
            
            # 4. Ordena Python-side (Multi-index sort)
            # Ordem Rígida (User Request 30/12/2024 - 16:50):
            # 1. Pontos DESC
            # 2. % Alcance Mensal DESC
            # 3. Ouro DESC
            # 4. Prata DESC
            # 5. Bronze DESC
            df = df.sort_values(
                by=['Pontos', '_alcance_mensal', 'Ouro', 'Prata', 'Bronze'], 
                ascending=[False, False, False, False, False]
            )
            
            # Remove coluna auxiliar se não quiser exibir
            df = df.drop(columns=['_alcance_mensal'])
            
            return df
            
        except Exception as e:
            # Fallback: retorna ordenação original do SQL se der erro na lógica extra
            print(f"Erro no tie-breaker: {e}")
            return df
    
    @st.cache_data(ttl=60, show_spinner=True)
    def get_athlete_history(_self, vendedor: str) -> pd.DataFrame:
        """
        Carrega histórico de conquistas de um atleta.
        
        Args:
            vendedor: Nome do vendedor.
        
        Returns:
            DataFrame com colunas: data_conquista, tipo_trofeu, pontos.
        """
        return queries.load_athlete_history(vendedor)
    
    @st.cache_data(ttl=60, show_spinner=True)
    def get_conquistas_por_semana(_self, vendedor: str) -> pd.DataFrame:
        """
        Carrega conquistas agrupadas por semana para um vendedor.
        
        Args:
            vendedor: Nome do vendedor.
        
        Returns:
            DataFrame com colunas: Semana, Início, Fim, Pontos, Ouro, Prata, Bronze, Bonus_1, Bonus_2.
        """
        df = queries.load_conquistas_raw(vendedor)
        
        if df.empty:
            return pd.DataFrame()
        
        try:
            # Converte data_conquista para datetime
            df['data_conquista'] = pd.to_datetime(df['data_conquista'])
            
            # Calcula semana ISO (segunda a domingo, mas consideramos segunda a sábado)
            df['ano'] = df['data_conquista'].dt.isocalendar().year
            df['semana'] = df['data_conquista'].dt.isocalendar().week
            
            # Calcula segunda-feira da semana
            df['data_semana'] = df['data_conquista'].dt.to_period('W-MON').dt.start_time
            
            # Agrupa por semana
            resumo = df.groupby(['ano', 'semana', 'data_semana']).agg({
                'pontos': 'sum',
                'tipo_trofeu': lambda x: {
                    'OURO': (x == 'OURO').sum(),
                    'PRATA': (x == 'PRATA').sum(),
                    'BRONZE': (x == 'BRONZE').sum(),
                    'BONUS_1': (x == 'BONUS_1').sum(),
                    'BONUS_2': (x == 'BONUS_2').sum()
                }
            }).reset_index()
            
            # Expande o dicionário de medalhas em colunas
            resumo['ouro'] = resumo['tipo_trofeu'].apply(lambda x: x.get('OURO', 0))
            resumo['prata'] = resumo['tipo_trofeu'].apply(lambda x: x.get('PRATA', 0))
            resumo['bronze'] = resumo['tipo_trofeu'].apply(lambda x: x.get('BRONZE', 0))
            resumo['bonus_1'] = resumo['tipo_trofeu'].apply(lambda x: x.get('BONUS_1', 0))
            resumo['bonus_2'] = resumo['tipo_trofeu'].apply(lambda x: x.get('BONUS_2', 0))
            
            # Calcula data_fim (sábado da semana)
            resumo['data_fim'] = resumo['data_semana'] + pd.Timedelta(days=5)
            
            # Formata semana_uuid
            resumo['semana_uuid'] = resumo.apply(
                lambda row: f"{row['ano']}_W{row['semana']:02d}", axis=1
            )
            
            # Seleciona e ordena colunas
            resultado = resumo[[
                'semana_uuid', 'data_semana', 'data_fim', 
                'pontos', 'ouro', 'prata', 'bronze', 'bonus_1', 'bonus_2'
            ]].copy()
            
            resultado.columns = [
                'Semana', 'Início', 'Fim', 
                'Pontos', 'Ouro', 'Prata', 'Bronze', 'Bonus_1', 'Bonus_2'
            ]
            
            # Ordena por semana (mais recente primeiro)
            resultado = resultado.sort_values('Início', ascending=False)
            
            return resultado
            
        except Exception as e:
            st.error(f"Erro ao processar conquistas por semana: {e}")
            return pd.DataFrame()
    
    @st.cache_data(ttl=300, show_spinner=False)
    def get_all_vendedores(_self) -> List[str]:
        """
        Retorna lista de todos os vendedores ativos.
        
        Returns:
            Lista de nomes de vendedores.
        """
        df = queries.get_all_vendedores()
        
        if df.empty:
            return []
        
        return df['Vendedor'].unique().tolist()

