import unittest
import shutil
import sys
import os
from datetime import date, timedelta
from pathlib import Path

# Adiciona raiz do projeto ao path para importar src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
from src.gamificacao_vendedores import GamificacaoDB, MotorPontuacao

class TestGamificacao(unittest.TestCase):
    def setUp(self):
        # Setup: Cria banco temporário de teste
        self.test_dir = Path("tests/temp_data")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.test_dir / "test_gamificacao.db"
        
        # Limpa DB anterior se existir
        if self.db_path.exists():
            self.db_path.unlink()
            
        self.db = GamificacaoDB(self.db_path)
        self.engine = MotorPontuacao(self.db)
        
    def tearDown(self):
        # Cleanup
        if self.db_path.exists():
           pass # Manter para inspeção caso falhe, ou self.db_path.unlink()
        # shutil.rmtree(self.test_dir) # Opcional

    def test_bronze_trophy(self):
        """Testa se o troféu Bronze é concedido corretamente"""
        df = pd.DataFrame([
            {"Vendedor": "Vendedor A", "Meta": 1000, "Venda": 1000, "Alcance (%)": 100}, # Ganha
            {"Vendedor": "Vendedor B", "Meta": 1000, "Venda": 999, "Alcance (%)": 99.9}   # Não Ganha
        ])
        
        dia = date(2023, 10, 2) # Uma segunda-feira
        self.engine.processar_diario(df, dia)
        
        # Verificações
        resumo = self.db.get_resumo_dia(dia)
        
        # Vendedor A deve ter 1 troféu (Bronze)
        venda_a = next((r for r in resumo if r["nome"] == "Vendedor A"), None)
        self.assertIsNotNone(venda_a)
        self.assertIn("BRONZE", venda_a["trofeus"])
        self.assertEqual(venda_a["pontos_ganhos"], 1)
        
        # Vendedor B não deve ter troféus
        venda_b = next((r for r in resumo if r["nome"] == "Vendedor B"), None)
        self.assertIsNone(venda_b) # get_resumo_dia só retorna quem tem atividade ou venda registrada? 
        # Na verdade get_resumo_dia itera sobre 'resultados_meta' do dia. 
        # Vendedor B teve venda registrada, mas não ganhou troféu.
        
        # Vamos checar diretamente no banco
        conn = self.db._get_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM trofeus WHERE vendedor_nome='Vendedor B'")
        self.assertIsNone(c.fetchone())
        conn.close()

    def test_idempotency(self):
        """Testa se rodar duas vezes o mesmo dia não duplica troféus"""
        df = pd.DataFrame([
            {"Vendedor": "Vendedor X", "Meta": 100, "Venda": 150}
        ])
        dia = date(2023, 10, 3)
        
        # Roda 1ª vez
        self.engine.processar_diario(df, dia)
        
        # Roda 2ª vez
        self.engine.processar_diario(df, dia)
        
        conn = self.db._get_connection()
        c = conn.cursor()
        c.execute("SELECT count(*) FROM trofeus WHERE vendedor_nome='Vendedor X' AND tipo_trofeu='BRONZE'")
        count = c.fetchone()[0]
        conn.close()
        
        self.assertEqual(count, 1, "Não deve haver troféus duplicados para o mesmo dia/tipo")

if __name__ == '__main__':
    unittest.main()
