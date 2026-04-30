import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from conexion import cargar_datos_github
import numpy as np

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="World Cup Gold Data 2026", layout="wide", page_icon="🏆")

# --- CARGA DE DATOS ROBUSTA ---
# Intentamos cargar desde conexion.py, pero por si acaso te faltan archivos, 
# los cargamos directamente aquí con un bloque seguro.
@st.cache_data
def load_all_data():
    base_url = "https://raw.githubusercontent.com/jfjelstul/worldcup/master/data-csv/"
    return {
        'matches': pd.read_csv(base_url + "matches.csv"),
        'goals': pd.read_csv(base_url + "goals.csv"),
        'teams': pd.read_csv(base_url + "teams.csv"),
        'bookings': pd.read_csv(base_url + "bookings.csv"),
        'awards': pd.read_csv(base_url + "awards.csv"),
        'winners': pd.read_csv(base_url + "award_winners.csv"),
        'stadiums': pd.read_csv(base_url + "stadiums.csv"),
        'penalties': pd.read_csv(base_url + "penalty_kicks.csv")
    }

data = load_all_data()

# --- TÍTULO ---
st.title("🏆 Análisis Estadístico Global Mundial Football")
st.markdown("---")

# --- SIDEBAR (Filtros Globales) ---
st.sidebar.header("Filtros de Análisis")
edicion = st.sidebar.selectbox("Selecciona un Mundial", sorted(data['matches']['tournament_name'].unique(), reverse=True))

# Filtrar datos por la edición seleccionada
m_filt = data['matches'][data['matches']['tournament_name'] == edicion]
g_filt = data['goals'][data['goals']['tournament_name'] == edicion]
b_filt = data['bookings'][data['bookings']['tournament_name'] == edicion]
w_filt = data['winners'][data['winners']['tournament_name'] == edicion]
p_filt = data['penalties'][data['penalties']['tournament_name'] == edicion]

# --- LAYOUT PRINCIPAL ---
tab1, tab2, tab3 = st.tabs(["📈 Analítica y Tendencias", "🏟️ Detalle de Partidos", "🌟 Jugadores Laureados y Penaltis"])

# ================= TAB 1: ANALÍTICA Y TENDENCIAS =================
with tab1:
    st.subheader(f"Resumen de {edicion}")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Partidos Jugados", len(m_filt))
    col2.metric("Goles Totales", len(g_filt), f"{round(len(g_filt)/len(m_filt), 2)} por partido")
    col3.metric("Tarjetas Amarillas", len(b_filt[b_filt['yellow_card'] == 1]))
    col4.metric("Tarjetas Rojas", len(b_filt[b_filt['red_card'] == 1]))

    st.markdown("---")
    
    c1, c2 = st.columns([1.5, 1])
    
    with c1:
        st.subheader("📉 Gráfica de Tendencia")
        # Calculamos goles por partido de TODA la historia
        goles_hist = data['goals'].groupby('tournament_name').size().reset_index(name='goles')
        partidos_hist = data['matches'].groupby('tournament_name').size().reset_index(name='partidos')
        tendencia = pd.merge(goles_hist, partidos_hist, on='tournament_name')
        tendencia['promedio'] = tendencia['goles'] / tendencia['partidos']
        
        # Extraemos el año para el eje X
        tendencia['year'] = tendencia['tournament_name'].str.extract('(\d{4})').astype(int)
        tendencia = tendencia.sort_values('year')

        fig_tendencia = px.line(
            tendencia, x='year', y='promedio', markers=True,
            title="Evolución de Goles por Partido (1930 - Actualidad)",
            labels={'year': 'Año del Mundial', 'promedio': 'Goles por Partido'},
            template="plotly_white"
        )
        # Resaltar en rojo la edición seleccionada
        year_sel = int(edicion[:4])
        fig_tendencia.add_vline(x=year_sel, line_dash="dash", line_color="red", annotation_text="Edición Actual")
        st.plotly_chart(fig_tendencia, use_container_width=True)

    with c2:
        st.subheader("🟨🟥 Matriz de Dureza")
        if not b_filt.empty:
            # Creamos tramos de tiempo para las tarjetas
            bins = [0, 15, 30, 45, 60, 75, 90, 150]
            labels = ['0-15', '16-30', '31-45', '46-60', '61-75', '76-90', 'Prórroga']
            b_filt = b_filt.copy() # Evitar warning de pandas
            b_filt['tramo_minuto'] = pd.cut(b_filt['minute_regulation'], bins=bins, labels=labels, right=True)
            
            # Matriz: Equipos vs Tramos
            matriz_dureza = b_filt.groupby(['team_name', 'tramo_minuto']).size().reset_index(name='tarjetas')
            matriz_pivot = matriz_dureza.pivot(index='team_name', columns='tramo_minuto', values='tarjetas').fillna(0)
            
            # Filtramos solo equipos que hayan recibido al menos 3 tarjetas en total para no saturar
            matriz_pivot = matriz_pivot[matriz_pivot.sum(axis=1) > 2]
            
            fig_dureza = px.imshow(
                matriz_pivot, 
                color_continuous_scale='YlOrRd',
                title="¿Cuándo hacen mas faltas los equipos?",
                labels=dict(x="Tramo del Partido", y="Selección", color="Tarjetas")
            )
            st.plotly_chart(fig_dureza, use_container_width=True)
        else:
            st.info("En esta edición no hubo tarjetas registradas (o no existían).")

