import pandas as pd
from pathlib import Path
import glob
import os

temp_dir = Path("tests/temp_real_data_execution")
candidates = list(temp_dir.glob("meta_empresa_*.xlsx"))
if not candidates:
    candidates = list(temp_dir.glob("Meta*.xlsx"))

if candidates:
    f = candidates[0]
    print(f"Reading: {f}")
    try:
        df = pd.read_excel(f)
        print("COLUNAS:")
        print(list(df.columns))
        print("\nAMOSTRA:")
        print(df.head(3).to_string())
    except Exception as e:
        print(f"Erro: {e}")
else:
    print("Nenhum arquivo encontrado.")
