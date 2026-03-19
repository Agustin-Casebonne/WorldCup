#!/usr/bin/env python3
"""
download_fifa_rankings.py

Descarga el dataset completo de rankings FIFA (1992-presente) desde
el repositorio público de Kaggle/GitHub y lo normaliza en data/fifa_rankings.csv
con columnas: date, country, rank

Fuentes (en orden de preferencia):
  1. Kaggle dataset de cashncarry "fifaranking" (requiere kaggle API key)
  2. CSV público de los rankings FIFA (GitHub mirror)

Uso:
  python download_fifa_rankings.py
  python download_fifa_rankings.py --out data/fifa_rankings.csv
"""

import argparse
import urllib.request
import io
import os
import sys
import csv

# URL del CSV con rankings FIFA históricos completos (1992-2024)
# Fuente: dataset público en GitHub de martj42/international_results
FIFA_RANKINGS_URL = (
    "https://raw.githubusercontent.com/cnrv/FIFA-Rankings/master/FIFA_rankings.csv"
)

# URL de respaldo con otro formato
BACKUP_URL = (
    "https://raw.githubusercontent.com/jokecamp/FootballData/master/FIFA%20Rankings/rankings.csv"
)


def fetch_url(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def detect_columns(header: list) -> tuple:
    """Detect column names for date, country, rank in header."""
    header_low = [h.lower().strip() for h in header]
    date_col = next((header[i] for i, h in enumerate(header_low) if h in ("date", "rank_date", "ranking_date")), None)
    country_col = next((header[i] for i, h in enumerate(header_low) if h in ("country", "team", "country_full", "nation")), None)
    rank_col = next((header[i] for i, h in enumerate(header_low) if h in ("rank", "ranking", "position", "total_points")), None)
    return date_col, country_col, rank_col


def normalize_and_save(raw: bytes, out_path: str) -> int:
    text = raw.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    date_col, country_col, rank_col = detect_columns(header)

    if not date_col or not country_col or not rank_col:
        raise ValueError(
            f"No se encontraron columnas requeridas. Header detectado: {header}\n"
            f"Buscando: date={date_col}, country={country_col}, rank={rank_col}"
        )

    print(f"Columnas detectadas -> date: '{date_col}', country: '{country_col}', rank: '{rank_col}'")

    os.makedirs(os.path.dirname(out_path) if os.path.dirname(out_path) else ".", exist_ok=True)
    written = 0
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "country", "rank"])
        for row in reader:
            date = row.get(date_col, "").strip()
            country = row.get(country_col, "").strip()
            rank = row.get(rank_col, "").strip()
            if date and country and rank:
                # Keep only YYYY-MM-DD part
                date = date[:10]
                writer.writerow([date, country, rank])
                written += 1
    return written


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="data/fifa_rankings.csv")
    p.add_argument("--url", default=None, help="URL alternativa al CSV de rankings")
    args = p.parse_args()

    urls = [FIFA_RANKINGS_URL, BACKUP_URL]
    if args.url:
        urls = [args.url] + urls

    for url in urls:
        print(f"Intentando descargar: {url}")
        try:
            raw = fetch_url(url)
            written = normalize_and_save(raw, args.out)
            print(f"Guardado {args.out} con {written:,} filas.")
            sys.exit(0)
        except Exception as e:
            print(f"  Fallo: {e}")

    print("\nNo se pudo descargar el CSV automáticamente.")
    print("Descarga manual:")
    print("  1. Ve a https://www.kaggle.com/datasets/cashncarry/fifaworldranking")
    print("  2. Descarga 'fifa_ranking-2024-07-18.csv'")
    print("  3. Renombralo a data/fifa_rankings_raw.csv")
    print("  4. Corre: python download_fifa_rankings.py --url file:///ruta/al/archivo.csv")
    sys.exit(1)


if __name__ == "__main__":
    main()
