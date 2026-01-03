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
from dashboard.services.store_service import get_store_service
from dashboard.ui import components, styles
from dashboard.database.queries import load_normalized_store_ranking

# --- INITIALIZATION ---
st.set_page_config(page_title="NL CHAMPIONS LEAGUE", page_icon="🥇", layout="wide")
styles.load_custom_css()

# Auto-refresh every 10 minutes (600 seconds)
st_autorefresh(interval=600 * 1000, key="data_refresh")

# Initialize Services
settings = AppSettings()
medal_service = MedalService()
period_service = PeriodService()
store_service = get_store_service()

# --- SIDEBAR FILTERS ---
st.sidebar.title("📅 Filtros")
default_start, default_end = period_service.get_current_month_range()
df_start_date = st.sidebar.date_input("Data Inicial", value=date.fromisoformat(default_start))
df_end_date = st.sidebar.date_input("Data Final", value=date.fromisoformat(default_end))

start_date_str = df_start_date.isoformat()
end_date_str = df_end_date.isoformat()

if st.sidebar.button("🔄 Atualizar Dados"):
    st.cache_data.clear()
    st.rerun()

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
tab_quadro, tab_semanal, tab_loja, tab_atleta, tab_comp = st.tabs([
    "🥇 Quadro Geral", 
    "🏆 Ranking Semanal",
    "🏬 Perfil da Loja", 
    "👤 Perfil do Atleta", 
    "📊 Comparação de Lojas"
])

# === TAB 1: QUADRO GERAL ===
with tab_quadro:
    st.markdown("#### 🌍 Classificação de Elite (Olimpíadas)")
    
    # 1. Ranking de Vendedores (Volume + Medalhas) - PRIORIDADE TOTAL
    df_quadro = medal_service.get_medal_table(start_date_str, end_date_str)
    
    # [NEW] Apply Centralized Badges
    try:
        from src.services.badge_service import BadgeService
        badge_service_dashboard = BadgeService()
        if not df_quadro.empty:
            df_quadro = badge_service_dashboard.aplicar_badges(df_quadro)
    except Exception as e:
        print(f"Error applying badges in dashboard: {e}")

    if not df_quadro.empty:
        # Destaque para os Medalhistas
        components.render_top3_cards(df_quadro)
        
        st.divider()
        
        # Tabela Estilo Olimpíadas
        st.subheader("🥇 Quadro de Medalhas Individual")
        
        # Reorder columns to show Badge first if exists
        cols = ["badge_icon", "Vendedor", "Pontos", "Ouro", "Prata", "Bronze"] if "badge_icon" in df_quadro.columns else ["Vendedor", "Pontos", "Ouro", "Prata", "Bronze"]
        
        st.dataframe(
            df_quadro[cols],
            column_config={
                "badge_icon": st.column_config.TextColumn("Rank", width="small"),
                "Vendedor": st.column_config.TextColumn("Atleta", width="medium"),
                "Pontos": st.column_config.NumberColumn("⭐ Total Pontos", format="%d"),
                "Ouro": st.column_config.NumberColumn("🥇 Ouro", format="%d"),
                "Prata": st.column_config.NumberColumn("🥈 Prata", format="%d"),
                "Bronze": st.column_config.NumberColumn("🥉 Bronze", format="%d"),
            },
            width="stretch",
            hide_index=True
        )
    else:
        st.info("Ainda não há dados para o quadro de medalhas neste período.")

    st.divider()
    
    # 2. Ranking de Lojas (Secundário / Comparação)
    with st.expander("🏬 Ver Ranking de Eficiência por Loja"):
        st.subheader("Eficiência das Unidades (Pts/Vend)")
        df_ranking_lojas = store_service.get_normalized_ranking(start_date_str, end_date_str)
        components.render_store_leaderboard(df_ranking_lojas)

