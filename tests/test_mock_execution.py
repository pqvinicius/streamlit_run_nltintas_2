import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime
import pandas as pd
from pathlib import Path
import shutil
import sys
import os
import logging

# Configure logging to show info during test
logging.basicConfig(level=logging.INFO)

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import daily_seller_ranking

class TestE2EMock(unittest.TestCase):
    def setUp(self):
        # Setup Mock Environment
        self.test_dir = Path("tests/mock_env")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(parents=True, exist_ok=True)
        
        self.data_dir = self.test_dir / "data"
        self.data_dir.mkdir(exist_ok=True)
        self.output_dir = self.test_dir / "output"
        self.output_dir.mkdir(exist_ok=True)
        
        # 1. Create Dummy Sales Excel
        # Creating a DataFrame that mocks the expected input format
        df = pd.DataFrame({
            "Vendedor": ["Vendedor A", "Vendedor B", "Vendedor C"],
            "Meta": [1000, 1000, 1000],
            "Venda": [1500, 1000, 500], # A: 150%, B: 100%, C: 50%
            "Alcance (%)": [150, 100, 50] 
        })
        self.meta_path = self.data_dir / "Vendas.xlsx"
        df.to_excel(self.meta_path, index=False)
        
        # 2. Create Dummy Contacts CSV
        # This mirrors the structure of vendedores_contato.csv
        self.contacts_file = self.test_dir / "vendedores_contato.csv"
        with open(self.contacts_file, "w") as f:
            f.write("Vendedor;NomeTratado;Telefone;Ativo\n")
            f.write("Vendedor A;Vend A;5511999999991;S\n")
            f.write("Vendedor B;Vend B;5511999999992;S\n")
            f.write("Vendedor C;Vend C;5511999999993;S\n") # Ativo but low sales

        # Override BASE_DIR in the module to point to our test env
        self.original_base_dir = daily_seller_ranking.BASE_DIR
        daily_seller_ranking.BASE_DIR = self.test_dir

    def tearDown(self):
        # Restore BASE_DIR
        daily_seller_ranking.BASE_DIR = self.original_base_dir
        # Optional: Keep files for inspection
        # shutil.rmtree(self.test_dir)

    @patch("src.config.get_whatsapp_config")
    @patch("src.services.whatsapp_service.WhatsAppService")
    @patch("src.notifications.whatsapp_notifier.WhatsAppNotifier")
    @patch("src.gamificacao_vendedores.get_engine")
    @patch("src.daily_seller_ranking._ja_enviou_hoje")
    @patch("src.daily_seller_ranking._registrar_envio_hoje")
    def test_full_pipeline_mock(self, mock_reg_envio, mock_ja_enviou, mock_get_engine, mock_notifier_cls, mock_wa_service, mock_get_wa_config):
        print("\n\n--- INICIANDO TESTE MOCKADO E2E ---")
        
        # --- CONFIG MOCK ---
        # Forces all flags to TRUE
        mock_get_wa_config.return_value = {
            "enviar_whatsapp": True,
            "enviar_grupo": True,
            "enviar_individual": True,
            "nome_grupo": "GRUPO TESTE MOCK",
            "intervalo_entre_envios": 0,
            "group_id": "",
            "wait_time": 1,
            "tab_close": True,
            "enviar_ranking_diario": True,
            "enviar_ranking_vendedores": True
        }
        
        # --- IDEMPOTENCY MOCK ---
        # Pretend it never ran today
        mock_ja_enviou.return_value = False
        
        # --- NOTIFIER MOCK ---
        # Mock success for individual messages
        mock_notifier = mock_notifier_cls.return_value
        mock_notifier.send_individual_message.return_value = True
        
        # --- WHATSAPP SERVICE MOCK ---
        mock_wa_instance = mock_wa_service.return_value
        mock_wa_instance.send_ranking.return_value = True
        mock_wa_instance.send_individual_message.return_value = True
        
        # --- DATE MOCK (SEXTA-FEIRA) ---
        # Mocking datetime.now() to be a Friday (e.g., 2025-12-26 is a Friday)
        # We need to mock datetime.now in the module we are testing
        target_date = datetime(2025, 12, 26, 10, 0, 0) # Friday
        
        with patch("src.daily_seller_ranking.datetime") as mock_dt:
            mock_dt.now.return_value = target_date
            mock_dt.strftime = datetime.strftime
            # Also mock date for engine calls inside
            # But engine uses datetime.date which is hard to mock if imported directly
            # Let's rely on the fact that daily_seller_ranking uses datetime.now().date()
            
            # --- GAMIFICATION ENGINE MOCK ---
            mock_engine = MagicMock()
            mock_get_engine.return_value = mock_engine
            
            # Mock Data Returns
            mock_engine.db.get_resumo_dia.return_value = [] # No individual msgs for simplicity
            
            # Mock Weekly/Points Data
            mock_engine.db.get_ranking_semanal.return_value = [
                {"nome": "Vendedor A", "meta": 5000, "venda": 6000, "alcance": 120}
            ]
            mock_engine.db.get_ranking_pontos.return_value = [
                {"rank": 1, "nome": "Vendedor A", "pontos": 10, "medalhas": {"OURO": 1, "PRATA": 0, "BRONZE": 0, "BONUS": 0}}
            ]
            
            # EXECUTE THE MAIN FUNCTION
            generated_path = daily_seller_ranking.gerar_ranking_vendedores(self.meta_path, self.output_dir)
            
            # --- ASSERTIONS ---
            
            # Should have generated: Diario + Semanal + Pontos (3 images)
            # generated_path returns the first one (Diario), but paths_gerados should have 3.
            # We can check the mock_wa_service call args to see the list.
            
            mock_wa_instance.send_ranking.assert_called()
            args, _ = mock_wa_instance.send_ranking.call_args
            paths_sent = args[1] if len(args) > 1 else [] # The list of paths
            
            print(f"\n[INFO] Imagens enviadas no grupo: {paths_sent}")
            self.assertTrue(len(paths_sent) >= 3, "Deveria ter gerado Diário, Semanal e Pontos na Sexta-feira")
            self.assertTrue(any("ranking_vendedor" in p for p in paths_sent))
            self.assertTrue(any("ranking_semanal" in p for p in paths_sent))
            self.assertTrue(any("ranking_pontos" in p for p in paths_sent))
            
        print("\ntest_full_pipeline_mock: SUCESSO")

if __name__ == "__main__":
    unittest.main()
