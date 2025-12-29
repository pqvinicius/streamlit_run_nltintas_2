import shutil
import os
import glob
from datetime import datetime
from pathlib import Path
from src.logger import get_logger

logger = get_logger(__name__)

class BackupManager:
    """
    Gerencia backups automáticos de arquivos críticos (DBs).
    Faz backup em pasta datada E junto do arquivo original (diário).
    """
    
    def __init__(self, backup_dir: str = "backups", retention_days: int = 7):
        self.backup_dir = Path(backup_dir)
        self.retention_days = retention_days

    def perform_backup(self, files_to_backup: list[Path | str]) -> bool:
        """
        Realiza backup dos arquivos listados:
        1. Para pasta datada (backups/YYYY-MM-DD/)
        2. Junto do arquivo original (arquivo.db.backup) - backup diário
        """
        timestamp = datetime.now().strftime("%Y-%m-%d")
        dest_folder = self.backup_dir / timestamp
        
        try:
            dest_folder.mkdir(parents=True, exist_ok=True)
            
            count = 0
            for src_file in files_to_backup:
                src = Path(src_file)
                if src.exists():
                    # 1. Backup para pasta datada
                    shutil.copy2(src, dest_folder / src.name)
                    
                    # 2. Backup diário junto do arquivo original
                    backup_original = src.parent / f"{src.name}.backup"
                    shutil.copy2(src, backup_original)
                    logger.debug(f"BACKUP | Backup diário criado: {backup_original.name}")
                    
                    count += 1
                    logger.debug(f"BACKUP | Arquivo salvo: {src.name}")
                else:
                    logger.warning(f"BACKUP | Arquivo não encontrado para backup: {src}")

            if count > 0:
                logger.info(f"BACKUP | Backup diário realizado em: {dest_folder} ({count} arquivos)")
                logger.info(f"BACKUP | Backups locais criados junto dos arquivos originais")
                self._clean_old_backups()
                return True
            return False

        except Exception as e:
            logger.error(f"BACKUP | Falha crítica no backup: {e}")
            return False

    def _clean_old_backups(self):
        """
        Mantém apenas os últimos N backups (dias).
        """
        try:
            # Lista subpastas (YYYY-MM-DD)
            subfolders = sorted(
                [f for f in self.backup_dir.iterdir() if f.is_dir()],
                key=os.path.getmtime
            )
            
            if len(subfolders) > self.retention_days:
                to_remove = len(subfolders) - self.retention_days
                for i in range(to_remove):
                    folder_to_del = subfolders[i]
                    shutil.rmtree(folder_to_del)
                    logger.info(f"BACKUP | Rotação: Backup antigo removido ({folder_to_del.name})")

        except Exception as e:
            logger.warning(f"BACKUP | Falha na rotação de backups antigos: {e}")
