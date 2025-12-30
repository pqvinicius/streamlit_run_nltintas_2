"""
Componentes UI reutilizáveis do dashboard.
"""
import streamlit as st
import pandas as pd
from typing import Optional

from dashboard.utils.helpers import get_medal_icon


def render_top3_cards(df_quadro: pd.DataFrame):
    """
    Renderiza cards do top 3 vendedores.
    
    Args:
        df_quadro: DataFrame com ranking de vendedores.
    """
    if df_quadro.empty:
        return
    
    col1, col2, col3 = st.columns(3)
    
    if len(df_quadro) >= 1:
        top1 = df_quadro.iloc[0]
        with col2:  # Gold in Center
            st.markdown(f"""
            <div class="metric-card" style="border: 2px solid #FFD700; background-color: #FFFBE6; min-height: 160px; transform: scale(1.1);">
                <div style="font-size: 40px;">🥇</div>
                <div style="font-weight: bold; font-size: 18px; color: #1f1f1f;">{top1['Vendedor']}</div>
                <div style="font-size: 32px; font-weight: 800; color: #B78727;">{top1['Pontos']} pts</div>
            </div>
            """, unsafe_allow_html=True)
    
    if len(df_quadro) >= 2:
        top2 = df_quadro.iloc[1]
        with col1:  # Silver on Left
            st.markdown(f"""
            <div class="metric-card" style="border: 2px solid #C0C0C0; background-color: #F8F9FA; min-height: 140px; margin-top: 20px;">
                <div style="font-size: 30px;">🥈</div>
                <div style="font-weight: bold; font-size: 16px; color: #1f1f1f;">{top2['Vendedor']}</div>
                <div style="font-size: 24px; font-weight: 800; color: #7f7f7f;">{top2['Pontos']} pts</div>
            </div>
            """, unsafe_allow_html=True)
    
    if len(df_quadro) >= 3:
        top3 = df_quadro.iloc[2]
        with col3:  # Bronze on Right
            st.markdown(f"""
            <div class="metric-card" style="border: 2px solid #CD7F32; background-color: #FFF5EB; min-height: 140px; margin-top: 20px;">
                <div style="font-size: 30px;">🥉</div>
                <div style="font-weight: bold; font-size: 16px; color: #1f1f1f;">{top3['Vendedor']}</div>
                <div style="font-size: 24px; font-weight: 800; color: #A05922;">{top3['Pontos']} pts</div>
            </div>
            """, unsafe_allow_html=True)


def render_medal_timeline(df_hist: pd.DataFrame):
    """
    Renderiza linha do tempo de medalhas.
    
    Args:
        df_hist: DataFrame com histórico de conquistas.
    """
    if df_hist.empty:
        st.info("Ainda sem medalhas. A competição está só começando 🔥")
        return
    
    from datetime import datetime
    
    for _, row in df_hist.iterrows():
        icon = get_medal_icon(str(row['tipo_trofeu']))
        data_fmt = datetime.strptime(str(row['data_conquista']), "%Y-%m-%d").strftime("%d/%m")
        st.markdown(
            f"📅 **{data_fmt}** — {icon} **{row['tipo_trofeu']}** (+{int(row['pontos'])} pts)"
        )


def render_weekly_chart(df_semanas: pd.DataFrame):
    """
    Renderiza gráfico de pontos por semana.
    
    Args:
        df_semanas: DataFrame com conquistas por semana.
    """
    if df_semanas.empty:
        st.info("Ainda não há conquistas agrupadas por semana.")
        return
    
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


def render_store_leaderboard(df_stores: pd.DataFrame):
    """Renderiza a tabela de ranking de lojas (Normalizada)."""
    if df_stores.empty:
        st.info("Ainda não há dados suficientes para o ranking de lojas.")
        return

    st.dataframe(
        df_stores,
        column_config={
            "Loja": st.column_config.TextColumn("Unidade", width="medium"),
            "Vendedores": st.column_config.NumberColumn("👥 Time", format="%d"),
            "Total Pontos": st.column_config.NumberColumn("⭐ Total", format="%d"),
            "Pontos por Vendedor": st.column_config.NumberColumn("⚡ Eficiência (Pts/Vend)", format="%.1f"),
            "Total Ouro": st.column_config.NumberColumn("🥇", format="%d"),
        },
        use_container_width=True,
        hide_index=True
    )


def render_store_comparison_chart(df_comp: pd.DataFrame):
    """Renderiza gráfico de evolução comparativo entre lojas."""
    if df_comp.empty:
        st.info("Selecione lojas para visualizar a comparação de evolução.")
        return

    # Pivot table to have dates as index and stores as columns
    df_pivot = df_comp.pivot(index='data', columns='loja', values='pontos_acumulados').fillna(method='ffill').fillna(0)
    
    st.line_chart(df_pivot, height=400)

