Resumen rápido

- Fuente recomendada: **Kaggle (FIFA World Cup Dataset)** — la más completa para análisis históricos (resultados, alineaciones, goles, etapas, jugadores). Alternativa ligera: **openfootball (GitHub)**.
- Objetivo: descargar dataset y cargarlo en MongoDB (local o Atlas) usando el script `load_worldcup_to_mongo.py`.

Pasos para obtener los datos

1) Opción (recomendada): Kaggle
- Regístrate en Kaggle y genera tu `kaggle.json` (Account -> API).
- Instala Kaggle CLI: `pip install kaggle`.
- Descargar dataset (ejemplo):

```bash
kaggle datasets download -d <dataset-owner/dataset-name> -p data/ --unzip
```

Busca en Kaggle por "FIFA World Cup Dataset" o "World Cup 1930-2022".

2) Alternativa (openfootball, GitHub)

```bash
git clone https://github.com/openfootball/world-cup.git data/openfootball
```

Instalación de dependencias

```bash
pip install pymongo pandas
```

Preparar MongoDB

- Local: instala MongoDB Community y asegúrate que `mongod` esté corriendo.
- Atlas: crea cluster y copia la `connection string` (ej: `mongodb+srv://user:pass@cluster0.mongodb.net`).

Ejecutar el script de carga

```bash
python load_worldcup_to_mongo.py --data-dir data/ --mongo-uri "mongodb://localhost:27017" --db worldcup
```

Cosas a tener en cuenta

- El script es genérico: crea una colección por cada CSV/JSON (nombre = nombre del fichero). Revisa y renombra colecciones si quieres normalizar (ej. `matches`, `teams`, `players`).
- Convierte `NaN` a `null` para MongoDB.
- Para grandes volúmenes, importa por lotes (ya implementado) y considera `mongod` con suficiente memoria.

Sugerencias de modelo e índices

- Colecciones sugeridas: `tournaments`, `matches`, `teams`, `players`, `events`, `lineups`.
- Índices recomendados:
  - `matches`: `{ match_id: 1 }`, `{ date: 1 }`, `{ home_team_id: 1, away_team_id: 1 }`
  - `players`: `{ player_id: 1 }`, `{ team_id: 1 }`
  - `teams`: `{ team_id: 1 }`

Consultas de ejemplo (mongo shell)

```js
// Partidos de Argentina en 2018
db.matches.find({"year":2018, $or: [{"home_team":"Argentina"},{"away_team":"Argentina"}]})

// Goleadores: agrupar por jugador y sumar goles (si hay campo 'goals')
db.events.aggregate([
  { $match: { type: "goal" } },
  { $group: { _id: "$player_id", goals: { $sum: 1 } } },
  { $sort: { goals: -1 } }
])
```

Siguientes pasos recomendados

- Revisar nombres y normalizar esquema según el dataset que descargues.
- Añadir validaciones (ej. `mongod` schema validation) si vas a exponer datos en producción.

Si quieres, puedo:
- Crear una estructura de colecciones normalizada (ETL) basada en un dataset específico (p. ej. Kaggle). 
- Conectar y subir un ejemplo de dataset si me das acceso a los archivos o me indicas el dataset exacto de Kaggle/GitHub que usarás.
