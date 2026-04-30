import pandas as pd
import streamlit as st

@st.cache_data
def cargar_datos_github():
    base_url = "https://raw.githubusercontent.com/jfjelstul/worldcup/master/data-csv/"
    
    # Cargamos los DataFrames principales
    matches = pd.read_csv(base_url + "matches.csv")
    goals = pd.read_csv(base_url + "goals.csv")
    teams = pd.read_csv(base_url + "teams.csv")
    
    return matches, goals, teams

# Uso en el Dashboard
df_matches, df_goals, df_teams = cargar_datos_github()