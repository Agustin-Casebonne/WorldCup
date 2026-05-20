import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from conexion import cargar_datos_github
import numpy as np
import unicodedata
import re
from pymongo import MongoClient
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import os


# ==============================
# MONGO DB

client = MongoClient("mongodb://localhost:27017")
db = client["worldCup"]
coll = db["matches"]

datos = list(coll.find(
    {},
    {
        "_id": 0,
        "home_team": 1,
        "away_team": 1,
        "elo_diff": 1,
        "match_temp": 1,
        "match_hum": 1,
        "shock_home": 1,
        "shock_away": 1,
        "home_days_since_last_match": 1,
        "away_days_since_last_match": 1,
        "winner": 1
    }
))

df = pd.DataFrame(datos)


# ENTRENAMIENTO DEL MODELO

# CARGA DE DATOS 
base_path = os.path.dirname(__file__)
ruta_csv = os.path.join(base_path, "mundiales_clima_pro.csv")
df_train = pd.read_csv(ruta_csv)

# DEFINIR GANADOR 
def definir_ganador(row):
    if row['home_score'] > row['away_score']:
        return 0  # Home
    if row['away_score'] > row['home_score']:
        return 1  # Away
    return 2      # Draw

df_train['target'] = df_train.apply(definir_ganador, axis=1)

# CODIFICAR EQUIPOS 
le = LabelEncoder()
todos_equipos = pd.concat([
    df_train['home_team'],
    df_train['away_team']
]).unique()
le.fit(todos_equipos)

df_train['home_id'] = le.transform(df_train['home_team'])
df_train['away_id'] = le.transform(df_train['away_team'])

# --- D. FEATURES ---
features = [
    'home_id',
    'away_id',
    'elo_diff',
    'match_temp',
    'match_hum',
    'shock_home',
    'shock_away'
]

X = df_train[features].fillna(0)
y = df_train['target']

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42
)

# ENTRENAR EXTRA TREES 
mejor_modelo = ExtraTreesClassifier(
    n_estimators=100,
    random_state=42
)
mejor_modelo.fit(X_train, y_train)

y_pred = mejor_modelo.predict(X_test)
precision = accuracy_score(y_test, y_pred)

print(f"Extra Trees: {precision * 100:.2f}%")

# LIMPIEZA DE NOMBRES

