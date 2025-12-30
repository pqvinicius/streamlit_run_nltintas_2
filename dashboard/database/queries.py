"""
Queries SQL centralizadas para o dashboard.
Todas as queries retornam DataFrames vazios em caso de erro.
"""
import pandas as pd
import sqlite3
from typing import Optional

from dashboard.database.connection import DatabaseConnection


def load_medal_table(start_date: str, end_date: str) -> pd.DataFrame:
    """Carrega tabela de medalhas (quadro geral)."""
    db = DatabaseConnection()
    if not db.exists: return pd.DataFrame()
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
            AND t.data_conquista BETWEEN ? AND ?
        WHERE v.ativo = 1 AND v.tipo != 'GERENTE'
        GROUP BY v.nome
        ORDER BY Pontos DESC, Ouro DESC, Prata DESC, Bronze DESC
    """
    try:
        with db.get_connection() as conn:
            df = pd.read_sql(query, conn, params=[start_date, end_date])
        return df
    except Exception: return pd.DataFrame()


def load_athlete_history(vendedor: str) -> pd.DataFrame:
    """Carrega histórico de conquistas de um atleta."""
    db = DatabaseConnection()
    if not db.exists: return pd.DataFrame()
    query = """
        SELECT data_conquista, tipo_trofeu, pontos 
        FROM trofeus 
        WHERE vendedor_nome = ? 
        ORDER BY data_conquista DESC
    """
    try:
        with db.get_connection() as conn:
            df = pd.read_sql(query, conn, params=[vendedor])
        return df
    except Exception: return pd.DataFrame()


def get_all_vendedores():
    """Retorna lista de todos os vendedores ativos."""
    db = DatabaseConnection()
    if not db.exists: return pd.DataFrame()
    query = "SELECT DISTINCT nome as Vendedor FROM vendedores WHERE ativo = 1 ORDER BY nome ASC"
    try:
        with db.get_connection() as conn:
            df = pd.read_sql(query, conn)
        return df
    except Exception: return pd.DataFrame()


def get_all_lojas():
    """Retorna lista de todas as lojas ativas."""
    db = DatabaseConnection()
    if not db.exists: return pd.DataFrame()
    query = "SELECT DISTINCT loja FROM vendedores WHERE ativo = 1 AND loja IS NOT NULL AND loja != '' ORDER BY loja ASC"
    try:
        with db.get_connection() as conn:
            df = pd.read_sql(query, conn)
        return df
    except Exception: return pd.DataFrame()


def load_store_overview(loja: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Resumo de performance de uma loja."""
    db = DatabaseConnection()
    if not db.exists: return pd.DataFrame()
    query = """
        SELECT 
            COUNT(DISTINCT v.nome) as vendedores_ativos,
            COALESCE(SUM(t.pontos), 0) as total_pontos,
            COALESCE(SUM(CASE WHEN t.tipo_trofeu = 'OURO' THEN 1 ELSE 0 END), 0) AS total_ouro,
            COALESCE(SUM(CASE WHEN t.tipo_trofeu IN ('PRATA', 'BRONZE') THEN 1 ELSE 0 END), 0) AS total_outras
        FROM vendedores v
        LEFT JOIN trofeus t 
            ON v.nome = t.vendedor_nome 
            AND t.data_conquista BETWEEN ? AND ?
        WHERE v.loja = ? AND v.ativo = 1
    """
    try:
        with db.get_connection() as conn:
            df = pd.read_sql(query, conn, params=[start_date, end_date, loja])
        return df
    except Exception: return pd.DataFrame()


