import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="Dashboard YJC", layout="wide", initial_sidebar_state="expanded")

@st.cache_resource
def init_gsheet():
    try:
        credentials_dict = st.secrets["google_credentials"]
        credentials = Credentials.from_service_account_info(
            credentials_dict,
            scopes=[
                'https://www.googleapis.com/auth/spreadsheets.readonly',
                'https://www.googleapis.com/auth/drive.readonly'
            ]
        )
        client = gspread.authorize(credentials)
        spreadsheet_id = "1i-CBHtOvvTIZPpaEMelbumbV7il-ha4utJMAmq_FvvA"
        sheet = client.open_by_key(spreadsheet_id)
        return sheet
    except Exception as e:
        st.error(f"Erreur d'authentification: {e}")
        return None

@st.cache_data(ttl=3600)
def load_data():
    sheet = init_gsheet()
    if sheet is None:
        return None, None, None, None
    try:
        global_data = pd.DataFrame(sheet.worksheet("Global").get_all_values())
        regions_names = ['Tambacounda', 'Dakar', 'Kedougou', 'Sedhiou', 'Matam']
        regions_data = {}
        for region in regions_names:
            try:
                ws = sheet.worksheet(region)
                regions_data[region] = pd.DataFrame(ws.get_all_values())
            except:
                regions_data[region] = pd.DataFrame()
        try:
            fonds_data = pd.DataFrame(sheet.worksheet("Suivi-Fonds Yaakar").get_all_values())
        except:
            fonds_data = pd.DataFrame()
        try:
            dashboard_data = pd.DataFrame(sheet.worksheet("Dashboard").get_all_values())
        except:
            dashboard_data = pd.DataFrame()
        return global_data, regions_data, fonds_data, dashboard_data
    except Exception as e:
        st.error(f"Erreur de chargement: {e}")
        return None, None, None, None

def extract_indicators(data_df):
    if data_df is None or data_df.empty:
        return pd.DataFrame()
    try:
        indicators = data_df.iloc[3:, 2:6].copy()
        indicators.columns = ['Indicateur', 'Cible', 'Atteint', 'Observations']
        for col in ['Cible', 'Atteint']:
            indicators[col] = pd.to_numeric(indicators[col], errors='coerce')
        indicators['% Atteint'] = (indicators['Atteint'] / indicators['Cible'] * 100).round(1)
        return indicators.dropna(subset=['Cible'])
    except:
        return pd.DataFrame()

def extract_regional_comparison(regions_data):
    try:
        comparison = []
        for region, data_df in regions_data.items():
            if data_df is not None and not data_df.empty:
                try:
                    val_atteinte = float(data_df.iloc[6, 5]) if len(data_df) > 6 else 0
                    val_cible = float(data_df.iloc[6, 4]) if len(data_df) > 6 else 1
                    pct = (val_atteinte / val_cible * 100) if val_cible > 0 else 0
                except:
                    val_atteinte, val_cible, pct = 0, 0, 0
                comparison.append({
                    'Région': region,
                    'Cible': val_cible,
                    'Atteint': val_atteinte,
                    '% Performance': round(pct, 1)
                })
        return pd.DataFrame(comparison)
    except:
        return pd.DataFrame()

# ===== INTERFACE =====
st.title("📊 Dashboard YJC - YASSO + Fonds Yaakar")
st.markdown("Suivi en temps réel du projet Yaakaar Jeunesse Citoyenneté")

