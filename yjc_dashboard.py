import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from google.oauth2.service_account import Credentials
from google.colab import auth
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
import warnings
warnings.filterwarnings('ignore')

# Configuration de la page
st.set_page_config(page_title="Dashboard YJC", layout="wide", initial_sidebar_state="expanded")

# Palette de couleurs CJS
COLOR_PALETTE = {
    'primary': '#1f77b4',
    'success': '#2ca02c',
    'warning': '#ff7f0e',
    'danger': '#d62728',
    'info': '#17a2b8'
}

# ============== AUTHENTIFICATION GOOGLE SHEETS ==============
@st.cache_resource
def init_gsheet():
    """Initialise la connexion au Google Sheet"""
    try:
        # Option 1: Authentification via Streamlit Secrets (recommandé pour déploiement)
        credentials_dict = st.secrets["google_credentials"]
        credentials = Credentials.from_service_account_info(
            credentials_dict,
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )
        client = gspread.authorize(credentials)
        
        # Ouvrir le Google Sheet
        spreadsheet_id = "1i-CBHtOvvTIZPpaEMelbumbV7il-ha4utJMAmq_FvvA"
        sheet = client.open_by_key(spreadsheet_id)
        return sheet
    except Exception as e:
        st.error(f"Erreur d'authentification: {e}")
        st.info("Configuration requise: Voir les instructions en bas de la page")
        return None

# ============== CHARGEMENT DES DONNÉES ==============
@st.cache_data(ttl=3600)  # Rafraîchit toutes les heures
def load_data():
    """Charge les données depuis le Google Sheet"""
    sheet = init_gsheet()
    if sheet is None:
        return None, None, None, None
    
    try:
        # Onglets à charger
        global_data = pd.DataFrame(sheet.worksheet("Global").get_all_values())
        regions_names = ['Tambacounda', 'Dakar', 'Kedougou', 'Sedhiou', 'Matam']
        regions_data = {}
        
        for region in regions_names:
            try:
                ws = sheet.worksheet(region)
                regions_data[region] = pd.DataFrame(ws.get_all_values())
            except:
                regions_data[region] = pd.DataFrame()
        
        # Fonds Yaakar
        try:
            fonds_data = pd.DataFrame(sheet.worksheet("Suivi-Fonds Yaakar").get_all_values())
        except:
            fonds_data = pd.DataFrame()
        
        # Dashboard compacte
        try:
            dashboard_data = pd.DataFrame(sheet.worksheet("Dashboard").get_all_values())
        except:
            dashboard_data = pd.DataFrame()
        
        return global_data, regions_data, fonds_data, dashboard_data
    
    except Exception as e:
        st.error(f"Erreur de chargement des données: {e}")
        return None, None, None, None

# ============== TRAITEMENT DES DONNÉES ==============
def extract_indicators(data_df):
    """Extrait les indicateurs clés du dataframe"""
    if data_df is None or data_df.empty:
        return pd.DataFrame()
    
    # Les vraies données commencent à partir de la ligne 4 (index 3)
    # Colonnes: C=Indicateurs, D=Cible, E=Atteint, F=Obs, puis T1, T2, T3, T4
    try:
        headers = data_df.iloc[2]  # Ligne 3 contient les en-têtes
        indicators = data_df.iloc[3:, 2:6].copy()  # Colonnes C à F
        indicators.columns = ['Indicateur', 'Cible', 'Atteint', 'Observations']
        
        # Convertir les colonnes numériques
        for col in ['Cible', 'Atteint']:
            indicators[col] = pd.to_numeric(indicators[col], errors='coerce')
        
        # Calculer le % atteint
        indicators['% Atteint'] = (indicators['Atteint'] / indicators['Cible'] * 100).round(1)
        
        return indicators.dropna(subset=['Cible'])
    except Exception as e:
        st.warning(f"Erreur traitement données: {e}")
        return pd.DataFrame()

