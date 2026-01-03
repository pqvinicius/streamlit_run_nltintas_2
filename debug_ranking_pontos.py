import sys
import os
import logging
from pathlib import Path
from datetime import date, datetime

# Setup basic logging
logging.basicConfig(level=logging.INFO)

# Add src to path
sys.path.append(os.path.abspath("."))

from src.services.ranking_service import RankingService, get_ranking_service
from src.gamificacao_vendedores import get_engine

def debug():
    print("DEBUG: Initializing RankingService...")
    service = get_ranking_service()
    
    print("DEBUG: Getting Engine...")
    engine = get_engine()
    
    dest_dir = Path("data/ranking_output")
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    # Mock logo if needed, or point to existing one
    logo_path = Path("logo_empresa.png")
    if not logo_path.exists():
        logo_path = None
        
    print(f"DEBUG: Generating images in {dest_dir}...")
    try:
        # Verify the method call signature matches: engine, destino_dir, logo
        paths = service._gerar_ranking_pontos(engine, dest_dir, logo_path)
        print(f"DEBUG: Success! Generated: {paths}")
        
        # Verify file existence
        for p in paths:
            if os.path.exists(p):
                print(f"VERIFIED: File exists at {p}")
            else:
                print(f"ERROR: File reported but not found at {p}")
                
    except Exception as e:
        print(f"DEBUG: Failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug()