def load_store_sellers(loja: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Lista de vendedores e medalhas de uma loja específica."""
    db = DatabaseConnection()
    if not db.exists: return pd.DataFrame()
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
            AND t.data_conquista BETWEEN ? AND ?
        WHERE v.loja = ? AND v.ativo = 1 AND v.tipo = 'VENDEDOR'
        GROUP BY v.nome
        ORDER BY Pontos DESC
    """
    try:
        with db.get_connection() as conn:
            df = pd.read_sql(query, conn, params=[start_date, end_date, loja])
        return df
    except Exception: return pd.DataFrame()


def load_store_evolution(loja: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Carrega evolução diária de pontos para uma loja."""
    db = DatabaseConnection()
    if not db.exists: return pd.DataFrame()
    query = """
        SELECT 
            t.data_conquista as data,
            SUM(t.pontos) AS pontos_dia
        FROM trofeus t
        JOIN vendedores v ON v.nome = t.vendedor_nome
        WHERE v.loja = ? AND t.data_conquista BETWEEN ? AND ?
        GROUP BY t.data_conquista
        ORDER BY t.data_conquista
    """
    try:
        with db.get_connection() as conn:
            df = pd.read_sql(query, conn, params=[loja, start_date, end_date])
        return df
    except Exception: return pd.DataFrame()


def load_stores_comparison_evolution(lojas: list, start_date: str, end_date: str) -> pd.DataFrame:
    """Carrega evolução diária para múltiplas lojas comparadas."""
    db = DatabaseConnection()
    if not db.exists: return pd.DataFrame()
    placeholders = ','.join(['?'] * len(lojas))
    query = f"""
        SELECT 
            t.data_conquista as data,
            v.loja,
            SUM(t.pontos) AS pontos_dia
        FROM trofeus t
        JOIN vendedores v ON v.nome = t.vendedor_nome
        WHERE v.loja IN ({placeholders}) 
          AND t.data_conquista BETWEEN ? AND ?
        GROUP BY t.data_conquista, v.loja
        ORDER BY t.data_conquista
    """
    params = list(lojas) + [start_date, end_date]
    try:
        with db.get_connection() as conn:
            df = pd.read_sql(query, conn, params=params)
        return df
    except Exception: return pd.DataFrame()


def load_normalized_store_ranking(start_date: str, end_date: str) -> pd.DataFrame:
    """Ranking de lojas por Pontos por Vendedor (Eficiência)."""
    db = DatabaseConnection()
    if not db.exists: return pd.DataFrame()
    query = """
        WITH stats AS (
            SELECT 
                v.loja,
                COUNT(DISTINCT v.nome) as qtd_vendedores,
                COALESCE(SUM(t.pontos), 0) as total_pontos,
                COALESCE(SUM(CASE WHEN t.tipo_trofeu = 'OURO' THEN 1 ELSE 0 END), 0) AS total_ouro
            FROM vendedores v
            LEFT JOIN trofeus t 
                ON v.nome = t.vendedor_nome 
                AND t.data_conquista BETWEEN ? AND ?
            WHERE v.ativo = 1 AND v.loja IS NOT NULL AND v.loja != '' AND v.tipo = 'VENDEDOR'
            GROUP BY v.loja
        )
        SELECT 
            loja AS Loja,
            qtd_vendedores AS Vendedores,
            total_pontos AS "Total Pontos",
            total_ouro AS "Total Ouro",
            ROUND(CAST(total_pontos AS REAL) / qtd_vendedores, 1) AS "Pontos por Vendedor"
        FROM stats
        WHERE qtd_vendedores > 0
        ORDER BY "Pontos por Vendedor" DESC, total_ouro DESC
    """
    try:
        with db.get_connection() as conn:
            df = pd.read_sql(query, conn, params=[start_date, end_date])
        return df
    except Exception: return pd.DataFrame()


def load_conquistas_raw(vendedor_nome: str) -> pd.DataFrame:
    """
    Carrega tabela crua de conquistas para processamento semanal.
    Retorna: data_conquista, tipo_trofeu, pontos
    """
    db = DatabaseConnection()
    if not db.exists: return pd.DataFrame()
    
    query = """
        SELECT
            data_conquista,
            tipo_trofeu,
            pontos,
            vendedor_nome
        FROM trofeus
        WHERE vendedor_nome = ?
        ORDER BY data_conquista ASC
    """
    try:
        with db.get_connection() as conn:
            df = pd.read_sql(query, conn, params=[vendedor_nome])
        return df
    except Exception: return pd.DataFrame()
