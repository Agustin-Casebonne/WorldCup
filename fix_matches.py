#!/usr/bin/env python3
"""
fix_matches.py

Corrige los CSVs de partidos donde la fecha quedó pegada al nombre del equipo
o donde la fecha está en una línea separada en el cup.txt original.

Patrones corregidos:
  1. "Fri Jun/9  Germany" → date="2006-06-09", home_team="Germany"
  2. 2014: fecha en línea separada del cup.txt → buscada por (home, away)

Uso:
  python fix_matches.py
  python fix_matches.py --input data/parsed/matches_all.csv --output data/parsed/matches_all_clean.csv
"""

import argparse
import re
import pandas as pd
from pathlib import Path
from typing import Optional

# e.g. "Fri Jun/9     Germany"
DATE_PREFIX_RE = re.compile(
    r'^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Za-z]{3})[/\.](\d{1,2})\s+(.*)',
    re.IGNORECASE
)

# Standalone date header line e.g. "Thu Jun/12"
DATE_HEADER_RE = re.compile(
    r'^(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Za-z]{3})[/\.](\d{1,2})\s*$',
    re.IGNORECASE
)

# "  17:00  Team1 v Team2  score"
TEAM_V_TEAM_RE = re.compile(
    r'^\s*\d{1,2}:\d{2}\s+(.+?)\s+v\s+(.+?)\s+\d+-\d+',
    re.IGNORECASE
)

# "  17:00  Team1 1-3 Team2  @"
TEAM_SCORE_TEAM_RE = re.compile(
    r'^\s*\d{1,2}:\d{2}\s+(.+?)\s+\d+-\d+(?:\s+\(\d+-\d+\))?\s+(.+?)\s*(?:@|\[|$)'
)

MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
    'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
    'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}


def _make_date(year: int, month_str: str, day_str: str) -> Optional[str]:
    month = MONTH_MAP.get(month_str.lower())
    if not month:
        return None
    try:
        return f"{year}-{month:02d}-{int(day_str):02d}"
    except Exception:
        return None


def extract_year(tournament: str) -> Optional[int]:
    m = re.search(r'(\d{4})', str(tournament))
    return int(m.group(1)) if m else None


def build_cup_date_lookup(cup_txt_path: Path, year: int) -> dict:
    """
    Parse cup.txt -> {(home_team, away_team): 'YYYY-MM-DD'}.
    Handles 'Thu Jun/12' date headers followed by match lines.
    """
    lookup = {}
    current_date = None
    try:
        text = cup_txt_path.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return lookup

    for line in text.splitlines():
        stripped = line.strip()

        # Standalone date header
        m = DATE_HEADER_RE.match(stripped)
        if m:
            current_date = _make_date(year, m.group(1), m.group(2))
            continue

        if current_date is None:
            continue

        # "  17:00  Team1 v Team2  score"
        m = TEAM_V_TEAM_RE.match(line)
        if m:
            lookup[(m.group(1).strip(), m.group(2).strip())] = current_date
            continue

        # "  17:00  Team1 1-3 Team2"
        m = TEAM_SCORE_TEAM_RE.match(line)
        if m:
            home = m.group(1).strip()
            away = m.group(2).strip()
            if re.search(r'[A-Za-z]', home) and re.search(r'[A-Za-z]', away):
                lookup[(home, away)] = current_date

    return lookup


def parse_team_date(value: str, year: Optional[int]) -> tuple:
    """Extract (team_name, date_str) when date prefix is embedded in field."""
    if not value or not isinstance(value, str):
        return value, None
    m = DATE_PREFIX_RE.match(value.strip())
    if not m:
        return value.strip(), None
    month_str, day_str, team = m.group(1), m.group(2), m.group(3).strip()
    return team, (_make_date(year, month_str, day_str) if year else None)


def fix_df(df: pd.DataFrame, cup_lookups: dict) -> pd.DataFrame:
    df = df.copy()
    new_dates, new_home_teams, new_winners = [], [], []

    for _, row in df.iterrows():
        year = extract_year(row.get('tournament', ''))
        existing_date = row.get('date')
        home_val = str(row.get('home_team', '') or '')
        away_val = str(row.get('away_team', '') or '')

        if pd.isna(existing_date) or str(existing_date).strip() == '':
            # Try embedded date in home_team field
            team, date_str = parse_team_date(home_val, year)

            # If still no date, try cup.txt lookup
            if not date_str and year in cup_lookups:
                lk = cup_lookups[year]
                date_str = lk.get((team, away_val.strip()))

            new_home_teams.append(team)
            new_dates.append(date_str)
        else:
            new_home_teams.append(home_val)
            new_dates.append(existing_date)

        # Fix winner (may also have date prefix)
        winner_val = str(row.get('winner', '') or '')
        winner_team, _ = parse_team_date(winner_val, year)
        new_winners.append(winner_team)

    df['date'] = new_dates
    df['home_team'] = new_home_teams
    df['winner'] = new_winners
    return df


def load_cup_lookups(openfootball_dir: str) -> dict:
    """Load cup.txt date lookups for all tournaments."""
    lookups = {}
    base = Path(openfootball_dir)
    for folder in base.iterdir():
        if not folder.is_dir():
            continue
        m = re.search(r'(\d{4})', folder.name)
        if not m:
            continue
        year = int(m.group(1))
        cup_txt = folder / 'cup.txt'
        if cup_txt.exists():
            lk = build_cup_date_lookup(cup_txt, year)
            if lk:
                lookups[year] = lk
    return lookups


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', default='data/parsed/matches_all.csv')
    p.add_argument('--output', default='data/parsed/matches_all_clean.csv')
    p.add_argument('--openfootball-dir', default='data/openfootball')
    p.add_argument('--also-fix-yearly', action='store_true',
                   help='Also fix individual matches_YYYY.csv files in same folder')
    args = p.parse_args()

    print("Cargando lookups de cup.txt...")
    lookups = load_cup_lookups(args.openfootball_dir)
    print(f"  Lookups cargados para: {sorted(lookups.keys())}")

    print(f"\nLeyendo {args.input}...")
    df = pd.read_csv(args.input)
    before_null = df['date'].isna().sum()
    print(f"  Fechas null antes: {before_null}")

    df_fixed = fix_df(df, lookups)
    after_null = df_fixed['date'].isna().sum()
    print(f"  Fechas null después: {after_null}")
    print(f"  Fechas recuperadas: {before_null - after_null}")

    df_fixed.to_csv(args.output, index=False)
    print(f"Guardado: {args.output}")

    if args.also_fix_yearly:
        folder_path = Path(args.input).parent
        for f in sorted(folder_path.glob('matches_????.csv')):
            df_y = pd.read_csv(f)
            null_before = df_y['date'].isna().sum()
            if null_before > 0:
                df_y_fixed = fix_df(df_y, lookups)
                null_after = df_y_fixed['date'].isna().sum()
                df_y_fixed.to_csv(f, index=False)
                print(f"  {f.name}: {null_before} null -> {null_after} null")


if __name__ == '__main__':
    main()