# ================= TAB 2: DETALLE DE PARTIDO =================
with tab2:
    st.subheader("Buscador de Enfrentamientos")
    
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        p_sel = st.selectbox("Selecciona un partido", m_filt['match_name'].unique())
    
    det_partido = m_filt[m_filt['match_name'] == p_sel].iloc[0]
    m_id = det_partido['match_id']
    
    st.markdown(f"<h2 style='text-align: center;'>{det_partido['match_name']} ({det_partido['score']})</h2>", unsafe_allow_html=True)
    st.caption(f"<div style='text-align: center;'>🏟️ {det_partido['stadium_name']} | 📅 {det_partido['match_date']}</div>", unsafe_allow_html=True)
    st.markdown("---")

    ca, cb = st.columns(2)
    with ca:
        st.markdown("#### ⚽ Goleadores")
        goles_p = g_filt[g_filt['match_id'] == m_id]
        if not goles_p.empty:
            for _, r in goles_p.iterrows():
                st.success(f"**{r['team_name']}** - {r['given_name']} {r['family_name']} ({r['minute_label']})")
        else:
            st.write("Sin goles registrados.")

    with cb:
        st.markdown("#### 🟨🟥 Disciplina")
        cards_p = b_filt[b_filt['match_id'] == m_id]
        if not cards_p.empty:
            for _, r in cards_p.iterrows():
                if r['red_card'] == 1:
                    st.error(f"🟥 **{r['team_name']}** - {r['family_name']} ({r['minute_label']})")
                else:
                    st.warning(f"🟨 **{r['team_name']}** - {r['family_name']} ({r['minute_label']})")
        else:
            st.write("Partido limpio. Sin tarjetas.")

# ================= TAB 3: SALÓN DE LA FAMA Y PENALTIS =================
with tab3:
    st.header("🏆 Cuadro de Honor")
    
    if not w_filt.empty:
        # Mostramos los premios como "Tarjetas" usando columnas
        premios = w_filt['award_name'].unique()
        cols = st.columns(len(premios[:4])) # Mostrar máximo 4 en una fila para que no se apelmace
        
        for idx, premio in enumerate(premios[:4]):
            ganador = w_filt[w_filt['award_name'] == premio].iloc[0]
            with cols[idx]:
                st.info(f"**{premio}**")
                st.markdown(f"### {ganador['given_name']} {ganador['family_name']}")
                st.caption(f"🏳️ {ganador['team_name']}")
    else:
        st.warning("Los premios individuales empezaron a registrarse de forma oficial a partir de 1978/1982.")

    st.markdown("---")
    
    # ZONA CLUTCH: ANÁLISIS DE PENALTIS
    st.subheader("🎯 Zona 'Clutch': Los Penaltis")
    if not p_filt.empty:
        col_pk1, col_pk2 = st.columns(2)
        
        with col_pk1:
            aciertos = p_filt['converted'].sum()
            fallos = len(p_filt) - aciertos
            fig_pk = px.pie(
                values=[aciertos, fallos], 
                names=['Anotados', 'Fallados / Parados'],
                title="Efectividad en Tandas de Penaltis",
                color_discrete_sequence=['#2ecc71', '#e74c3c'],
                hole=0.4
            )
            st.plotly_chart(fig_pk, use_container_width=True)
            
        with col_pk2:
            rendimiento_pk = p_filt.groupby('team_name')['converted'].agg(['sum', 'count']).reset_index()
            rendimiento_pk['porcentaje'] = (rendimiento_pk['sum'] / rendimiento_pk['count']) * 100
            rendimiento_pk = rendimiento_pk.sort_values('sum', ascending=False)
            
            fig_bar_pk = px.bar(
                rendimiento_pk, x='team_name', y='sum',
                text=rendimiento_pk['porcentaje'].apply(lambda x: f"{x:.0f}% acierto"),
                labels={'sum': 'Penaltis Anotados', 'team_name': 'Selección'},
                title="Rendimiento por Selección",
                color='porcentaje', color_continuous_scale="greens"
            )
            st.plotly_chart(fig_bar_pk, use_container_width=True)
    else:
        st.info("No hubo tandas de penaltis en esta edición del torneo.")
 