# === TAB 2: RANKING SEMANAL (ANÁLISE) ===
with tab_semanal:
    st.markdown("#### 🕵️ Análise Detalhada da Semana")
    
    # 1. Filtro de Semana
    options_dict = medal_service.get_available_weeks_options()
    
    if options_dict:
        # Pega a semana mais recente por padrão
        selected_option = st.selectbox(
            "📅 Selecione a Semana para Análise:", 
            options_dict, 
            format_func=lambda x: x['label']
        )
        
        if selected_option:
            wk_start = selected_option['start_date']
            wk_end = selected_option['end_date']
            
            # Carrega dados
            df_semanal = medal_service.get_weekly_summary(wk_start, wk_end)
            
            if not df_semanal.empty:
                # 2. KPIs da Semana
                best_seller = df_semanal.iloc[0] # Assumindo ordenado por pontos
                total_medals = df_semanal['Ouro'].sum() + df_semanal['Prata'].sum() + df_semanal['Bronze'].sum()
                avg_score = df_semanal['Pontos'].mean()
                
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("🥇 Maior Pontuação", int(best_seller['Pontos']))
                k2.metric("👤 Melhor Vendedor", best_seller['Vendedor'])
                k3.metric("🏅 Medalhas Distribuídas", int(total_medals))
                k4.metric("📊 Média de Pontos", f"{avg_score:.1f}")
                
                st.divider()
                
                # 3. Tabela Interativa
                st.subheader("📋 Classificação Completa da Semana")
                
                # Config columns
                st.dataframe(
                    df_semanal,
                    column_config={
                        "Alcance %": st.column_config.ProgressColumn(
                            "Alcance Meta",
                            format="%.1f%%",
                            min_value=0,
                            max_value=120,
                        ),
                        "Status": st.column_config.TextColumn("Status"),
                        "Pontos": st.column_config.NumberColumn(" Pontos", format="%d"),
                        "Venda": None,
                        "Meta": None,
                    },
                    width="stretch",
                    hide_index=True
                )
                
                c_chart, c_text = st.columns([2, 1])
                
                with c_chart:
                    # 4. Gráfico: Quem fez mais pontos?
                    st.subheader("📊 Performance por Pontos")
                    st.bar_chart(
                        df_semanal.set_index("Vendedor")[["Pontos"]],
                        color="#FFD700", # Gold-ish
                        height=400
                    )
                    
                with c_text:
                    # 5. Destaques Automáticos
                    st.subheader("🔍 Insights Automáticos")
                    st.markdown(f"""
                    - **{best_seller['Vendedor']}** liderou com **{int(best_seller['Pontos'])}** pontos.
                    - **{len(df_semanal[df_semanal['Alcance %'] >= 100])}** vendedores bateram a meta (100%+).
                    - **{len(df_semanal[df_semanal['Pontos'] > avg_score])}** vendedores ficaram acima da média ({avg_score:.0f}).
                    """)
                    
                    if not df_semanal[df_semanal['Ouro'] > 0].empty:
                        ouro_names = ", ".join(df_semanal[df_semanal['Ouro'] > 0]['Vendedor'].tolist())
                        st.markdown(f"- 🥇 **Ouro da semana**: {ouro_names}")

            else:
                st.warning("Sem dados para esta semana.")
    else:
        st.info("Nenhum histórico semanal encontrado.")

# === TAB 2: PERFIL DA LOJA ===
with tab_loja:
    st.markdown("#### 🏬 Detalhamento por Unidade")
    
    lojas = store_service.get_all_lojas()
    if lojas:
        sel_loja = st.selectbox("Selecione a Loja:", lojas)
        
        if sel_loja:
            # Overview Metrics
            df_ov = store_service.get_store_overview(sel_loja, start_date_str, end_date_str)
            if not df_ov.empty:
                row = df_ov.iloc[0]
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("⭐ PONTOS TOTAIS", int(row.get('total_pontos', 0)))
                c2.metric("👥 VENDEDORES", int(row.get('vendedores_ativos', 0)))
                c3.metric("🥇 OUROS", int(row.get('total_ouro', 0)))
                c4.metric("🥈+🥉 MEDALHAS", int(row.get('total_outras', 0)))
                
                st.divider()
                
                # Evolution Chart
                st.subheader("📈 Evolução de Pontos da Loja (Acumulado)")
                df_evo = store_service.get_store_evolution(sel_loja, start_date_str, end_date_str)
                if not df_evo.empty:
                    # Gráfico de Linha (Acumulado)
                    st.line_chart(df_evo.set_index('data')['pontos_acumulados'], height=300)
                
                st.divider()
                
                # Bar Chart (Daily Comparison)
                st.subheader("📊 Comparativo Diário (Pontos por Dia)")
                if not df_evo.empty:
                    st.bar_chart(df_evo.set_index('data')['pontos_dia'], height=300)
                
                st.divider()
                
                # Store Sellers
                st.subheader("👥 Performance do Time")
                df_sellers = store_service.get_store_sellers(sel_loja, start_date_str, end_date_str)
                st.dataframe(df_sellers, width="stretch", hide_index=True)
    else:
        st.warning("Nenhuma loja encontrada na base de dados.")

