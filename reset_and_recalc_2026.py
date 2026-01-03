import sys
import os
import sqlite3
import shutil
from datetime import date, timedelta
from pathlib import Path

sys.path.append(os.path.abspath("."))
from src.gamificacao_vendedores import get_engine
from src.config import get_paths

def reset_and_recalc():
    paths = get_paths()
    db_path = Path(paths["data_dir"]) / "gamificacao_vendedores.db"
    backup_path = db_path.with_suffix(".db.bak")
    
    print(f"--- RESET AND RECALCULATE 2026 ---")
    
    # 1. Backup
    print(f"Backing up DB to {backup_path}...")
    shutil.copy(db_path, backup_path)
    
    conn = sqlite3.connect(db_path)
    
    try:
        # 2. Delete 2026 Trophies & Weekly Results to force clean slate
        print("Clearing 2026 Trofeus and Weekly Results...")
        conn.execute("DELETE FROM trofeus WHERE data_conquista >= '2026-01-01'")
        # Note: We keep resultado_meta (Sales History) to enable replay!
        
        # Also clear weekly aggregation to ensure it rebuilds correctly from daily data
        conn.execute("DELETE FROM resultado_semanal WHERE data_fechamento >= '2026-01-01'")
        
        conn.commit()
        conn.close()
        
        # 3. Replay
        engine = get_engine()
        start_date = date(2026, 1, 1)
        end_date = date.today() # 2026-01-03
        
        delta = end_date - start_date
        
        print(f"Replaying from {start_date} to {end_date}...")
        
        for i in range(delta.days + 1):
            d = start_date + timedelta(days=i)
            print(f"Processing {d}...")
            
            # This relies on 'resultado_meta' already having data for 'd'.
            # If no data exists for that day (e.g. script didn't run), nothing happens.
            
            # 3.1. Re-Process Daily (Bronze) from DB Logic
            # processar_diario requires DF. We simulate it by reading from DB.
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT vendedor_nome, meta, venda, alcance FROM resultado_meta WHERE data = ?", (d,))
            rows = cursor.fetchall()
            conn.close()
            
            for row in rows:
                nome = row['vendedor_nome']
                alcance = row['alcance']
                
                # Check Bronze Rule
                # We need access to SCORING_RULES. They are in engine instance.
                # Assume engine.SCORING_RULES exists
                if alcance >= engine.SCORING_RULES["BRONZE"]["meta_pct"]:
                    # Registrar Trofeu
                    engine.db.registrar_trofeu(
                        nome, 
                        d, 
                        "BRONZE", 
                        engine.SCORING_RULES["BRONZE"]["pontos"], 
                        f"Meta Diária Batida (Recalc): {alcance:.1f}%"
                    )
            
            # 3.2. Weekly Process (Updates Aggregation, Grants Prata)
            engine.processar_semanal(d)
            
            # 3.3. Monthly Process (Grants Gold/Bonus)
            engine.processar_mensal(d)
            
        print("Replay Complete!")
        
    except Exception as e:
        print(f"ERROR: {e}")
        # Restore backup?
        # shutil.copy(backup_path, db_path)

if __name__ == "__main__":
    reset_and_recalc()