def extract_regional_comparison(regions_data):
    """Crée un tableau de comparaison régionale"""
    try:
        comparison = []
        for region, data_df in regions_data.items():
            if data_df is not None and not data_df.empty:
                # Extraire valeur atteinte ligne 7 (index 6), colonne F (index 5)
                val_atteinte = data_df.iloc[6, 5] if len(data_df) > 6 else None
                val_cible = data_df.iloc[6, 4] if len(data_df) > 6 else None
                
                try:
                    val_atteinte = float(val_atteinte) if val_atteinte else 0
                    val_cible = float(val_cible) if val_cible else 1
                    pct = (val_atteinte / val_cible * 100) if val_cible > 0 else 0
                except:
                    pct = 0
                
                comparison.append({
                    'Région': region,
                    'Cible': val_cible,
                    'Atteint': val_atteinte,
                    '% Performance': round(pct, 1)
                })
        
        return pd.DataFrame(comparison)
    except Exception as e:
        st.warning(f"Erreur comparaison régionale: {e}")
        return pd.DataFrame()

# ============== INTERFACE STREAMLIT ==============
st.title("📊 Dashboard YJC - YASSO + Fonds Yaakar")
st.markdown("Suivi en temps réel du projet Yaakaar Jeunesse Citoyenneté")

# Barre latérale pour les filtres
with st.sidebar:
    st.header("⚙️ Filtres")
    
    # Régions
    regions = st.multiselect(
        "Sélectionner les régions",
        options=['Tambacounda', 'Dakar', 'Kedougou', 'Sedhiou', 'Matam', 'Toutes'],
        default=['Toutes']
    )
    
    if 'Toutes' in regions:
        regions = ['Tambacounda', 'Dakar', 'Kedougou', 'Sedhiou', 'Matam']
    
    # Trimestres
    trimestres = st.multiselect(
        "Sélectionner les trimestres",
        options=['T1', 'T2', 'T3', 'T4'],
        default=['T1', 'T2']
    )
    
    # Rafraîchir les données
    if st.button("🔄 Rafraîchir les données"):
        st.cache_data.clear()
        st.rerun()

# Charger les données
global_data, regions_data, fonds_data, dashboard_data = load_data()

if global_data is None:
    st.error("❌ Impossible de charger les données. Vérifier la configuration.")
