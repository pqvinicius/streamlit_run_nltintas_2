import streamlit as st
from streamlit_autorefresh import st_autorefresh
from datetime import date
from pathlib import Path

# Adiciona o diretório raiz ao path para permitir imports do pacote dashboard
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dashboard.config.settings import AppSettings
from dashboard.services.medal_service import MedalService
from dashboard.services.period_service import PeriodService
from dashboard.ui import components, styles

# --- INITIALIZATION ---
st.set_page_config(page_title="NL CHAMPIONS LEAGUE", page_icon="🥇", layout="wide")
styles.load_custom_css()

# Auto-refresh every 10 minutes (600 seconds)
st_autorefresh(interval=600 * 1000, key="data_refresh")

# Initialize Services
settings = AppSettings()
medal_service = MedalService()
period_service = PeriodService()

# --- HEADER ---
# Busca logo (jpg, png ou jpeg)
logo_path = None
for ext in [".jpg", ".png", ".jpeg"]:
    p = Path(__file__).parent.parent / "data" / f"logo_empresa{ext}"
    if p.exists():
        logo_path = p
        break

if logo_path:
    col_logo, col_text = st.columns([1, 6])
    with col_logo:
        st.image(str(logo_path), width=120)
    with col_text:
        st.title("🏆 NL CHAMPIONS LEAGUE")
        st.markdown("### 🔥 Competição em andamento")
else:
    st.title("🏆 NL CHAMPIONS LEAGUE")
    st.markdown("### 🔥 Competição em andamento")

st.divider()

# --- TABS ---
tab_quadro, tab_atleta = st.tabs(["🥇 Quadro de Medalhas", "👤 Perfil do Atleta"])

# === TAB 1: QUADRO DE MEDALHAS ===
with tab_quadro:
    st.markdown("#### 🌍 Classificação Geral")
    
    # Get Commercial Period
    inicio, fim = period_service.get_current_month_range()
    
    # Load Data
    df_quadro = medal_service.get_medal_table(inicio, fim)
    
    if not df_quadro.empty:
        # Highlight Top 3
        components.render_top3_cards(df_quadro)
        
        st.divider()

        # Update Button
        if st.button("🔄 Atualizar placar", type="primary"):
            st.cache_data.clear()
            st.rerun()

        # Leaderboard Table
        st.dataframe(
            df_quadro,
            column_config={
                "Vendedor": st.column_config.TextColumn("Atleta", width="medium"),
                "Ouro": st.column_config.NumberColumn("🥇 Ouro", format="%d"),
                "Prata": st.column_config.NumberColumn("🥈 Prata", format="%d"),
                "Bronze": st.column_config.NumberColumn("🥉 Bronze", format="%d"),
                "Pontos": st.column_config.NumberColumn("⭐ Pontos", format="%d"),
            },
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Ainda não há dados para o quadro de medalhas deste mês.")

# === TAB 2: PERFIL DO ATLETA ===
with tab_atleta:
    st.markdown("#### 👤 Ficha Técnica e Conquistas")
    
    # Get All Active Sellers
    vendedores = medal_service.get_all_vendedores()
    
    if vendedores:
        sel_vendedor = st.selectbox("Selecione o Atleta:", vendedores)
        
        if sel_vendedor:
            df_hist = medal_service.get_athlete_history(sel_vendedor)
            
            # Summary Metrics
            if not df_hist.empty:
                total_pts = df_hist["pontos"].sum()
                cnt_ouro = len(df_hist[df_hist["tipo_trofeu"].str.contains("OURO", case=False)])
                cnt_prata = len(df_hist[df_hist["tipo_trofeu"].str.contains("PRATA", case=False)])
                cnt_bronze = len(df_hist[df_hist["tipo_trofeu"].str.contains("BRONZE", case=False)])
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("⭐ PONTOS TOTAIS", int(total_pts))
                c2.metric("🥇 OURO", cnt_ouro)
                c3.metric("🥈 PRATA", cnt_prata)
                c4.metric("🥉 BRONZE", cnt_bronze)
            
            st.divider()
            
            # Timeline
            st.subheader("📜 Linha do Tempo")
            components.render_medal_timeline(df_hist)
            
            st.divider()
            
            # Weekly Achievements
            st.subheader("📅 Conquistas por Semana")
            df_semanas = medal_service.get_conquistas_por_semana(sel_vendedor)
            components.render_weekly_chart(df_semanas)
    else:
        st.warning("Nenhum atleta encontrado na base de dados.")

st.divider()
st.markdown("<div style='text-align: center; color: grey;'>Desenvolvido por Vinicius Xavier</div>", unsafe_allow_html=True)
