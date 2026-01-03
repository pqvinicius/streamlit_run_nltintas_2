import sqlite3
import pandas as pd
from pathlib import Path
import sys
import os
from datetime import date, timedelta

sys.path.append(os.path.abspath("."))
from src.config import get_paths

def cleanup_duplicates():
    paths = get_paths()
    db_path = Path(paths["data_dir"]) / "gamificacao_vendedores.db"
    
    print(f"--- Cleaning Duplicates in {db_path} ---")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 1. Deduplicate PRATA (Weekly)
        # Strategy: Find (User, Year, Week) with count > 1. Keep min(id) or max(id)?
        # Let's keep the FIRST one (min id).
        
        print("Checking PRATA duplicates...")
        # SQLite doesn't have easy date functions for week, so we'll fetch all PRATA and process in python
        df_prata = pd.read_sql("SELECT id, vendedor_nome, data_conquista FROM trofeus WHERE tipo_trofeu='PRATA'", conn)
        df_prata['data_conquista'] = pd.to_datetime(df_prata['data_conquista']).dt.date
        
        ids_to_remove = []
        
        # Group by User + Week
        # Helper to get ISO Week
        def get_iso_week(d):
            return d.isocalendar()[:2] # (Year, Week)

        df_prata['week_key'] = df_prata['data_conquista'].apply(get_iso_week)
        
        grouped = df_prata.groupby(['vendedor_nome', 'week_key'])
        
        for name, group in grouped:
            if len(group) > 1:
                # Keep the first one, delete others
                keep_id = group.sort_values('id').iloc[0]['id']
                remove = group[group['id'] != keep_id]['id'].tolist()
                print(f"Removing {len(remove)} duplicate PRATA for {name[0]} in week {name[1]}")
                ids_to_remove.extend(remove)

        # 2. Deduplicate OURO/BONUS (Monthly)
        print("Checking OURO/BONUS duplicates...")
        df_mensal = pd.read_sql("SELECT id, vendedor_nome, data_conquista, tipo_trofeu FROM trofeus WHERE tipo_trofeu IN ('OURO', 'BONUS_1', 'BONUS_2')", conn)
        df_mensal['data_conquista'] = pd.to_datetime(df_mensal['data_conquista']).dt.date
        
        # Helper for Commercial Month (approx) or just Calendar Month for safety
        def get_month_key(d):
            return (d.year, d.month)

        df_mensal['month_key'] = df_mensal['data_conquista'].apply(get_month_key)
        
        grouped_mensal = df_mensal.groupby(['vendedor_nome', 'tipo_trofeu', 'month_key'])
        
        for name, group in grouped_mensal:
            if len(group) > 1:
                keep_id = group.sort_values('id').iloc[0]['id']
                remove = group[group['id'] != keep_id]['id'].tolist()
                print(f"Removing {len(remove)} duplicate {name[1]} for {name[0]} in month {name[2]}")
                ids_to_remove.extend(remove)

        if ids_to_remove:
            placeholders = ','.join('?' * len(ids_to_remove))
            cursor.execute(f"DELETE FROM trofeus WHERE id IN ({placeholders})", ids_to_remove)
            conn.commit()
            print(f"SUCCESS: Removed {len(ids_to_remove)} duplicate records.")
        else:
            print("No duplicates found to remove.")
            
    except Exception as e:
        print(f"ERROR: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    cleanup_duplicates()
