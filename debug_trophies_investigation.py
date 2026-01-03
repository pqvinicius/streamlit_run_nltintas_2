import sqlite3
import pandas as pd
from pathlib import Path
import sys
import os

# Add src to path
sys.path.append(os.path.abspath("."))

from src.config import get_paths

def investigate_medals():
    paths = get_paths()
    db_path = Path(paths["data_dir"]) / "gamificacao_vendedores.db"
    
    conn = sqlite3.connect(db_path)
    
    names = ["LUCAS"]
    
    print(f"--- Investigating Medals in {db_path} ---")
    
    for name in names:
        query = f"""
            SELECT id, vendedor_nome, date(data_conquista) as data, tipo_trofeu, pontos
            FROM trofeus 
            WHERE vendedor_nome LIKE '%{name}%'
            ORDER BY data_conquista, tipo_trofeu
        """
        df = pd.read_sql(query, conn)
        
        if not df.empty:
            print(f"\nResults for '{name}':")
            print(df.to_string(index=False))
            
            # Check for duplicates (Name + Day + Type)
            dups = df[df.duplicated(subset=['vendedor_nome', 'data', 'tipo_trofeu'], keep=False)]
            if not dups.empty:
                print(f"\n[!!!] DUPLICATES FOUND for {name}:")
                print(dups)
            else:
                print(f"\nNo duplicates found for {name}.")
        else:
            print(f"\nNo records found for '{name}'")

    conn.close()

if __name__ == "__main__":
    investigate_medals()
