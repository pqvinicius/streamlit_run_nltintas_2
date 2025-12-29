import sqlite3
from pathlib import Path

db_path = Path("data/gamificacao_vendedores.db")

if not db_path.exists():
    print(f"DATABASE NOT FOUND AT {db_path}")
else:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check Points Sum for Today
        print("--- POINTS STATUS (2025-12-23) ---")
        query = """
            SELECT 
                count(*) as total_trofeus,
                sum(pontos) as total_pontos,
                sum(case when tipo_trofeu = 'OURO' then 1 else 0 end) as ouros,
                sum(case when tipo_trofeu = 'PRATA' then 1 else 0 end) as pratas,
                sum(case when tipo_trofeu = 'BRONZE' then 1 else 0 end) as bronzes
            FROM trofeus
            WHERE data_conquista = '2025-12-23'
        """
        cursor.execute(query)
        res = cursor.fetchone()
        print(f"Total Trofeus: {res[0]}")
        print(f"Total Pontos: {res[1]}")
        print(f"Ouros: {res[2]} | Pratas: {res[3]} | Bronzes: {res[4]}")

        # Check Rankings Data (Simulate RankingService)
        print("\n--- TOP 5 RANKING PONTOS (Simulated) ---")
        query = """
            SELECT 
                v.nome, 
                SUM(t.pontos) as pts
            FROM vendedores v
            JOIN trofeus t ON v.nome = t.vendedor_nome
            GROUP BY v.nome
            HAVING pts > 0
            ORDER BY pts DESC
            LIMIT 5
        """
        cursor.execute(query)
        for row in cursor.fetchall():
            print(row)
                    
        conn.close()
    except Exception as e:
        print(f"ERROR: {e}")
