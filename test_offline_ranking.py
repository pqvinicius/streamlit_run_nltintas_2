import pandas as pd
from pathlib import Path
from src.services.ranking_service import RankingService
from src.config import get_base_dir
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = get_base_dir()
DATA_DIR = BASE_DIR / "data"
META_PATH = DATA_DIR / "MetaVendedor_2312.xlsx"

if not META_PATH.exists():
    print(f"ERROR: {META_PATH} not found. Please ensure it exists.")
else:
    # Setup Service
    service = RankingService() # FIXED: takes no arguments
    
    print("\n--- STARTING OFFLINE RANKING GENERATION ---")
    try:
        # We pass send_whatsapp=False
        result = service.execute(META_PATH, DATA_DIR, send_whatsapp=False)
        print(f"\nSUCCESS! Daily Ranking Path: {result}")
        
        # Check if other PNGs exist
        for ptype in ["pontos", "semanal", "mensal"]:
            found = list(DATA_DIR.glob(f"ranking_{ptype}*.png"))
            print(f"Found {len(found)} PNGs for type '{ptype}'")
            
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
