import argparse
import sys
import traceback
import time
from datetime import datetime

import pandas as pd
from pathlib import Path

# === GOVERNANÇA: LOGGING SINGLETON ===
from src.logger import get_logger
from src.governance.execution_logger import ExecutionLogger

# Imports essenciais
from src.web_automation import executar_web_automation
from src.config import get_paths, get_base_dir
from src.daily_seller_ranking import gerar_ranking_vendedores

# Configura logger singleton para uso GLOBAL
logger = get_logger()

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fluxo BI CITEL - Ranking & Gamificação de Vendedores")
    parser.add_argument("--meta-arquivo", type=Path, help="Usa um arquivo Meta já existente no disco.")
    parser.add_argument("--force", action="store_true", default=True, help="Sobrescreve arquivos (Padrão).")
    parser.add_argument("--no-force", dest="force", action="store_false", help="Não sobrescreve arquivos.")
    parser.add_argument("--no-whatsapp", action="store_true", help="Desabilita envio via WhatsApp.")
    return parser.parse_args()


def _run_ranking_diario(
    meta_arquivo: Path | None, 
    paths_cfg: dict[str, str], 
    force: bool, 
    send_whatsapp: bool, 
    exec_log: ExecutionLogger
) -> None:
    base_dir = get_base_dir()
    data_cfg = paths_cfg.get("data_dir")
    data_dir = Path(data_cfg) if data_cfg else base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    
    meta_vendedor = None
    
    # 1. INGESTAO
    # 1. INGESTAO COM RETRY DE BI
    try:
        if meta_arquivo is None:
            logger.info("INGESTAO | Iniciando download de planilhas...")
            
            max_tentativas = 3
            for tentativa in range(1, max_tentativas + 1):
                logger.info(f"INGESTAO | Tentativa {tentativa}/{max_tentativas}")
                
                # A. Executa Automação Web
                arquivos = executar_web_automation(
                    diretorio_destino=data_dir,
                    somente_meta_empresa=False, 
                    force_overwrite=force,
                )
                meta_vendedor = arquivos.get("meta_vendedor")
                
                # B. Valida Existência
                if not meta_vendedor or not meta_vendedor.exists():
                    logger.warning("INGESTAO | Download não gerou arquivo. Aguardando 40s...")
                    time.sleep(40)
                    continue

                # C. Valida Conteúdo (Sanity Check)
                logger.info("INGESTAO | Validando sanidade do arquivo...")
                try:
                    df_preview = pd.read_excel(meta_vendedor, header=None, nrows=5)
                    invalid_flag = False
                    for idx, row in df_preview.iterrows():
                        if any("ERRO AO RECUPERAR RESULTADOS" in str(cell).upper() for cell in row):
                            logger.error(f"INGESTAO | Excel inválido detectado (Linha {idx}): 'Erro ao recuperar resultados'")
                            logger.info("INGESTAO | Ação: Removendo arquivo e reiniciando ciclo de download.")
                            meta_vendedor.unlink(missing_ok=True)
                            invalid_flag = True
                            break
                    
                    if invalid_flag:
                        time.sleep(40)
                        continue # Volta para o BI
                        
                except Exception as e:
                    logger.warning(f"INGESTAO | Erro ao validar arquivo (pode ser corrompido): {e}")
                    # Se não abre, é inválido. Apaga e retry.
                    meta_vendedor.unlink(missing_ok=True)
                    time.sleep(40)
                    continue

                # Se chegou aqui, é VÁLIDO
                logger.info("INGESTAO | Arquivo válido e saneado. Prosseguindo.")
                exec_log.log("INGESTAO", "SUCCESS", message=f"Arquivo baixado e validado: {meta_vendedor.name}")
                break # Sai do loop de tentativas
            
            else:
                # Loop terminou sem break = Falha em todas as tentativas
                logger.error("INGESTAO | Falha após todas as tentativas de download.")
                
                # Fallback Cache (Último recurso)
                candidates = sorted(data_dir.glob(f"MetaVendedor_*.xlsx"), key=lambda p: p.stat().st_mtime, reverse=True)
                if candidates:
                    meta_vendedor = candidates[0]
                    msg = f"FALHA DOWNLOAD. Usando CACHE mais recente: {meta_vendedor.name}"
                    logger.warning(f"INGESTAO | {msg}")
                    exec_log.log("INGESTAO", "WARNING", message=msg)
                else:
                    msg = "Meta Vendedor não encontrado nem baixado (mesmo após retries)."
                    logger.error(f"INGESTAO | {msg}")
                    exec_log.log("INGESTAO", "FAIL", message=msg)
                    return

        else:
            meta_vendedor = meta_arquivo
            logger.info(f"INGESTAO | Usando arquivo manual: {meta_vendedor}")
            exec_log.log("INGESTAO", "SUCCESS", message="Arquivo manual utilizado")

    except Exception as e:
        logger.error(f"INGESTAO | Erro crítico no fluxo de ingestão: {e}")
        exec_log.log("INGESTAO", "FAIL", error_stack=traceback.format_exc())
        return

    # 2. PROCESSAMENTO E RANKING
    if meta_vendedor and meta_vendedor.exists():
        logger.info(f"PROCESSAMENTO | Iniciando processamento: {meta_vendedor.name}")
        try:
            # Passa a flag de WhatsApp explicitamente para o serviço
            destino_vendedor = gerar_ranking_vendedores(
                meta_vendedor, 
                data_dir, 
                send_whatsapp=send_whatsapp
            )
            
            if destino_vendedor:
                logger.info(f"RANKING | Sucesso! Gerado em: {destino_vendedor}")
                exec_log.log("RANKING", "SUCCESS", substep="ranking_vendedor", message=str(destino_vendedor))
            else:
                logger.warning("RANKING | Nenhum ranking gerado (vazio ou erro lógico).")
                exec_log.log("RANKING", "SKIPPED", message="Nenhum output gerado")
        except Exception as exc:
             logger.error("RANKING | Falha crítica ao gerar ranking.", exc_info=True)
             exec_log.log("RANKING", "FAIL", error_stack=traceback.format_exc())
    else:
        logger.error("PROCESSAMENTO | Arquivo alvo inexistente. Abortando.")
        exec_log.log("PROCESSAMENTO", "FAIL", message="Arquivo inesistente para processamento")


