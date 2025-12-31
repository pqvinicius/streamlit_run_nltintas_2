
import sys
import os
from datetime import date
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from src.feriados import FeriadosManager

def main():
    mgr = FeriadosManager()
    
    # Week of Dec 29, 2025
    start_date = date(2025, 12, 29) # Monday
    end_date = date(2026, 1, 3)     # Saturday
    
    # Check for specific dates
    jan1 = date(2026, 1, 1)
    
    print(f"Checking period: {start_date} to {end_date}")
    
    # Check Jan 1st
    is_holiday = mgr.eh_feriado(jan1, "TODAS")
    print(f"Is 2026-01-01 a holiday (TODAS)? {is_holiday}")
    
    # Calculate working days
    days = mgr.calcular_dias_uteis_periodo(start_date, end_date, "TODAS")
    print(f"Working days in period: {days}")
    
    # Detailed breakdown
    curr = start_date
    print("\nBreakdown:")
    total = 0.0
    from datetime import timedelta
    while curr <= end_date:
        wd = curr.weekday()
        day_val = 0.0
        is_hol = mgr.eh_feriado(curr, "TODAS")
        
        if not is_hol:
            if curr.month == 12 and curr.day == 31:
                day_val = 0.5
                print(f"{curr} (Wed 31/12): {day_val} (Special 0.5)")
            elif wd < 5:
                day_val = 1.0
                print(f"{curr} (Weekday): {day_val}")
            elif wd == 5:
                day_val = 0.5
                print(f"{curr} (Saturday): {day_val}")
        else:
            print(f"{curr} (Holiday): 0.0")
            
        total += day_val
        curr += timedelta(days=1)
        
    print(f"Calculated Total Breakdown: {total}")

if __name__ == "__main__":
    main()
