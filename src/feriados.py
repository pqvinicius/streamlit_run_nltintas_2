import pandas as pd
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
import logging
import sys
from src.config import get_base_dir

logger = logging.getLogger(__name__)

class FeriadosManager:
    def __init__(self):
        self.feriados_df = self._carregar_feriados()
        
    def _carregar_feriados(self) -> pd.DataFrame:
        candidates = [
            get_base_dir() / "data" / "feriados.csv",
            Path.cwd() / "data" / "feriados.csv",
            Path(sys.executable).parent / "data" / "feriados.csv" if getattr(sys, "frozen", False) else None,
        ]
        
        path = None
        for candidate in candidates:
            if candidate and candidate.exists():
                path = candidate
                break
        
        if not path:
            logger.warning(f"Arquivo de feriados não encontrado em nenhum local: {[str(c) for c in candidates if c]}")
            return pd.DataFrame(columns=["loja", "data", "tipo"])
            
        try:
            df = pd.read_csv(path)
            # Normalizar datas para datetime.date
            df["data"] = pd.to_datetime(df["data"], errors="coerce").dt.date
            return df
        except Exception as e:
            logger.error(f"Erro ao carregar feriados de {path}: {e}")
            return pd.DataFrame(columns=["loja", "data", "tipo"])

    def eh_feriado(self, data: date, loja: str) -> bool:
        """
        Verifica se é feriado para uma loja específica.
        Considera feriados NACIONAIS ("TODAS") e feriados da LOJA.
        """
        if self.feriados_df.empty:
            return False
            
        # Filtra feriados do dia
        feriados_dia = self.feriados_df[self.feriados_df["data"] == data]
        
        if feriados_dia.empty:
            return False
            
        # Verifica Nacional
        if "TODAS" in feriados_dia["loja"].values:
            return True
            
        # Verifica Loja Específica (converter loja para str para garantir match)
        loja_str = str(loja).strip()
        # Tenta match exato ou numérico (ex: 14 vs "14")
        match = feriados_dia[feriados_dia["loja"].astype(str) == loja_str]
        
        return not match.empty

    def calcular_dias_uteis_periodo(self, data_inicio: date, data_fim: date, loja: str) -> float:
        """
        Calcula dias úteis num período para uma loja.
        Pesos:
        - Seg-Sex: 1.0 (se não for feriado)
        - Sábado: 0.5 (se não for feriado)
        - Domingo: 0.0
        """
        dias_uteis = 0.0
        curr = data_inicio
        while curr <= data_fim:
            # Se for feriado (Nacional ou Loja), conta 0
            if not self.eh_feriado(curr, loja):
                wd = curr.weekday()
                
                # Regra Customizada: 31/12 vale 0.5 (Reveillon)
                if curr.month == 12 and curr.day == 31:
                    dias_uteis += 0.5
                elif wd < 5: # Seg-Sex
                    dias_uteis += 1.0
                elif wd == 5: # Sábado
                    dias_uteis += 0.5
                # Domingo (6) ignora
            curr += timedelta(days=1)
            
        return dias_uteis