with st.sidebar:
    st.header("⚙️ Filtres")
    regions_select = st.multiselect(
        "Régions",
        options=['Tambacounda', 'Dakar', 'Kedougou', 'Sedhiou', 'Matam'],
        default=['Tambacounda', 'Dakar', 'Kedougou', 'Sedhiou', 'Matam']
    )
    trimestres_select = st.multiselect(
        "Trimestres",
        options=['T1', 'T2', 'T3', 'T4'],
        default=['T1', 'T2']
    )
    if st.button("🔄 Rafraîchir"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

global_data, regions_data, fonds_data, dashboard_data = load_data()

if global_data is None:
    st.error("❌ Impossible de charger les données. Vérifier la configuration Google.")
    st.stop()

tab1, tab2, tab3, tab4 = st.tabs(["📈 Vue Globale", "🗺️ Par Région", "💰 Fonds Yaakar", "📋 Données Brutes"])

with tab1:
    st.subheader("Performance Globale YJC")
    indicators_df = extract_indicators(global_data)

    if not indicators_df.empty:
        cols = st.columns(4)
        for i, row in enumerate(indicators_df.head(4).itertuples()):
            with cols[i % 4]:
                delta = f"{row.Atteint - row.Cible:.0f} vs cible" if pd.notna(row.Atteint) and pd.notna(row.Cible) else "N/A"
                st.metric(label=str(row.Indicateur)[:40], value=f"{row.Atteint:.0f}" if pd.notna(row.Atteint) else "N/A", delta=delta)

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        if not indicators_df.empty:
            fig = go.Figure()
            df_plot = indicators_df.head(6).dropna(subset=['Cible', 'Atteint'])
            fig.add_trace(go.Bar(x=df_plot['Indicateur'].str[:20], y=df_plot['Atteint'], name='Atteint', marker_color='#2ca02c'))
            fig.add_trace(go.Bar(x=df_plot['Indicateur'].str[:20], y=df_plot['Cible'], name='Cible', marker_color='#d62728'))
            fig.update_layout(title="Indicateurs vs Cibles", barmode='group', height=400)
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        if not indicators_df.empty:
            fig = px.bar(indicators_df.head(8).dropna(subset=['% Atteint']),
                        x='Indicateur', y='% Atteint',
                        color='% Atteint',
                        color_continuous_scale=['#d62728', '#ff7f0e', '#2ca02c'],
                        title="% Atteint par Indicateur")
            fig.add_hline(y=100, line_dash="dash", line_color="blue", annotation_text="Cible 100%")
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("Tableau des Indicateurs")
    if not indicators_df.empty:
        st.dataframe(indicators_df[['Indicateur', 'Cible', 'Atteint', '% Atteint', 'Observations']],
                    use_container_width=True, height=400)

with tab2:
    st.subheader("Comparaison Régionale")
    regional_df = extract_regional_comparison({r: regions_data[r] for r in regions_select if r in regions_data})

    if not regional_df.empty:
        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(regional_df, x='Région', y='% Performance',
                        color='% Performance',
                        color_continuous_scale=['#d62728', '#ff7f0e', '#2ca02c'],
                        title='Performance par Région (%)')
            fig.add_hline(y=100, line_dash="dash", line_color="blue")
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=regional_df['Région'], y=regional_df['Cible'], name='Cible', marker_color='#d62728'))
            fig.add_trace(go.Bar(x=regional_df['Région'], y=regional_df['Atteint'], name='Atteint', marker_color='#2ca02c'))
            fig.update_layout(title="Cible vs Atteint par Région", barmode='group')
            st.plotly_chart(fig, use_container_width=True)
        st.dataframe(regional_df, use_container_width=True)
    else:
        st.warning("Données régionales non disponibles")

with tab3:
    st.subheader("Suivi du Fonds Yaakar")
    if fonds_data is not None and not fonds_data.empty:
        st.dataframe(fonds_data, use_container_width=True, height=500)
    else:
        st.info("Données Fonds Yaakar non disponibles")

with tab4:
    st.subheader("Données Brutes")
    selected = st.selectbox("Onglet", ["Global"] + list(regions_data.keys()))
    if selected == "Global":
        st.dataframe(global_data, use_container_width=True, height=500)
    elif selected in regions_data and not regions_data[selected].empty:
        st.dataframe(regions_data[selected], use_container_width=True, height=500)
    else:
        st.info(f"Données de {selected} non disponibles")

st.divider()
st.markdown("**Dashboard YJC** - MEL Manager CJS | Mise à jour automatique toutes les heures")
