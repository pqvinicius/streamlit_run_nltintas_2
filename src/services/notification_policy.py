import logging
import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import List, Dict, Optional, Any

class NotificationPolicy:
    """
    Centraliza a lógica de decisão de envios do WhatsApp (Grupo e Individual).
    Garante idempotência usando uma tabela SQLite (notificacoes_enviadas).
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            from src.config import get_paths
            self.db_path = Path(get_paths()["data_dir"]) / "gamificacao_vendedores.db"
        else:
            self.db_path = db_path
            
        self.logger = logging.getLogger("NotificationPolicy")

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    # --- LÓGICA DE GRUPO (RANKINGS) ---

    def deve_enviar_ranking_diario(self, now: datetime) -> Optional[str]:
        """
        Retorna o turno ('M' ou 'T') se deve enviar, ou None.
        Janelas: M (10-14), T (16-20).
        """
        hour = now.hour
        shift = None
        if 10 <= hour < 14:
            shift = "M"
        elif 16 <= hour < 20:
            shift = "T"
            
        if not shift:
            return None
            
        day_str = now.strftime("%Y-%m-%d")
        ref = f"{day_str}_{shift}"
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM notificacoes_enviadas 
                WHERE vendedor_nome = 'GRUPO' 
                  AND tipo = 'RANKING_DIARIO' 
                  AND referencia = ?
                  AND data_envio = ?
            """, (ref, day_str))
            if cursor.fetchone():
                return None
                
        return shift

    def registrar_envio_diario(self, now: datetime, shift: str):
        day_str = now.strftime("%Y-%m-%d")
        hora_str = now.strftime("%H:%M:%S")
        ref = f"{day_str}_{shift}"
        
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO notificacoes_enviadas 
                (vendedor_nome, tipo, referencia, data_envio, hora_envio)
                VALUES (?, ?, ?, ?, ?)
            """, ('GRUPO', 'RANKING_DIARIO', ref, day_str, hora_str))

    def deve_enviar_ranking_semanal(self, now: datetime) -> bool:
        """Sexta-feira, uma vez por semana ISO."""
        if now.weekday() != 4: # Friday
            return False
        return self._check_weekly_idempotency("weekly", now)

    def deve_enviar_ranking_mensal(self, now: datetime) -> bool:
        """Quarta-feira, uma vez por semana ISO."""
        if now.weekday() != 2: # Wednesday
            return False
        return self._check_weekly_idempotency("monthly", now)

    def deve_enviar_ranking_pontos(self, now: datetime) -> bool:
        """Segunda-feira, uma vez por semana ISO."""
        if now.weekday() != 0: # Monday
            return False
        return self._check_weekly_idempotency("points", now)

    def _check_weekly_idempotency(self, key: str, now: datetime) -> bool:
        """Verifica se um ranking especial já foi enviado nesta semana ISO."""
        tipo_map = {
            "weekly": "RANKING_SEMANAL",
            "monthly": "RANKING_MENSAL",
            "points": "RANKING_PONTOS"
        }
        tipo = tipo_map.get(key, key.upper())
        iso_week = now.strftime("%G-W%V") # Ex: 2025-W02
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 1 FROM notificacoes_enviadas 
                WHERE vendedor_nome = 'GRUPO' 
                  AND tipo = ? 
                  AND referencia = ?
            """, (tipo, iso_week))
            return not cursor.fetchone()

    def registrar_envio_semanal(self, key: str, now: datetime):
        # Mapear chaves legadas para os novos tipos de banco
        tipo_map = {
            "weekly": "RANKING_SEMANAL",
            "monthly": "RANKING_MENSAL",
            "points": "RANKING_PONTOS"
        }
        tipo = tipo_map.get(key, key.upper())
        iso_week = now.strftime("%G-W%V")
        day_str = now.strftime("%Y-%m-%d")
        hora_str = now.strftime("%H:%M:%S")

        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO notificacoes_enviadas 
                (vendedor_nome, tipo, referencia, data_envio, hora_envio)
                VALUES (?, ?, ?, ?, ?)
            """, ('GRUPO', tipo, iso_week, day_str, hora_str))

    def hoje_tem_ranking_especial(self, now: datetime) -> Optional[str]:
        wd = now.weekday()
        if wd == 0: return "points"
        if wd == 2: return "monthly"
        if wd == 4: return "weekly"
        return None

    # --- LÓGICA INDIVIDUAL (CONQUISTAS) ---

    def deve_enviar_mensagem_individual(self, vendedor: str, now: datetime, conquistas_atuais: List[str]) -> bool:
        """
        Decide o envio baseado em evolução.
        Busca a última referência enviada hoje para este vendedor.
        """
        if not conquistas_atuais:
            return False
            
        vendedor = vendedor.strip().upper()
        day_str = now.strftime("%Y-%m-%d")
        ref_atual = "+".join(sorted(list(set(conquistas_atuais))))
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Busca a última notificação do dia
            cursor.execute("""
                SELECT referencia FROM notificacoes_enviadas 
                WHERE vendedor_nome = ? 
                  AND tipo = 'CONQUISTA_INDIVIDUAL' 
                  AND data_envio = ?
                ORDER BY id DESC LIMIT 1
            """, (vendedor, day_str))
            
            row = cursor.fetchone()
            if row:
                last_ref = row[0]
                if last_ref == ref_atual:
                    return False # Nenhuma mudança em relação ao que já foi enviado hoje
            
            self.logger.info(f"Envio individual autorizado para {vendedor}: {ref_atual} (Anterior: {row[0] if row else 'Nenhum'})")
            return True

    def registrar_envio_individual(self, vendedor: str, now: datetime, conquistas_notificadas: List[str]):
        vendedor = vendedor.strip().upper()
        day_str = now.strftime("%Y-%m-%d")
        hora_str = now.strftime("%H:%M:%S")
        ref = "+".join(sorted(list(set(conquistas_notificadas))))
        
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO notificacoes_enviadas 
                (vendedor_nome, tipo, referencia, data_envio, hora_envio)
                VALUES (?, ?, ?, ?, ?)
            """, (vendedor, 'CONQUISTA_INDIVIDUAL', ref, day_str, hora_str))

    def gerar_mensagem_conquista(self, vendedor: str, conquistas_atuais: List[str], pontuacao_atual: int) -> str:
        conquistas_str = " e ".join(sorted(conquistas_atuais))
        return (
            f"🌟 *PARABÉNS, {vendedor.upper()}!* 🌟\n\n"
            f"Você conquistou o troféu de *{conquistas_str}* hoje!\n"
            f"Sua pontuação acumulada nas Olimpíadas é de *{pontuacao_atual} pontos*.\n\n"
            f"Continue acelerando! 🚀"
        )
