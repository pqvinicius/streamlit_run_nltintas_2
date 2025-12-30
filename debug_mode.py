from src.config import get_execution_mode
import os
from datetime import datetime
import sys

print("--- DIAGNÓSTICO DE MODO ---")
print(f"Horário Atual (hour): {datetime.now().hour}")
print(f"Env EXECUTION_MODE: {os.getenv('EXECUTION_MODE')}")
print(f"sys.argv: {sys.argv}")
print(f"Modo Detectado: {get_execution_mode()}")
print("---------------------------")
