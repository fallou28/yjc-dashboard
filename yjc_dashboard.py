import streamlit as st
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Dashboard YJC", layout="wide")

st.title("📊 Dashboard YJC - YASSO + Fonds Yaakar")
st.markdown("Suivi en temps réel du projet Yaakaar Jeunesse Citoyenneté")

st.info("⚠️ Configuration Google requise. Voir 'Instructions' en bas.")

# KPI Cards
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Organisations YASSO", "179", "-21 vs cible")
with col2:
    st.metric("Plans d'action", "137", "+7 vs cible")
with col3:
    st.metric("Organisations validées", "140", "En ligne")
with col4:
    st.metric("Débats citoyens", "85", "+15 ce trim")

st.divider()
st.success("Dashboard déployé! Prochaine étape: ajouter les secrets Google.")
