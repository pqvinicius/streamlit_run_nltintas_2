"""
Serviço de cálculo de períodos comerciais.
Gerencia lógica de mês comercial e períodos.
"""
from datetime import date, timedelta
from typing import Dict, Tuple

from dashboard.config.settings import get_mes_comercial_config


class PeriodService:
    """Serviço para cálculos de períodos comerciais."""
    
    def __init__(self):
        self._mes_config: Dict[str, int] = {}
    
    @property
    def mes_config(self) -> Dict[str, int]:
        """Configuração do mês comercial (cacheado)."""
        if not self._mes_config:
            self._mes_config = get_mes_comercial_config()
        return self._mes_config
    
    def get_periodo_mes_comercial(
        self, 
        data_atual: date
    ) -> Tuple[date, date]:
        """
        Retorna o período do mês comercial: dia_inicio até a data atual.
        
        Args:
            data_atual: Data de referência.
        
        Returns:
            Tupla (inicio_ciclo, fim_ciclo) onde:
            - inicio_ciclo: Dia 26 do mês anterior (ou mês atual se já passou do dia 26)
            - fim_ciclo: data_atual
        """
        dia_inicio = self.mes_config["dia_inicio"]
        dia_fim = self.mes_config["dia_fim"]
        
        if data_atual.day <= dia_fim:
            # Estamos no final do ciclo (ex: dia 25/Jan). Início foi 26/Dez.
            mes_anterior = (data_atual.replace(day=1) - timedelta(days=1))
            inicio_ciclo = mes_anterior.replace(day=dia_inicio)
        else:
            # Estamos após o dia 25, então o ciclo começou no dia 26 do mês atual
            if data_atual.day >= dia_inicio:
                inicio_ciclo = data_atual.replace(day=dia_inicio)
            else:
                # Entre dia 1 e dia 25, ciclo começou no dia 26 do mês anterior
                mes_anterior = (data_atual.replace(day=1) - timedelta(days=1))
                inicio_ciclo = mes_anterior.replace(day=dia_inicio)
        
        return inicio_ciclo, data_atual
    
    def get_current_month_range(self) -> Tuple[str, str]:
        """
        Retorna o período do mês comercial atual (dia 26 até hoje).
        
        Returns:
            Tupla (inicio_str, fim_str) no formato YYYY-MM-DD.
        """
        today = date.today()
        inicio_ciclo, fim_ciclo = self.get_periodo_mes_comercial(today)
        return inicio_ciclo.strftime("%Y-%m-%d"), fim_ciclo.strftime("%Y-%m-%d")
    
    def clear_cache(self):
        """Limpa o cache de configurações."""
        self._mes_config = {}

