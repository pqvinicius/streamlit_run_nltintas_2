import sys
import os
import pandas as pd
from datetime import date
sys.path.append(os.path.abspath("."))

from src.gamificacao_vendedores import get_engine

def debug_ranking():
    engine = get_engine()
    # Force today or specific date if needed
    ref_date = date.today() 
    
    print(f"--- Debugging Ranking Pontos for {ref_date} ---")
    
    ranking = engine.db.get_ranking_pontos(ref_date)
    
    # Print key columns
    df = pd.DataFrame(ranking)
    if not df.empty:
        # Flatten medalhas dict for display
        df['bronze'] = df['medalhas'].apply(lambda x: x.get('BRONZE', 0))
        df['prata'] = df['medalhas'].apply(lambda x: x.get('PRATA', 0))
        df['ouro'] = df['medalhas'].apply(lambda x: x.get('OURO', 0))
        
        display_cols = ['rank', 'nome', 'pontos', 'bronze', 'prata', 'ouro', '_alcance_mensal']
        print(df[display_cols].head(20).to_string(index=False))
    else:
        print("Ranking is empty!")

if __name__ == "__main__":
    debug_ranking()