def limpiar_equipo(texto):
    texto = texto.lower()
    texto = unicodedata.normalize('NFKD', texto).encode('ascii', 'ignore').decode('utf-8')
    texto = re.sub(r'[^a-z0-9\s]', '', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto

# GRUPOS
grupos = {
    "A": [
        ("México", "Sudáfrica"),
        ("República de Corea", "Chequia"),
        ("México", "República de Corea"),
        ("Chequia", "Sudáfrica"),
        ("México", "Chequia"),
        ("Sudáfrica", "República de Corea"),
    ],
    "B": [
        ("Canadá", "Bosnia y Herzegovina"),
        ("Catar", "Suiza"),
        ("Canadá", "Catar"),
        ("Suiza", "Bosnia y Herzegovina"),
        ("Canadá", "Suiza"),
        ("Bosnia y Herzegovina", "Catar"),
    ],
    "C": [
        ("Brasil", "Marruecos"),
        ("Haití", "Escocia"),
        ("Escocia", "Marruecos"),
        ("Brasil", "Haití"),
        ("Escocia", "Brasil"),
        ("Marruecos", "Haití"),
    ],
    "D": [
        ("EE. UU.", "Paraguay"),
        ("Australia", "Turquía"),
        ("EE. UU.", "Australia"),
        ("Turquía", "Paraguay"),
        ("Turquía", "EE. UU."),
        ("Paraguay", "Australia"),
    ],
    "E": [
        ("Alemania", "Curazao"),
        ("Costa de Marfil", "Ecuador"),
        ("Alemania", "Costa de Marfil"),
        ("Ecuador", "Curazao"),
        ("Curazao", "Costa de Marfil"),
        ("Ecuador", "Alemania"),
    ],
    "F": [
        ("Países Bajos", "Japón"),
        ("Suecia", "Túnez"),
        ("Países Bajos", "Suecia"),
        ("Túnez", "Japón"),
        ("Japón", "Suecia"),
        ("Túnez", "Países Bajos"),
    ],
    "G": [
        ("Bélgica", "Egipto"),
        ("RI de Irán", "Nueva Zelanda"),
        ("Bélgica", "RI de Irán"),
        ("Nueva Zelanda", "Egipto"),
        ("Egipto", "RI de Irán"),
        ("Nueva Zelanda", "Bélgica"),
    ],
    "H": [
        ("España", "Islas de Cabo Verde"),
        ("Arabia Saudí", "Uruguay"),
        ("España", "Arabia Saudí"),
        ("Uruguay", "Islas de Cabo Verde"),
        ("Islas de Cabo Verde", "Arabia Saudí"),
        ("Uruguay", "España"),
    ],
    "I": [
        ("Francia", "Senegal"),
        ("Irak", "Noruega"),
        ("Francia", "Irak"),
        ("Noruega", "Senegal"),
        ("Noruega", "Francia"),
        ("Senegal", "Irak"),
    ],
    "J": [
        ("Argentina", "Argelia"),
        ("Austria", "Jordania"),
        ("Argentina", "Austria"),
        ("Jordania", "Argelia"),
        ("Argelia", "Austria"),
        ("Jordania", "Argentina"),
    ],
    "K": [
        ("Portugal", "RD Congo"),
        ("Uzbekistán", "Colombia"),
        ("Portugal", "Uzbekistán"),
        ("Colombia", "RD Congo"),
        ("Colombia", "Portugal"),
        ("RD Congo", "Uzbekistán"),
    ],
    "L": [
        ("Inglaterra", "Croacia"),
        ("Ghana", "Panamá"),
        ("Inglaterra", "Ghana"),
        ("Panamá", "Croacia"),
        ("Panamá", "Inglaterra"),
        ("Croacia", "Ghana"),
    ]
}

# FUNCION PREDICCION
def predecir_partido(team1, team2):
    try:
        t1 = le.transform([limpiar_equipo(team1)])[0]
        t2 = le.transform([limpiar_equipo(team2)])[0]
    except:
        return team1

    fila = df[(df["home_team"] == team1) & (df["away_team"] == team2)]

    if len(fila) > 0:
        r = fila.iloc[0]
        X = pd.DataFrame([{
            "home_id": t1,
            "away_id": t2,
            "elo_diff": r["elo_diff"],
            "match_temp": r["match_temp"],
            "match_hum": r["match_hum"],
            "shock_home": r["shock_home"],
            "shock_away": r["shock_away"],
            "home_days_since_last_match": r["home_days_since_last_match"],
            "away_days_since_last_match": r["away_days_since_last_match"]
        }])
    else:
        X = pd.DataFrame([{
            "home_id": t1,
            "away_id": t2,
            "elo_diff": 0,
            "match_temp": 0,
            "match_hum": 0,
            "shock_home": 0,
            "shock_away": 0,
            "home_days_since_last_match": 0,
            "away_days_since_last_match": 0
        }])

    pred = mejor_modelo.predict(X)[0]

    if pred == 0:
        return team1
    elif pred == 1:
        return team2
    else:
        return np.random.choice([team1, team2])




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
tab1, tab2, tab3, tab4 = st.tabs(["📈 Analítica y Tendencias", "🏟️ Detalle de Partidos", "🌟 Jugadores Laureados y Penaltis", "🔮 Simulación del Mundial"])

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
            
with tab4:

    st.header("🏆 Copa Mundial 2026")

    # Mostramos la precisión del modelo en la sidebar
    st.sidebar.metric("🎯 Precisión del modelo", f"{precision * 100:.2f}%")

    st.write("Pulsa el botón para simular el torneo completo con el modelo entrenado.")

    if st.button("⚽ Simular Mundial"):

        tabla_grupos = {}
        terceros = []
        resultados_grupos = {}

       
        # FASE DE GRUPOS 
        
        for grupo, partidos in grupos.items():
            puntos = {}
            for t1, t2 in partidos:
                ganador = predecir_partido(t1, t2)
                puntos.setdefault(t1, 0)
                puntos.setdefault(t2, 0)
                if ganador == t1:
                    puntos[t1] += 3
                elif ganador == t2:
                    puntos[t2] += 3
                else:
                    puntos[t1] += 1
                    puntos[t2] += 1

            orden = sorted(puntos.items(), key=lambda x: x[1], reverse=True)
            resultados_grupos[grupo] = orden

            tabla_grupos[grupo] = {
                "1": orden[0][0],
                "2": orden[1][0],
                "3": orden[2][0],
                "pts3": orden[2][1]
            }
            terceros.append((grupo, orden[2][0], orden[2][1]))

        # ======================
        # FASE DE GRUPOS 
        # ======================
        st.subheader("📋 Fase de Grupos")
        iconos = ["🥇", "🥈", "🥉", "   "]
        letras = list(resultados_grupos.keys())
        filas = [letras[i:i+4] for i in range(0, len(letras), 4)]

        for fila in filas:
            cols = st.columns(4)
            for col, letra in zip(cols, fila):
                with col:
                    st.markdown(f"*Grupo {letra}*")
                    for i, (eq, pts) in enumerate(resultados_grupos[letra]):
                        icono = iconos[i] if i < len(iconos) else "   "
                        st.write(f"{icono} {eq} — *{pts}pts*")

        st.divider()

        
        # MEJORES TERCEROS
       
        terceros_ordenados = sorted(terceros, key=lambda x: x[2], reverse=True)
        mejores_terceros = list(terceros_ordenados[:8])

        # Validación: todos los grupos deben tener cobertura
        todos_grupos = set(grupos.keys())
        grupos_en_restricciones = {
            "A", "B", "C", "D", "F",
            "C", "D", "F", "G", "H",
            "C", "E", "F", "H", "I",
            "E", "H", "I", "J", "K",
            "B", "D", "E", "F", "I", "J",
            "A", "E", "G", "H", "I", "J",
            "E", "F", "G", "I", "J",
            "D", "E", "G", "I", "J", "L",
        }
        grupos_sin_cobertura = todos_grupos - grupos_en_restricciones
        if grupos_sin_cobertura:
            st.error(f"❌ Grupos sin cobertura: {grupos_sin_cobertura}")
            st.stop()

        def mejor_tercero(grupos_validos):
            for i, (g, eq, pts) in enumerate(mejores_terceros):
                if g in grupos_validos:
                    mejores_terceros.pop(i)
                    return eq
            if mejores_terceros:
                g, eq, pts = mejores_terceros.pop(0)
                st.warning(f"⚠️ Grupo {g} asignado fuera de restricción")
                return eq
            return "Por determinar"

     
        # RESULTADOS POR FASE
        
        ganadores = {}

        def jugar(idp, t1, t2):
            ganador = predecir_partido(t1, t2)
            st.write(f"*P{idp}* — {t1} vs {t2} → 🏆 *{ganador}*")
            ganadores[idp] = ganador

   
        # DIECISEISAVOS (73-88)
        
        st.subheader("🔥 Dieciseisavos de Final")

        partidos_16avos = [
            (73, tabla_grupos["A"]["2"], tabla_grupos["B"]["2"]),
            (74, tabla_grupos["E"]["1"], mejor_tercero(["A", "B", "C", "D", "F"])),
            (75, tabla_grupos["F"]["1"], tabla_grupos["C"]["2"]),
            (76, tabla_grupos["C"]["1"], tabla_grupos["F"]["2"]),
            (77, tabla_grupos["I"]["1"], mejor_tercero(["C", "D", "F", "G", "H"])),
            (78, tabla_grupos["E"]["2"], tabla_grupos["I"]["2"]),
            (79, tabla_grupos["A"]["1"], mejor_tercero(["C", "E", "F", "H", "I"])),
            (80, tabla_grupos["L"]["1"], mejor_tercero(["E", "H", "I", "J", "K"])),
            (81, tabla_grupos["D"]["1"], mejor_tercero(["B", "D", "E", "F", "I", "J"])),
            (82, tabla_grupos["G"]["1"], mejor_tercero(["A", "E", "G", "H", "I", "J"])),
            (83, tabla_grupos["K"]["2"], tabla_grupos["L"]["2"]),
            (84, tabla_grupos["H"]["1"], tabla_grupos["J"]["2"]),
            (85, tabla_grupos["B"]["1"], mejor_tercero(["E", "F", "G", "I", "J"])),
            (86, tabla_grupos["J"]["1"], tabla_grupos["H"]["2"]),
            (87, tabla_grupos["K"]["1"], mejor_tercero(["D", "E", "G", "I", "J", "L"])),
            (88, tabla_grupos["D"]["2"], tabla_grupos["G"]["2"]),
        ]

        col_izq, col_der = st.columns(2)
        mitad = len(partidos_16avos) // 2
        with col_izq:
            for idp, t1, t2 in partidos_16avos[:mitad]:
                jugar(idp, t1, t2)
        with col_der:
            for idp, t1, t2 in partidos_16avos[mitad:]:
                jugar(idp, t1, t2)

        st.divider()

       
        # OCTAVOS (89-96)
        
        st.subheader("⚔️ Octavos de Final")

        col_izq, col_der = st.columns(2)
        with col_izq:
            jugar(89, ganadores[74], ganadores[77])
            jugar(90, ganadores[73], ganadores[75])
            jugar(91, ganadores[76], ganadores[78])
            jugar(92, ganadores[79], ganadores[80])
        with col_der:
            jugar(93, ganadores[83], ganadores[84])
            jugar(94, ganadores[81], ganadores[82])
            jugar(95, ganadores[86], ganadores[88])
            jugar(96, ganadores[85], ganadores[87])

        st.divider()

       
        # CUARTOS (97-100)
        
        st.subheader("🏟️ Cuartos de Final")

        col_izq, col_der = st.columns(2)
        with col_izq:
            jugar(97, ganadores[89], ganadores[90])
            jugar(98, ganadores[93], ganadores[94])
        with col_der:
            jugar(99, ganadores[91], ganadores[92])
            jugar(100, ganadores[95], ganadores[96])

        st.divider()

        
        # SEMIFINALES (101-102)
       
        st.subheader("🔥 Semifinales")

        col_izq, col_der = st.columns(2)
        with col_izq:
            jugar(101, ganadores[97], ganadores[98])
        with col_der:
            jugar(102, ganadores[99], ganadores[100])

        st.divider()

        
        # FINAL
        
        st.subheader("🏆 FINAL")

        finalista1 = ganadores[101]
        finalista2 = ganadores[102]
        campeon = predecir_partido(finalista1, finalista2)

        st.write(f"🥇 *{finalista1}* vs *{finalista2}*")
        st.success(f"🏆 CAMPEÓN DEL MUNDIAL 2026: *{campeon}*")
        
    else:
        st.info("No hubo tandas de penaltis en esta edición del torneo.")
 