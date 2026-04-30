import requests
from datetime import datetime, timedelta

class FootballDataAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {'x-apisports-key': self.api_key}

    def get_match_stats(self, home_team, away_team, date_str):
        # 1. Intentamos buscar en la fecha exacta, el día antes y el día después
        # (Por si hay líos de zona horaria en tu MongoDB)
        fecha_dt = datetime.strptime(date_str, '%Y-%m-%d')
        fechas_a_probar = [
            date_str,
            (fecha_dt - timedelta(days=1)).strftime('%Y-%m-%d'),
            (fecha_dt + timedelta(days=1)).strftime('%Y-%m-%d')
        ]
        
        match_id = None
        match_data = None

        for fecha in fechas_a_probar:
            url = f"{self.base_url}/fixtures"
            params = {"date": fecha, "league": 1, "season": 2022} # Forzamos Mundial 2022
            
            try:
                res = requests.get(url, headers=self.headers, params=params)
                fixtures = res.json().get('response', [])
                
                for f in fixtures:
                    h_api = f['teams']['home']['name'].lower()
                    a_api = f['teams']['away']['name'].lower()
                    h_db = home_team.lower()
                    a_db = away_team.lower()
                    
                    # Comparación flexible
                    if (h_db in h_api or h_api in h_db) and (a_db in a_api or a_api in a_db):
                        match_id = f['fixture']['id']
                        match_data = f
                        break
                if match_id: break 
            except: continue

        if not match_id: return None

        # 2. Si lo encuentra, traer las estadísticas
        try:
            url_s = f"{self.base_url}/fixtures/statistics"
            res_s = requests.get(url_s, headers=self.headers, params={"fixture": match_id})
            stats = res_s.json().get('response', [])
            
            return {
                "stats": stats if stats else None,
                "logos": {
                    "home": match_data['teams']['home']['logo'],
                    "away": match_data['teams']['away']['logo']
                }
            }
        except:
            return None