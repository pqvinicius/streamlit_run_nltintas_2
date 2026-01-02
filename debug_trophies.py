import sqlite3
import pandas as pd

def load_medal_table_sim(start_date, end_date):
    try:
        conn = sqlite3.connect('data/gamificacao_vendedores.db')
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
            AND v.nome IN ('Genis Alberto Do Carmo Felix', 'Marcio C Santos Junior')
            GROUP BY v.nome
            ORDER BY Pontos DESC
        """
        df = pd.read_sql_query(query, conn, params=[start_date, end_date])
        print(f"--- SIMULATION {start_date} to {end_date} ---")
        print(df.to_string())
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Simulate current period
    load_medal_table_sim('2025-12-26', '2026-01-02')

    # Simulate with slightly extended period to be sure
    load_medal_table_sim('2025-12-26', '2026-01-03')
