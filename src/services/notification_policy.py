import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Set

class NotificationPolicy:
    """
    Centraliza a lógica de decisão de envios do WhatsApp (Grupo e Individual).
    Garante idempotência usando um arquivo JSON de histórico.
    """
    
    def __init__(self, history_file: Optional[Path] = None):
        if history_file is None:
            from src.config import get_paths
            self.history_file = Path(get_paths()["data_dir"]) / "notification_history.json"
        else:
            self.history_file = history_file
            
        self.logger = logging.getLogger("NotificationPolicy")
        self._history = self._load_history()

    def _load_history(self) -> Dict:
        if not self.history_file.exists():
            return {"group": {}, "individual": {}}
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Erro ao carregar histórico (corrompido?): {e}")
            try:
                backup = self.history_file.with_suffix(".corrupted")
                self.history_file.rename(backup)
                self.logger.warning(f"Arquivo corrompido renomeado para {backup.name}. Iniciando novo histórico.")
            except:
                pass
            return {"group": {}, "individual": {}}

    def _save_history(self):
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self._history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Erro ao salvar histórico: {e}")

    # --- LÓGICA DE GRUPO (RANKINGS) ---

    def deve_enviar_ranking_diario(self, now: datetime) -> Optional[str]:
        """
        Retorna o turno ('M' ou 'T') se deve enviar, ou None.
        Janelas: M (10-12), T (16-19).
        """
        hour = now.hour
        shift = None
        if 10 <= hour < 12:
            shift = "M"
        elif 16 <= hour < 19:
            shift = "T"
            
        if not shift:
            return None
            
        day_str = now.strftime("%Y-%m-%d")
        daily_history = self._history.get("group", {}).get("daily", {})
        
        sent_today = daily_history.get(day_str, [])
        if shift in sent_today:
            return None
            
        return shift

    def registrar_envio_diario(self, now: datetime, shift: str):
        day_str = now.strftime("%Y-%m-%d")
        if "group" not in self._history: self._history["group"] = {}
        if "daily" not in self._history["group"]: self._history["group"]["daily"] = {}
        
        if day_str not in self._history["group"]["daily"]:
            self._history["group"]["daily"][day_str] = []
            
        if shift not in self._history["group"]["daily"][day_str]:
            self._history["group"]["daily"][day_str].append(shift)
            self._save_history()

    def deve_enviar_ranking_semanal(self, now: datetime) -> bool:
        """Sexta-feira, uma vez por semana ISO."""
        if now.weekday() != 4: # Friday
            return False
        return self._check_weekly_idempotency("weekly", now)

    def deve_enviar_ranking_mensal(self, now: datetime) -> bool:
        """
        Quarta-feira, uma vez por semana ISO.
        Nota: 'Weekly snapshot of monthly performance'.
        """
        if now.weekday() != 2: # Wednesday
            return False
        return self._check_weekly_idempotency("monthly", now)

    def deve_enviar_ranking_pontos(self, now: datetime) -> bool:
        """Segunda-feira, uma vez por semana ISO."""
        if now.weekday() != 0: # Monday
            return False
        return self._check_weekly_idempotency("points", now)

    def _check_weekly_idempotency(self, key: str, now: datetime) -> bool:
        iso_week = now.strftime("%G-W%V") # Ex: 2025-W02
        group_history = self._history.get("group", {}).get(key, {})
        return not group_history.get(iso_week, False)

    def registrar_envio_semanal(self, key: str, now: datetime):
        iso_week = now.strftime("%G-W%V")
        if "group" not in self._history: self._history["group"] = {}
        if key not in self._history["group"]: self._history["group"][key] = {}
        self._history["group"][key][iso_week] = True
        self._save_history()

    # --- LÓGICA INDIVIDUAL (CONQUISTAS) ---

    def deve_enviar_mensagem_individual(self, vendedor: str, now: datetime, conquistas_atuais: List[str]) -> bool:
        """
        Decide o envio baseado em evolução (set logic).
        Ignora ordem e duplicidade de nomes.
        """
        if not conquistas_atuais:
            return False
            
        vendedor = vendedor.strip().upper()
        day_str = now.strftime("%Y-%m-%d")
        ind_history = self._history.get("individual", {}).get(vendedor, {}).get(day_str, [])
        
        set_atuais = set(conquistas_atuais)
        set_notificadas = set(ind_history)
        
        novas = set_atuais - set_notificadas
        if novas:
            self.logger.info(f"Envio individual autorizado para {vendedor} em {day_str}: {novas}")
            return True
            
        return False

    def registrar_envio_individual(self, vendedor: str, now: datetime, conquistas_notificadas: List[str]):
        vendedor = vendedor.strip().upper()
        day_str = now.strftime("%Y-%m-%d")
        if "individual" not in self._history: self._history["individual"] = {}
        if vendedor not in self._history["individual"]: self._history["individual"][vendedor] = {}
        
        # Persiste a lista completa do dia (ordenada para facilitar leitura)
        self._history["individual"][vendedor][day_str] = sorted(list(set(conquistas_notificadas)))
        self._save_history()

    def gerar_mensagem_conquista(self, vendedor: str, conquistas_atuais: List[str], pontuacao_atual: int) -> str:
        """Gera mensagem curta e objetiva com as conquistas do dia."""
        conquistas_str = " e ".join(sorted(conquistas_atuais))
        return (
            f"🌟 *PARABÉNS, {vendedor.upper()}!* 🌟\n\n"
            f"Você conquistou o troféu de *{conquistas_str}* hoje!\n"
            f"Sua pontuação acumulada nas Olimpíadas é de *{pontuacao_atual} pontos*.\n\n"
            f"Continue acelerando! 🚀"
        )
