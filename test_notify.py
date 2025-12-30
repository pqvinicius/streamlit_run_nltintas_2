import sys
import os
from datetime import datetime
from pathlib import Path

# Ajustar path
sys.path.append(os.getcwd())

from src.services.ranking_service import get_ranking_service
from src.gamificacao_vendedores import get_engine
import pandas as pd

def test_notify():
    print("=== TESTE NOTIFY COMPLETO ===")
    service = get_ranking_service()
    engine = get_engine()
    
    # Simular dados (precisamos de um df para processar_diario se quisermos dados novos, 
    # mas get_resumo_dia já tem dados do banco)
    now = datetime.now()
    print(f"Executando simulação para {now}")
    
    # Chamar _notify diretamente (precisamos de paths falsos)
    paths_fake = [Path("data/ranking_vendedor_p1.png")]
    
    # Criar um WhatsAppService fake para não abrir o browser de verdade durante o teste
    class FakeSender:
        def __init__(self):
            self.driver = type('FakeDriver', (), {'quit': lambda: print("Driver Quit")})()
        def send_ranking(self, groups, paths, caption=None):
            print(f"SIMULAÇÃO: Enviando Ranking para {groups}")
            return True
        def send_individual_message(self, fone, msg):
            print(f"SIMULAÇÃO: Enviando msg para {fone}: {msg[:20]}...")
            return True

    from unittest.mock import patch
    
    with patch('src.services.ranking_service.WhatsAppService', return_value=FakeSender()):
        print("\nChamando _notify...")
        service._notify(paths_fake, engine, send_whatsapp=True)

if __name__ == "__main__":
    test_notify()