def main() -> None:
    """Função principal com Governança de Logs via ExecutionLogger."""
    
    # 1. Inicializa Execution Logger (SQLite)
    base_dir = get_base_dir()
    db_path = base_dir / "data" / "execution_log.db"
    gamification_db = base_dir / "data" / "gamificacao_vendedores.db"
    
    # === BACKUP AUTOMÁTICO ===
    try:
        from src.governance.backup_manager import BackupManager
        backuper = BackupManager(backup_dir=base_dir / "backups")
        backuper.perform_backup([db_path, gamification_db])
    except Exception as e:
        print(f"Erro no backup (prosseguindo): {e}")
    # =========================
    
    is_frozen = getattr(sys, "frozen", False)
    env = "PROD" if is_frozen else "DEV"
    
    exec_log = ExecutionLogger(db_path=db_path, environment=env, trigger_type="MANUAL")
    
    logger = get_logger(modo=env)
    
    args = _parse_args()
    logger.info(f"PIPELINE | INICIANDO EXECUCAO: {logger.name}")
    exec_log.log("PIPELINE", "STARTED", message=f"Modo: {env}")

    try:
        paths_cfg = get_paths()
        
        # Converte flag negativa para positiva (send_whatsapp)
        send_whatsapp = not args.no_whatsapp
        
        _run_ranking_diario(
            args.meta_arquivo, 
            paths_cfg, 
            args.force, 
            send_whatsapp, 
            exec_log
        )
        
        # === GIT SYNC (Bonus: Atualiza Streamlit Cloud) ===
        try:
            import subprocess
            logger.info("GIT SYNC | Sincronizando dados com o repositório...")
            # Adiciona DBs e Imagens
            subprocess.run(["git", "add", "data/*.db", "data/*.png"], capture_output=True)
            # Tenta commitar se houver mudanças
            commit_res = subprocess.run(["git", "commit", "-m", f"Auto-sync: {datetime.now():%d/%m/%Y %H:%M}"], capture_output=True)
            if commit_res.returncode == 0:
                logger.info("GIT SYNC | Mudanças detectadas, realizando push...")
                subprocess.run(["git", "push"], capture_output=True)
                logger.info("GIT SYNC | Sucesso!")
            else:
                logger.info("GIT SYNC | Sem mudanças para sincronizar.")
        except Exception as e:
            logger.warning(f"GIT SYNC | Falha ao sincronizar: {e}")
        # ==================================================
        
        logger.info("PIPELINE | Execucao finalizada com sucesso")
        exec_log.log("PIPELINE", "SUCCESS")
        
    except KeyboardInterrupt:
        logger.warning("PIPELINE | Interrompido pelo usuário.")
        exec_log.log("PIPELINE", "ABORTED", message="Ctrl+C User Interrupt")
        if is_frozen:
            time.sleep(2)
            
    except Exception as exc:
        logger.error("PIPELINE | ERRO FATAL NÃO TRATADO", exc_info=True)
        exec_log.log("PIPELINE", "CRITICAL", error_stack=traceback.format_exc())
        
        if is_frozen:
            time.sleep(3)
        sys.exit(1)


if __name__ == "__main__":
    main()
