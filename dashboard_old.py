import streamlit as st
import pandas as pd
import sqlite3
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

# --- CONFIG & THEME ---
st.set_page_config(page_title="Olimpíadas de Vendas", page_icon="🥇", layout="wide")

# Custom CSS for "Olympics" feel
st.markdown("""
<style>
    .big-font { font-size: 24px !important; font-weight: bold; }
    .gold { color: #FFD700; }
    .silver { color: #C0C0C0; }
    .bronze { color: #CD7F32; }
    .metric-card {
        background-color: #f8f9fa;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_GAMIFICACAO = DATA_DIR / "gamificacao_vendedores.db"

# --- HELPERS ---
def get_mes_comercial_config():
    """Lê configuração do mês comercial do config.ini"""
    try:
        from configparser import ConfigParser
        config_path = Path(__file__).parent / "config.ini"
        if not config_path.exists():
            return {"dia_inicio": 26, "dia_fim": 25}
        parser = ConfigParser()
        parser.read(config_path, encoding="utf-8")
        if not parser.has_section("mes_comercial"):
            return {"dia_inicio": 26, "dia_fim": 25}
        sec = parser["mes_comercial"]
        return {
            "dia_inicio": sec.getint("dia_inicio", fallback=26),
            "dia_fim": sec.getint("dia_fim", fallback=25),
        }
    except Exception:
        return {"dia_inicio": 26, "dia_fim": 25}

def get_periodo_mes_comercial(data_atual: date, mes_config: dict) -> tuple[date, date]:
    """
    Retorna o período do mês comercial: dia_inicio até a data atual.
    Usa cálculo dinâmico baseado em configuração (alinhado com o sistema).
    
    Args:
        data_atual: Data de referência
        mes_config: Dict com "dia_inicio" e "dia_fim" (ex: {"dia_inicio": 26, "dia_fim": 25})
        
    Returns:
        Tupla (inicio_ciclo, fim_ciclo) onde:
        - inicio_ciclo: Dia 26 do mês anterior (ou mês atual se já passou do dia 26)
        - fim_ciclo: data_atual
    """
    dia_inicio = mes_config["dia_inicio"]
    dia_fim = mes_config["dia_fim"]
    
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

def get_current_month_range():
    """
    Retorna o período do mês comercial atual (dia 26 até hoje).
    Alinhado com a lógica do sistema de ranking.
    """
    today = date.today()
    mes_config = get_mes_comercial_config()
    inicio_ciclo, fim_ciclo = get_periodo_mes_comercial(today, mes_config)
    return inicio_ciclo.strftime("%Y-%m-%d"), fim_ciclo.strftime("%Y-%m-%d")

@st.cache_data(ttl=60)
def load_medal_table(start_date: str, end_date: str):
    if not DB_GAMIFICACAO.exists(): return pd.DataFrame()
    
    # Query Olímpica
    query = """
        SELECT 
            v.nome AS Vendedor, 
            COALESCE(SUM(t.pontos), 0) AS Pontos,
            COALESCE(SUM(CASE WHEN t.tipo_trofeu = 'OURO' THEN 1 ELSE 0 END), 0) AS Ouro,
            COALESCE(SUM(CASE WHEN t.tipo_trofeu = 'PRATA' THEN 1 ELSE 0 END), 0) AS Prata,
            COALESCE(SUM(CASE WHEN t.tipo_trofeu = 'BRONZE' THEN 1 ELSE 0 END), 0) AS Bronze
        FROM vendedores v
        LEFT JOIN trofeus t 
            ON v.nome = t.vendedor_nome 
            AND t.data_conquista >= ?
        WHERE v.ativo = 1 AND v.tipo != 'GERENTE'
        GROUP BY v.nome
        ORDER BY Pontos DESC, Ouro DESC, Prata DESC, Bronze DESC
    """
    
    try:
        con = sqlite3.connect(f"file:{DB_GAMIFICACAO}?mode=ro", uri=True)
        df = pd.read_sql(query, con, params=[start_date])
        con.close()
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=60)
def load_athlete_history(vendedor: str):
    if not DB_GAMIFICACAO.exists(): return pd.DataFrame()
    
    query = """
        SELECT 
            data_conquista, 
            tipo_trofeu, 
            pontos 
        FROM trofeus 
        WHERE vendedor_nome = ? 
        ORDER BY data_conquista DESC
    """
    try:
        con = sqlite3.connect(f"file:{DB_GAMIFICACAO}?mode=ro", uri=True)
        df = pd.read_sql(query, con, params=[vendedor])
        con.close()
        return df
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=60)
def load_conquistas_por_semana(vendedor: str):
    """
    Carrega conquistas agrupadas por semana para um vendedor.
    Retorna DataFrame com: semana_uuid, data_inicio, data_fim, total_pontos, ouro, prata, bronze
    """
    if not DB_GAMIFICACAO.exists(): 
        return pd.DataFrame()
    
    query = """
        SELECT 
            data_conquista,
            tipo_trofeu,
            pontos
        FROM trofeus 
        WHERE vendedor_nome = ? 
        ORDER BY data_conquista DESC
    """
    try:
        con = sqlite3.connect(f"file:{DB_GAMIFICACAO}?mode=ro", uri=True)
        df = pd.read_sql(query, con, params=[vendedor])
        con.close()
        
        if df.empty:
            return pd.DataFrame()
        
        # Converte data_conquista para datetime
        df['data_conquista'] = pd.to_datetime(df['data_conquista'])
        
        # Calcula semana ISO (segunda a domingo, mas consideramos segunda a sábado)
        # Ajusta para que segunda-feira seja o início da semana
        df['ano'] = df['data_conquista'].dt.isocalendar().year
        df['semana'] = df['data_conquista'].dt.isocalendar().week
        
        # Calcula segunda-feira da semana
        df['data_semana'] = df['data_conquista'].dt.to_period('W-MON').dt.start_time
        
        # Agrupa por semana
        resumo = df.groupby(['ano', 'semana', 'data_semana']).agg({
            'pontos': 'sum',
            'tipo_trofeu': lambda x: {
                'OURO': (x == 'OURO').sum(),
                'PRATA': (x == 'PRATA').sum(),
                'BRONZE': (x == 'BRONZE').sum(),
                'BONUS_1': (x == 'BONUS_1').sum(),
                'BONUS_2': (x == 'BONUS_2').sum()
            }
        }).reset_index()
        
        # Expande o dicionário de medalhas em colunas
        resumo['ouro'] = resumo['tipo_trofeu'].apply(lambda x: x.get('OURO', 0))
        resumo['prata'] = resumo['tipo_trofeu'].apply(lambda x: x.get('PRATA', 0))
        resumo['bronze'] = resumo['tipo_trofeu'].apply(lambda x: x.get('BRONZE', 0))
        resumo['bonus_1'] = resumo['tipo_trofeu'].apply(lambda x: x.get('BONUS_1', 0))
        resumo['bonus_2'] = resumo['tipo_trofeu'].apply(lambda x: x.get('BONUS_2', 0))
        
        # Calcula data_fim (sábado da semana)
        resumo['data_fim'] = resumo['data_semana'] + pd.Timedelta(days=5)
        
        # Formata semana_uuid
        resumo['semana_uuid'] = resumo.apply(
            lambda row: f"{row['ano']}_W{row['semana']:02d}", axis=1
        )
        
        # Seleciona e ordena colunas
        resultado = resumo[[
            'semana_uuid', 'data_semana', 'data_fim', 
            'pontos', 'ouro', 'prata', 'bronze', 'bonus_1', 'bonus_2'
        ]].copy()
        
        resultado.columns = [
            'Semana', 'Início', 'Fim', 
            'Pontos', 'Ouro', 'Prata', 'Bronze', 'Bonus_1', 'Bonus_2'
        ]
        
        # Ordena por semana (mais recente primeiro)
        resultado = resultado.sort_values('Início', ascending=False)
        
        return resultado
        
    except Exception as e:
        st.error(f"Erro ao carregar conquistas por semana: {e}")
        return pd.DataFrame()

def get_medal_icon(tipo):
    tipo = tipo.upper()
    if "OURO" in tipo: return "🥇"
    if "PRATA" in tipo: return "🥈"
    if "BRONZE" in tipo: return "🥉"
    return "🎖️"

# --- HEADER (HERO SECTION) ---
mes_ano = date.today().strftime("%B/%Y").capitalize()
st.title(f"🏆 OLIMPÍADAS DE VENDAS")
st.markdown(f"### 🔥 Competição em andamento")
st.divider()

if not DB_GAMIFICACAO.exists():
    st.error("⚠️ Base de dados de gamificação não encontrada.")
    st.stop()

# --- TABS CONCEPT ---
tab_quadro, tab_atleta = st.tabs(["🥇 Quadro de Medalhas", "👤 Perfil do Atleta"])

# === TAB 1: QUADRO DE MEDALHAS ===
with tab_quadro:
    st.markdown("#### 🌍 Classificação Geral")
    
    # Datas
    inicio, fim = get_current_month_range()
    
    df_quadro = load_medal_table(inicio, fim)
    
    if not df_quadro.empty:
        # Formatação Visual para Tabela
        # Adiciona coluna de Medalhas Visual (Opcional, mas Dataframe é limpo)
        
        # Highlight Top 3
        col1, col2, col3 = st.columns(3)
        
        if len(df_quadro) >= 1:
            top1 = df_quadro.iloc[0]
            with col2: # Gold in Center
                 st.markdown(f"""
                 <div class="metric-card" style="border: 2px solid #FFD700; background-color: #FFFBE6; min-height: 160px; transform: scale(1.1);">
                    <div style="font-size: 40px;">🥇</div>
                    <div style="font-weight: bold; font-size: 18px; color: #1f1f1f;">{top1['Vendedor']}</div>
                    <div style="font-size: 32px; font-weight: 800; color: #B78727;">{top1['Pontos']} pts</div>
                 </div>
                 """, unsafe_allow_html=True)

        if len(df_quadro) >= 2:
            top2 = df_quadro.iloc[1]
            with col1: # Silver on Left
                 st.markdown(f"""
                 <div class="metric-card" style="border: 2px solid #C0C0C0; background-color: #F8F9FA; min-height: 140px; margin-top: 20px;">
                    <div style="font-size: 30px;">🥈</div>
                    <div style="font-weight: bold; font-size: 16px; color: #1f1f1f;">{top2['Vendedor']}</div>
                    <div style="font-size: 24px; font-weight: 800; color: #7f7f7f;">{top2['Pontos']} pts</div>
                 </div>
                 """, unsafe_allow_html=True)
        
        if len(df_quadro) >= 3:
            top3 = df_quadro.iloc[2]
            with col3: # Bronze on Right
                 st.markdown(f"""
                 <div class="metric-card" style="border: 2px solid #CD7F32; background-color: #FFF5EB; min-height: 140px; margin-top: 20px;">
                    <div style="font-size: 30px;">🥉</div>
                    <div style="font-weight: bold; font-size: 16px; color: #1f1f1f;">{top3['Vendedor']}</div>
                    <div style="font-size: 24px; font-weight: 800; color: #A05922;">{top3['Pontos']} pts</div>
                 </div>
                 """, unsafe_allow_html=True)
        
        st.divider()

        # Botão de Atualizar
        if st.button("🔄 Atualizar placar", type="primary"):
            st.cache_data.clear()
            st.rerun()

        # Tabela Limpa (Sem Barras)
        st.dataframe(
            df_quadro,
            column_config={
                "Vendedor": st.column_config.TextColumn("Atleta", width="medium"),
                "Ouro": st.column_config.NumberColumn("🥇 Ouro", format="%d"),
                "Prata": st.column_config.NumberColumn("🥈 Prata", format="%d"),
                "Bronze": st.column_config.NumberColumn("🥉 Bronze", format="%d"),
                "Pontos": st.column_config.NumberColumn("⭐ Pontos", format="%d"), # Removed ProgressColumn
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Ainda não há dados para o quadro de medalhas deste mês.")

# === TAB 2: PERFIL DO ATLETA ===
with tab_atleta:
    st.markdown("#### 👤 Ficha Técnica e Conquistas")
    
    all_sellers = load_medal_table("2000-01-01", "2099-12-31") # Get all names
    if not all_sellers.empty:
        sel_vendedor = st.selectbox("Selecione o Atleta:", all_sellers["Vendedor"].unique())
        
        if sel_vendedor:
            df_hist = load_athlete_history(sel_vendedor)
            
            # Cards de Resumo
            total_pts = df_hist["pontos"].sum()
            cnt_ouro = len(df_hist[df_hist["tipo_trofeu"].str.contains("OURO", case=False)])
            cnt_prata = len(df_hist[df_hist["tipo_trofeu"].str.contains("PRATA", case=False)])
            cnt_bronze = len(df_hist[df_hist["tipo_trofeu"].str.contains("BRONZE", case=False)])
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("⭐ PONTOS TOTAIS", total_pts)
            c2.metric("🥇 OURO", cnt_ouro)
            c3.metric("🥈 PRATA", cnt_prata)
            c4.metric("🥉 BRONZE", cnt_bronze)
            
            st.divider()
            
            # Timeline
            st.subheader("📜 Linha do Tempo")
            if not df_hist.empty:
                for _, row in df_hist.iterrows():
                    icon = get_medal_icon(row['tipo_trofeu'])
                    data_fmt = datetime.strptime(row['data_conquista'], "%Y-%m-%d").strftime("%d/%m")
                    st.markdown(f"📅 **{data_fmt}** — {icon} **{row['tipo_trofeu']}** (+{row['pontos']} pts)")
            else:
                st.info("Ainda sem medalhas. A competição está só começando 🔥")
            
            st.divider()
            
            # Conquistas por Semana
            st.subheader("📅 Conquistas por Semana")
            df_semanas = load_conquistas_por_semana(sel_vendedor)
            
            if not df_semanas.empty:
                # Formata datas para exibição
                df_display = df_semanas.copy()
                df_display['Período'] = df_display.apply(
                    lambda row: f"{row['Início'].strftime('%d/%m')} - {row['Fim'].strftime('%d/%m/%Y')}", 
                    axis=1
                )
                
                # Exibe tabela formatada
                st.dataframe(
                    df_display[['Semana', 'Período', 'Pontos', 'Ouro', 'Prata', 'Bronze', 'Bonus_1', 'Bonus_2']],
                    column_config={
                        "Semana": st.column_config.TextColumn("Semana", width="small"),
                        "Período": st.column_config.TextColumn("Período", width="medium"),
                        "Pontos": st.column_config.NumberColumn("⭐ Pontos", format="%d"),
                        "Ouro": st.column_config.NumberColumn("🥇 Ouro", format="%d"),
                        "Prata": st.column_config.NumberColumn("🥈 Prata", format="%d"),
                        "Bronze": st.column_config.NumberColumn("🥉 Bronze", format="%d"),
                        "Bonus_1": st.column_config.NumberColumn("🎖️ Bonus 1", format="%d"),
                        "Bonus_2": st.column_config.NumberColumn("🏅 Bonus 2", format="%d"),
                    },
                    use_container_width=True,
                    hide_index=True
                )
                
                # Gráfico de barras com pontos por semana
                st.markdown("#### 📊 Pontos por Semana")
                st.bar_chart(
                    df_semanas.set_index('Semana')['Pontos'],
                    height=300
                )
            else:
                st.info("Ainda não há conquistas agrupadas por semana.")
    else:
        st.warning("Nenhum atleta encontrado.")