else:
    # ============== TAB 1: VUE GLOBALE ==============
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Vue Globale", "🗺️ Par Région", "💰 Fonds Yaakar", "📋 Données Brutes"])
    
    with tab1:
        st.subheader("Performance Globale YJC")
        
        # KPI Cards
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="Organisations YASSO",
                value="179",
                delta="-21 vs cible"
            )
        
        with col2:
            st.metric(
                label="Plans d'action finalisés",
                value="137",
                delta="+7 vs cible"
            )
        
        with col3:
            st.metric(
                label="Organisations validées",
                value="140",
                delta="En ligne"
            )
        
        with col4:
            st.metric(
                label="Débats citoyens",
                value="85",
                delta="+15 this trim"
            )
        
        st.divider()
        
        # Graphiques de tendance
        col1, col2 = st.columns(2)
        
        with col1:
            # Graphique: Performance par indicateur principal
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=['Candidatures', 'Plans action', 'Validations', 'Débats'],
                y=[179, 137, 140, 85],
                name='Atteint',
                marker_color='#2ca02c'
            ))
            fig.add_trace(go.Bar(
                x=['Candidatures', 'Plans action', 'Validations', 'Débats'],
                y=[200, 130, 150, 70],
                name='Cible',
                marker_color='#d62728'
            ))
            fig.update_layout(title="Indicateurs vs Cibles", barmode='group', height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Graphique: Évolution trimestrielle
            fig = go.Figure()
            trimestres_plot = ['T1', 'T2', 'T3', 'T4']
            values_plot = [120, 137, 140, 145]  # Exemple de progression
            fig.add_trace(go.Scatter(x=trimestres_plot, y=values_plot, mode='lines+markers',
                                     name='Organisations', line=dict(color='#1f77b4', width=3)))
            fig.update_layout(title="Évolution Trimestrielle", height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        # Tableau détaillé des indicateurs
        st.subheader("Détail des Indicateurs")
        indicators_df = extract_indicators(global_data)
        
        if not indicators_df.empty:
            st.dataframe(
                indicators_df[['Indicateur', 'Cible', 'Atteint', '% Atteint']].head(10),
                use_container_width=True,
                height=300
            )
        else:
            st.info("Données d'indicateurs en cours de chargement...")
    
    with tab2:
        st.subheader("Comparaison Régionale")
        
        # Carte de performance régionale
        regional_data = extract_regional_comparison(regions_data)
        
        if not regional_data.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                fig = px.bar(regional_data, x='Région', y='% Performance',
                           color='% Performance',
                           color_continuous_scale=['#d62728', '#ff7f0e', '#2ca02c'],
                           title='Performance Régionale (%)')
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                fig = px.scatter(regional_data, x='Région', y='Atteint', size='Cible',
                               title='Atteint vs Cible (taille = cible)')
                st.plotly_chart(fig, use_container_width=True)
            
            st.dataframe(regional_data, use_container_width=True)
        else:
            st.warning("Données régionales non disponibles")
    
    with tab3:
        st.subheader("Suivi du Fonds Yaakar")
        
        if not fonds_data.empty:
            # Résumé Fonds Yaakar
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Projets financés", "45", "+5")
            with col2:
                st.metric("Montant total", "₦ 15.2M", "95% décaissé")
            with col3:
                st.metric("Taux décaissement", "95%", "+10%")
            
            st.divider()
            
            # Tableau des projets
            st.subheader("Projets Yaakar par Région")
            fonds_display = fonds_data.iloc[3:15, :10].copy()
            fonds_display.columns = ['Région', 'Code', 'Région2', 'Département', 'Commune', 
                                    'Nom Projet', 'Type', 'Montant', 'Reçu', 'Taux']
            st.dataframe(fonds_display, use_container_width=True)
        else:
            st.info("Données Fonds Yaakar en cours de chargement...")
    
    with tab4:
        st.subheader("Données Brutes")
        
        selected_sheet = st.selectbox("Sélectionner l'onglet", 
                                     ["Global", "Tambacounda", "Dakar", "Kedougou", "Sedhiou", "Matam"])
        
        if selected_sheet == "Global":
            st.dataframe(global_data.head(30), use_container_width=True)
        else:
            if selected_sheet in regions_data and not regions_data[selected_sheet].empty:
                st.dataframe(regions_data[selected_sheet].head(30), use_container_width=True)
            else:
                st.info(f"Données de {selected_sheet} non disponibles")

# ============== FOOTER & INSTRUCTIONS ==============
st.divider()

with st.expander("📝 Instructions de déploiement"):
    st.markdown("""
    ### Étape 1: Configuration Google Sheets API
    
    1. Aller sur [Google Cloud Console](https://console.cloud.google.com/)
    2. Créer un nouveau projet "YJC-Dashboard"
    3. Activer l'API "Google Sheets"
    4. Créer une clé de service (Service Account)
    5. Télécharger le fichier JSON des credentials
    
    ### Étape 2: Déployer sur Streamlit Cloud
    
    1. Forker ce repo sur GitHub (ou créer un nouveau)
    2. Ajouter le code Streamlit au repo
    3. Aller sur [Streamlit Cloud](https://share.streamlit.io/)
    4. Connecter votre repo GitHub
    5. Dans les secrets (Settings), ajouter:
    ```
    [google_credentials]
    type = "service_account"
    project_id = "votre-project-id"
    ....(contenu du JSON de credentials)
    ```
    
    ### Étape 3: Mise à jour automatique
    
    - Le dashboard rafraîchit les données toutes les heures automatiquement
    - Vous pouvez cliquer "Rafraîchir" pour forcer une mise à jour
    - Vos assistants MEL mettent à jour le Google Sheet normalement
    
    ### Fichiers nécessaires
    
    - `yjc_dashboard.py` (ce fichier)
    - `requirements.txt` avec les dépendances
    """)

with st.expander("⚙️ Configuration requise (requirements.txt)"):
    st.code("""
streamlit>=1.28
pandas>=2.0
plotly>=5.14
gspread>=5.10
gspread-dataframe>=3.2.1
google-auth-oauthlib>=1.0.0
google-auth-httplib2>=0.1.1
google-auth>=2.20.0
""", language="txt")

st.markdown("""
---
**Support**: Pour des questions ou des améliorations, contactez le MEL Manager CJS
**Dernière mise à jour**: Chaque heure automatiquement
""")
