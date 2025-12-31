
import sqlite3
import logging
from pathlib import Path
from datetime import date, timedelta
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from src.gamificacao_vendedores import GamificacaoDB, get_periodo_semana
from src.feriados import FeriadosManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_metas_semanais():
    # 1. Identify current week (ref: Dec 31, 2025)
    ref_date = date(2025, 12, 31)
    iso_year, iso_week, _ = ref_date.isocalendar()
    semana_uuid = f"{iso_year}_W{iso_week}" # Should be 2026_W01
    
    print(f"--- Correction for Week: {semana_uuid} (Ref: {ref_date}) ---")
    
    db = GamificacaoDB()
    feriados_mgr = FeriadosManager()
    
    conn = db._get_connection()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 2. Get all metas for this week
    cursor.execute("""
        SELECT ms.id, ms.vendedor_nome, ms.meta_valor, ms.data_inicio, ms.data_fim, v.loja
        FROM metas_semanais ms
        LEFT JOIN vendedores v ON ms.vendedor_nome = v.nome
        WHERE ms.semana_uuid = ?
    """, (semana_uuid,))
    
    rows = cursor.fetchall()
    
    print(f"Found {len(rows)} entries to check.")
    
    updates = 0
    
    for row in rows:
        nome = row['vendedor_nome']
        current_meta = row['meta_valor']
        loja = row['loja'] or ""
        
        # 3. Calculate CORRECT Meta Total
        # Start and End of the week
        dt_inicio = date.fromisoformat(row['data_inicio'])
        dt_fim = date.fromisoformat(row['data_fim']) # Usually Saturday
        
        # Get Reference Daily Meta (needs to fetch from daily results to be accurate)
        # We assume the meta registered is based on 5.5 days.
        # So Daily Meta = current_meta / 5.5
        
        # BUT better to fetch from results table to be sure
        cursor_temp = conn.cursor()
        cursor_temp.execute("""
            SELECT MAX(meta) 
            FROM resultado_meta 
            WHERE vendedor_nome = ? AND data BETWEEN ? AND ?
        """, (nome, dt_inicio, dt_fim))
        res_meta = cursor_temp.fetchone()
        
        if res_meta and res_meta[0] and res_meta[0] > 0:
            meta_diaria = res_meta[0]
            
            # Calculate Correct Working Days
            du_total = feriados_mgr.calcular_dias_uteis_periodo(dt_inicio, dt_fim, loja)
            
            new_meta_total = meta_diaria * du_total
            
            # Update if different
            if abs(new_meta_total - current_meta) > 0.01:
                print(f"UPDATING {nome}: Old={current_meta:.2f} -> New={new_meta_total:.2f} (Dias Uteis: {du_total}, Meta Diario: {meta_diaria:.2f})")
                
                cursor.execute("""
                    UPDATE metas_semanais
                    SET meta_valor = ?
                    WHERE id = ?
                """, (new_meta_total, row['id']))
                updates += 1
            else:
                print(f"Skipping {nome}: Value matches ({current_meta:.2f})")
        else:
            print(f"Skipping {nome}: Could not find daily meta reference.")

    conn.commit()
    conn.close()
    
    print(f"\nCorrection Complete. {updates} rows updated.")

if __name__ == "__main__":
    fix_metas_semanais()
