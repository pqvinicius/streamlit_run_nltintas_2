"""
Queries SQL centralizadas para o dashboard.
Todas as queries retornam DataFrames vazios em caso de erro.
"""
import pandas as pd
import sqlite3
from typing import Optional

from dashboard.database.connection import DatabaseConnection


def load_medal_table(start_date: str, end_date: str) -> pd.DataFrame:
    """
    Carrega tabela de medalhas (quadro geral).
    
    Args:
        start_date: Data de início (formato YYYY-MM-DD).
        end_date: Data de fim (formato YYYY-MM-DD).
    
    Returns:
        DataFrame com colunas: Vendedor, Pontos, Ouro, Prata, Bronze.
        DataFrame vazio em caso de erro.
    """
    db = DatabaseConnection()
    
    if not db.exists:
        return pd.DataFrame()
    
    query = """
        SELECT 
            v.nome AS Vendedor, 
            COALESCE(SUM(t.pontos), 0) AS Pontos,
            COALESCE(SUM(CASE WHEN t.tipo_trofeu = 'OURO' THEN 1 ELSE 0 END), 0) AS Ouro,
            COALESCE(SUM(CASE WHEN t.tipo_trofeu = 'PRATA' THEN 1 ELSE 0 END), 0) AS Prata,
            COALESCE(SUM(CASE WHEN t.tipo_trofeu = 'BRONZE' THEN 1 ELSE 0 END), 0) AS Bronze
        FROM vendedores v
        LEFT JOIN trofeus t 
            ON v.nome = t.vendedor_nome 
            AND t.data_conquista >= ?
        WHERE v.ativo = 1 AND v.tipo != 'GERENTE'
        GROUP BY v.nome
        ORDER BY Pontos DESC, Ouro DESC, Prata DESC, Bronze DESC
    """
    
    try:
        with db.get_connection() as conn:
            df = pd.read_sql(query, conn, params=[start_date])
        return df
    except Exception:
        return pd.DataFrame()


def load_athlete_history(vendedor: str) -> pd.DataFrame:
    """
    Carrega histórico de conquistas de um atleta.
    
    Args:
        vendedor: Nome do vendedor.
    
    Returns:
        DataFrame com colunas: data_conquista, tipo_trofeu, pontos.
        DataFrame vazio em caso de erro.
    """
    db = DatabaseConnection()
    
    if not db.exists:
        return pd.DataFrame()
    
    query = """
        SELECT 
            data_conquista, 
            tipo_trofeu, 
            pontos 
        FROM trofeus 
        WHERE vendedor_nome = ? 
        ORDER BY data_conquista DESC
    """
    
    try:
        with db.get_connection() as conn:
            df = pd.read_sql(query, conn, params=[vendedor])
        return df
    except Exception:
        return pd.DataFrame()


def load_conquistas_raw(vendedor: str) -> pd.DataFrame:
    """
    Carrega conquistas brutas de um vendedor (para processamento).
    
    Args:
        vendedor: Nome do vendedor.
    
    Returns:
        DataFrame com colunas: data_conquista, tipo_trofeu, pontos.
        DataFrame vazio em caso de erro.
    """
    db = DatabaseConnection()
    
    if not db.exists:
        return pd.DataFrame()
    
    query = """
        SELECT 
            data_conquista,
            tipo_trofeu,
            pontos
        FROM trofeus 
        WHERE vendedor_nome = ? 
        ORDER BY data_conquista DESC
    """
    
    try:
        with db.get_connection() as conn:
            df = pd.read_sql(query, conn, params=[vendedor])
        return df
    except Exception:
        return pd.DataFrame()


def get_all_vendedores() -> pd.DataFrame:
    """
    Retorna lista de todos os vendedores ativos.
    
    Returns:
        DataFrame com coluna 'nome'.
        DataFrame vazio em caso de erro.
    """
    db = DatabaseConnection()
    
    if not db.exists:
        return pd.DataFrame()
    
    query = """
        SELECT DISTINCT nome AS Vendedor
        FROM vendedores
        WHERE ativo = 1 AND tipo != 'GERENTE'
        ORDER BY nome
    """
    
    try:
        with db.get_connection() as conn:
            df = pd.read_sql(query, conn)
        return df
    except Exception:
        return pd.DataFrame()

