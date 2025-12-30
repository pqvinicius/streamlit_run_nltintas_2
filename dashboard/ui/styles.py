"""
Estilos CSS customizados para o dashboard.
"""
import streamlit as st


import os

def load_custom_css():
    """
    Carrega CSS customizado para o dashboard.
    Deve ser chamado no início do app.
    """
    css_file = os.path.join(os.path.dirname(__file__), "styles.css")
    if os.path.exists(css_file):
        with open(css_file, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        # Fallback se arquivo não encontrado
        st.warning("Arquivo de estilos não encontrado.")

