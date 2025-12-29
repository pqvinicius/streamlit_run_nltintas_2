"""
Estilos CSS customizados para o dashboard.
"""
import streamlit as st


def load_custom_css():
    """
    Carrega CSS customizado para o dashboard.
    Deve ser chamado no início do app.
    """
    st.markdown("""
    <style>
        .big-font { 
            font-size: 24px !important; 
            font-weight: bold; 
        }
        .gold { 
            color: #FFD700; 
        }
        .silver { 
            color: #C0C0C0; 
        }
        .bronze { 
            color: #CD7F32; 
        }
        .metric-card {
            background-color: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
        }
    </style>
    """, unsafe_allow_html=True)

