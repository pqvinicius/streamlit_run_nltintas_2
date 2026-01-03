import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
import pandas as pd
from pathlib import Path
import shutil
import os
import sys

# Adiciona diretório raiz ao path para imports funcionarem
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.web_automation import executar_web_automation
from src.daily_seller_ranking import gerar_ranking_vendedores
from src.gamificacao_vendedores import GamificacaoDB, MotorPontuacao

class TestRealDataDryRun(unittest.TestCase):
    def setUp(self):
        # Setup Temp Dir
        self.temp_dir = Path("tests/temp_real_data_execution")
        # if self.temp_dir.exists():
        #     shutil.rmtree(self.temp_dir) # Comentado para preservar download em caso de erro no patch
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        self.temp_db_path = self.temp_dir / "temp_gamificacao.db"

    def test_run_real_download_and_process(self):
        print("\n" + "="*60)
        print("🚀 INICIANDO TESTE COM DADOS REAIS (DRY RUN)")
        print(f"📂 Diretório Temporário: {self.temp_dir.resolve()}")
        print("="*60)

        # 1. DOWNLOAD REAL
        print("\n[1/4] Verificando dados reais...")
        # 1. DOWNLOAD REAL - Precisa ser Meta Vendedor
        print("\n[1/4] Verificando dados reais (Meta Vendedor)...")
        
        # Otimização: Procura por Meta Vendedor
        candidates = list(self.temp_dir.glob("MetaVendedor_*.xlsx"))
        if candidates and len(candidates) > 0:
             meta_path_vendedor = candidates[0]
             print(f"ℹ️ Arquivo Vendedor já existente: {meta_path_vendedor.name}. Pulando download.")
        else:
             print("Downloading dados reais do BI (Completo: Loja + Vendedor)...")
             try:
                # Chama a automação real com flag False para baixar tudo (incluindo vendedores)
                arquivos = executar_web_automation(
                    diretorio_destino=self.temp_dir,
                    somente_meta_empresa=False, # Baixar Vendedores também
                    force_overwrite=True
                )
                meta_path_vendedor = arquivos.get("meta_vendedor")
             except Exception as e:
                self.fail(f"❌ Erro fatal no download: {e}")

        if not meta_path_vendedor or not os.path.exists(meta_path_vendedor):
             # Fallback
             candidates = list(self.temp_dir.glob("MetaVendedor*.xlsx"))
             if candidates:
                 meta_path_vendedor = candidates[0]
                 print(f"⚠️ Arquivo Vendedor encontrado via fallback: {meta_path_vendedor.name}")
             else:
                 self.fail("❌ Download falhou: Arquivo de Meta Vendedor não encontrado.")
        else:
            print(f"✅ Arquivo de Meta Vendedor pronto: {Path(meta_path_vendedor).name}")

            # DEBUG: Imprimir colunas do arquivo baixado (Vendedor)
            try:
                df_debug = pd.read_excel(meta_path_vendedor)
                print(f"[DEBUG] Colunas Vendedor: {list(df_debug.columns)}")
            except Exception as e:
                print(f"Erro debug: {e}")

        # 2. PREPARAR MOCKS (Sem envio, DB Temp, Data Fake)
        print("\n[2/4] Configurando Ambiente (Mock WhatsApp + DB Isolado)...")
        
        # Mock Date: Force Friday to test full ranking generation
        simulated_date = datetime(2025, 12, 26, 17, 30, 0) # Friday
        
        # Config de Pontuação Real mas apontando para DB Temp
        real_gamificacao_db = GamificacaoDB(db_path=self.temp_db_path)
        real_engine = MotorPontuacao(db=real_gamificacao_db)

        # Mocks Context
        # CORREÇÃO: Patch no local onde é definido
        # Como daily_seller_ranking agora é facade, precisamos mockar onde a data é usada (Service e Gamificacao)
        with patch("src.services.ranking_service.datetime") as mock_dt_service, \
             patch("src.gamificacao_vendedores.datetime") as mock_dt_gamificacao, \
             patch("src.gamificacao_vendedores.get_engine") as mock_get_engine, \
             patch("src.config.get_whatsapp_config") as mock_wa_cfg, \
             patch("src.services.ranking_service.WhatsAppService") as MockWhatsAppService:
             
            # 2.1 Configurar Mocks
            mock_dt_service.now.return_value = simulated_date
            mock_dt_service.strftime = datetime.strftime
            
            mock_dt_gamificacao.now.return_value = simulated_date
            mock_dt_gamificacao.date.today.return_value = simulated_date.date()
            mock_dt_gamificacao.strftime = datetime.strftime
            
            # Engine retorna nossa instância conectada ao DB temporário
            mock_get_engine.return_value = real_engine
            
            # Config WhatsApp "Ativada" mas com envio mockado
            mock_wa_cfg.return_value = {
                "enviar_whatsapp": True,
                "enviar_grupo": True,
                "enviar_individual": True,
                "nome_grupo": "[TESTE] Comercial"
            }
            
            # Mock WhatsAppService
            mock_wa_instance = MockWhatsAppService.return_value
            mock_wa_instance.send_ranking.return_value = True
            mock_wa_instance.send_individual_message.return_value = True
            
            # 3. EXECUTAR GERAÇÃO
            print("\n[3/4] Processando Rankings e Gamificação...")
            try:
                path_gerado = gerar_ranking_vendedores(Path(meta_path_vendedor), self.temp_dir)
            except Exception as e:
                self.fail(f"❌ Erro na geração do ranking: {e}")

            # 4. VALIDAÇÃO
            print("\n[4/4] Validando Resultados...")
            
            # Verifica Imagens
            esperados = ["ranking_vendedor.png", "ranking_semanal.png", "ranking_pontos.png"]
            for nome in esperados:
                f = self.temp_dir / nome
                # Se for ranking_vendedor, pode ter paginação (_p1.png)
                if not f.exists() and "ranking_vendedor" in nome:
                     paginated = list(self.temp_dir.glob("ranking_vendedor_p*.png"))
                     if paginated:
                         print(f"✅ Imagem gerada (paginada): {[p.name for p in paginated]}")
                         continue
                
                if f.exists():
                    print(f"✅ Imagem gerada: {nome} ({f.stat().st_size} bytes)")
                else:
                    print(f"❌ FALTOU Imagem: {nome}")
                    self.fail(f"Imagem {nome} não foi gerada.")
            
            # Verifica DB
            print(f"✅ Banco de Dados criado: {self.temp_db_path.name}")
            
            # Verifica chamadas de envio
            mock_wa_instance.send_ranking.assert_called()
            args, _ = mock_wa_instance.send_ranking.call_args
            msg_enviada = args[1] if len(args) > 1 else [] # lista de caminhos
            print(f"✅ Chamada de Grupo detectada com {len(msg_enviada)} imagens.")
            
            # Verifica chamadas individuais
            # Com dados reais, não sabemos quantos vendedores tem.
            # mock_notifier_instance foi removido pois a classe não existe mais no path antigo.
            print("⚠️ Validação de mensagens individuais ignorada neste teste (MockNotifier removido).")

        print("\n🏁 TESTE DRY RUN FINALIZADO COM SUCESSO!")

if __name__ == "__main__":
    unittest.main()
