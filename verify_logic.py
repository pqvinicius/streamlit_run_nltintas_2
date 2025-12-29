import pandas as pd
from datetime import date, timedelta
from src.feriados import FeriadosManager

def simular_calculo(nome_loja, id_loja, data_ref, meta_mensal_simulada):
    print(f"\n--- SIMULAÇÃO: {nome_loja} (Loja {id_loja}) ---")
    
    # 1. Configurações
    dias_uteis_base_config = 22 # Simula config.ini
    feriados_mgr = FeriadosManager()
    
    # 2. Definição da Semana (Segunda a Sábado)
    dt_segunda = data_ref - timedelta(days=data_ref.weekday()) # 16/03/2026
    dt_sabado = dt_segunda + timedelta(days=5) # 21/03/2026
    print(f"Semana de Referência: {dt_segunda} a {dt_sabado}")
    
    # 3. Definição do Mês (Para contar feriados municipais)
    data_inicio_mes = dt_segunda.replace(day=1)
    data_fim_mes = (data_inicio_mes + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    # -----------------------------------------------------
    # PASSO A: Calcular Dias Úteis do Mês Ajustado
    # -----------------------------------------------------
    qtd_feriados_municipais = 0
    curr = data_inicio_mes
    log_feriados = []
    while curr <= data_fim_mes:
        is_feriado_loja = feriados_mgr.eh_feriado(curr, str(id_loja))
        is_feriado_nacional = feriados_mgr.eh_feriado(curr, "TODAS")
        
        if is_feriado_loja and not is_feriado_nacional:
            if curr.weekday() < 6: # Se cair em dia útil
                qtd_feriados_municipais += 1
                log_feriados.append(f"{curr} (Mun)")
        elif is_feriado_nacional:
             log_feriados.append(f"{curr} (Nac - Já descontado da base)")
             
        curr += timedelta(days=1)
        
    dias_uteis_mes_ajustado = max(dias_uteis_base_config - qtd_feriados_municipais, 1)
    
    print(f"Config Dias Úteis Base: {dias_uteis_base_config}")
    print(f"Feriados Municipais no Mês: {qtd_feriados_municipais} {log_feriados}")
    print(f"Dias Úteis Mês Ajustado: {dias_uteis_mes_ajustado}")
    
    meta_diaria = meta_mensal_simulada / dias_uteis_mes_ajustado
    print(f"Meta Diária Calculada: R$ {meta_diaria:,.2f}")

    # -----------------------------------------------------
    # PASSO B: Calcular Dias Úteis da Semana
    # -----------------------------------------------------
    dias_uteis_semana = 0.0
    curr = dt_segunda
    detalhe_semana = []
    
    while curr <= dt_sabado:
        peso = 0.0
        obs = ""
        if not feriados_mgr.eh_feriado(curr, str(id_loja)):
            if curr.weekday() < 5: # Seg-Sex
                peso = 1.0
            elif curr.weekday() == 5: # Sab
                peso = 0.5
        else:
            obs = "FERIADO"
            
        dias_uteis_semana += peso
        detalhe_semana.append(f"{curr.strftime('%a')}: {peso} {obs}")
        curr += timedelta(days=1)
        
    print(f"Dias Úteis Semana (Calculado): {dias_uteis_semana}")
    print(f"Detalhe: { ' | '.join(detalhe_semana) }")
    
    # -----------------------------------------------------
    # PASSO C: Meta Semanal Final
    # -----------------------------------------------------
    meta_semanal = meta_diaria * dias_uteis_semana
    print(f"META SEMANAL FINAL: R$ {meta_semanal:,.2f}")

# Execução
# Data simulada: 20/03/2026 (Sexta) - Semana do feriado de 19/03 (Itaperuna)
data_simulacao = date(2026, 3, 20)
meta_exemplo = 22000.00

# Loja 15 (Itaperuna): Tem feriado municipal 19/03
simular_calculo("LOJA COM FERIADO (Itaperuna)", 15, data_simulacao, meta_exemplo)

# Loja 32 (Leopoldina): NÃO tem feriado nesta semana
simular_calculo("LOJA SEM FERIADO (Leopoldina)", 32, data_simulacao, meta_exemplo)
