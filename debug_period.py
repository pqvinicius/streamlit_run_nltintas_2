import sys
import os
from datetime import date

# Add current directory to sys.path so we can import dashboard packages
sys.path.append(os.getcwd())

try:
    from dashboard.services.period_service import PeriodService
    from dashboard.config.settings import get_mes_comercial_config

    print("--- DEBUG PERIOD SERVICE ---")
    ps = PeriodService()
    start, end = ps.get_current_month_range()
    
    print(f"Today: {date.today()}")
    print(f"Default Start Date: {start}")
    print(f"Default End Date:   {end}")
    
    mes_config = get_mes_comercial_config()
    print(f"Mes Config: {mes_config}")

except Exception as e:
    print(f"Error: {e}")