# === TAB 3: PERFIL DO ATLETA ===
with tab_atleta:
    st.markdown("#### 👤 Ficha Técnica e Conquistas")
    
    vendedores = medal_service.get_all_vendedores()
    
    if vendedores:
        sel_vendedor = st.selectbox("Selecione o Atleta:", vendedores)
        
        if sel_vendedor:
            df_hist = medal_service.get_athlete_history(sel_vendedor)
            
            # Summary Metrics
            if not df_hist.empty:
                # Filter history by selected period for metrics
                df_hist_period = df_hist[
                    (df_hist['data_conquista'] >= start_date_str) & 
                    (df_hist['data_conquista'] <= end_date_str)
                ]
                
                total_pts = df_hist_period["pontos"].sum()
                cnt_ouro = len(df_hist_period[df_hist_period["tipo_trofeu"].str.contains("OURO", case=False)])
                cnt_prata = len(df_hist_period[df_hist_period["tipo_trofeu"].str.contains("PRATA", case=False)])
                cnt_bronze = len(df_hist_period[df_hist_period["tipo_trofeu"].str.contains("BRONZE", case=False)])
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("⭐ PONTOS NO PERÍODO", int(total_pts))
                c2.metric("🥇 OURO", cnt_ouro)
                c3.metric("🥈 PRATA", cnt_prata)
                c4.metric("🥉 BRONZE", cnt_bronze)
            
                st.divider()
                
                # Timeline
                st.subheader("📜 Linha do Tempo (Período)")
                components.render_medal_timeline(df_hist_period)
                
                st.divider()
                
                # Weekly Achievements
                st.subheader("📅 Conquistas por Semana (Histórico)")
                df_semanas = medal_service.get_conquistas_por_semana(sel_vendedor)
                components.render_weekly_chart(df_semanas)
    else:
        st.warning("Nenhum atleta encontrado na base de dados.")

# === TAB 4: COMPARAÇÃO DE LOJAS ===
with tab_comp:
    st.markdown("#### 📊 Comparação Estratégica")
    
    todas_lojas = store_service.get_all_lojas()
    sel_lojas = st.multiselect("Selecione as lojas para comparar:", todas_lojas, default=todas_lojas[:2] if len(todas_lojas) >= 2 else todas_lojas)
    
    if sel_lojas:
        st.subheader("📈 Evolução Acumulada Comparada")
        df_comparison = store_service.get_stores_comparison(sel_lojas, start_date_str, end_date_str)
        components.render_store_comparison_chart(df_comparison)
        
        st.divider()
        
        # Comparative KPIs
        st.subheader("🎯 KPIs de Eficiência")
        df_ranking_lojas = store_service.get_normalized_ranking(start_date_str, end_date_str)
        df_comp_metrics = df_ranking_lojas[df_ranking_lojas['Loja'].isin(sel_lojas)]
        
        cols = st.columns(len(sel_lojas))
        for i, loja in enumerate(sel_lojas):
            loja_data = df_comp_metrics[df_comp_metrics['Loja'] == loja]
            if not loja_data.empty:
                row = loja_data.iloc[0]
                with cols[i]:
                    st.metric(f"Loja: {loja}", f"{row['Pontos por Vendedor']} pts/vend")
                    st.caption(f"Total: {int(row['Total Pontos'])} pts | 🥇: {int(row['Total Ouro'])}")
    else:
        st.info("Selecione pelo menos uma loja para comparar.")

st.divider()
st.markdown("<div style='text-align: center; color: grey;'>Desenvolvido por Vinicius Xavier</div>", unsafe_allow_html=True)
