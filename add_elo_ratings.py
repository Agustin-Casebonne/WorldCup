#!/usr/bin/env python3
"""
add_elo_ratings.py

Calcula ratings Elo para cada equipo procesando los partidos en orden cronológico.
Los ratings se añaden a cada partido como `home_elo` y `away_elo`
(el Elo ANTES del partido, que es lo que vale para predicción).

Parámetros Elo usados:
 - Elo inicial: 1500 para todos
 - K factor knockout (Semi, Final, QF): 60
 - K factor grupo: 40
 - Ventaja local (host tournament): +50 puntos al Elo esperado
 - Extra goles: ajuste si el resultado es >2 goles de diferencia

Uso:
  python add_elo_ratings.py
  python add_elo_ratings.py --input data/parsed/matches_all.csv --out-csv data/parsed/matches_all_with_elo.csv
"""

import argparse
import json
import math
import pandas as pd
from datetime import datetime

# ── Elo constants ──────────────────────────────────────────────────────────────
ELO_INIT = 1500.0
ELO_SCALE = 400.0      # divisor in 10^x
HOME_ADVANTAGE = 50.0  # points added to home expected score during group stage

KNOCKOUT_STAGES = {
    "final", "finals", "third-place match", "third place match",
    "semi-finals", "semi-final", "quarter-finals", "quarter-final",
    "round of 16", "last 16", "second round",
}


def k_factor(stage: str) -> float:
    if stage and stage.lower().strip() in KNOCKOUT_STAGES:
        return 60.0
    return 40.0


def goal_multiplier(home_score: int, away_score: int) -> float:
    """ClubElo-style multiplier for goal difference."""
    diff = abs(home_score - away_score)
    if diff <= 1:
        return 1.0
    elif diff == 2:
        return 1.5
    else:
        return (11 + diff) / 8.0


def expected_score(elo_home: float, elo_away: float, home_advantage: float = HOME_ADVANTAGE) -> float:
    return 1.0 / (1.0 + 10 ** ((elo_away - elo_home - home_advantage) / ELO_SCALE))


def actual_score(home_goals: int, away_goals: int) -> tuple:
    """Returns (score_home, score_away) where win=1, draw=0.5, loss=0."""
    if home_goals > away_goals:
        return 1.0, 0.0
    elif home_goals < away_goals:
        return 0.0, 1.0
    else:
        return 0.5, 0.5


def update_elo(elo_home: float, elo_away: float,
               home_goals: int, away_goals: int, stage: str) -> tuple:
    k = k_factor(stage)
    gm = goal_multiplier(home_goals, away_goals)
    e_home = expected_score(elo_home, elo_away)
    e_away = 1.0 - e_home
    s_home, s_away = actual_score(home_goals, away_goals)
    new_home = elo_home + k * gm * (s_home - e_home)
    new_away = elo_away + k * gm * (s_away - e_away)
    return round(new_home, 2), round(new_away, 2)


def compute_elo(matches: pd.DataFrame) -> pd.DataFrame:
    """
    Process matches in chronological order, computing Elo before each match.
    Returns the dataframe with added columns:
      home_elo_before, away_elo_before, home_elo_after, away_elo_after,
      elo_diff (home - away before match)
    """
    # Sort by date; keep original index to re-merge
    df = matches.copy()
    df["_orig_idx"] = df.index

    # Parse date safely
    df["_date_parsed"] = pd.to_datetime(df["date"], errors="coerce")
    df_sorted = df.sort_values("_date_parsed", na_position="last").reset_index(drop=True)

    elo: dict = {}

    home_elo_before = []
    away_elo_before = []
    home_elo_after_list = []
    away_elo_after_list = []

    for _, row in df_sorted.iterrows():
        home = row.get("home_team")
        away = row.get("away_team")
        stage = str(row.get("stage") or "")
        hs = row.get("home_score")
        as_ = row.get("away_score")

        if not home or not away:
            home_elo_before.append(None)
            away_elo_before.append(None)
            home_elo_after_list.append(None)
            away_elo_after_list.append(None)
            continue

        he = elo.get(home, ELO_INIT)
        ae = elo.get(away, ELO_INIT)

        home_elo_before.append(round(he, 2))
        away_elo_before.append(round(ae, 2))

        # Update only if scores are valid
        try:
            hs_int = int(hs)
            as_int = int(as_)
            new_he, new_ae = update_elo(he, ae, hs_int, as_int, stage)
        except (TypeError, ValueError):
            new_he, new_ae = he, ae

        elo[home] = new_he
        elo[away] = new_ae
        home_elo_after_list.append(new_he)
        away_elo_after_list.append(new_ae)

    df_sorted["home_elo"] = home_elo_before
    df_sorted["away_elo"] = away_elo_before
    df_sorted["home_elo_after"] = home_elo_after_list
    df_sorted["away_elo_after"] = away_elo_after_list
    df_sorted["elo_diff"] = df_sorted.apply(
        lambda r: round(r["home_elo"] - r["away_elo"], 2)
        if r["home_elo"] is not None and r["away_elo"] is not None else None,
        axis=1
    )

    # Restore original order
    df_sorted = df_sorted.sort_values("_orig_idx").drop(columns=["_orig_idx", "_date_parsed"])
    return df_sorted


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="data/parsed/matches_all.csv")
    p.add_argument("--out-csv", default="data/parsed/matches_all_with_elo.csv")
    p.add_argument("--out-json", default="data/parsed/matches_all_with_elo.json")
    args = p.parse_args()

    print(f"Leyendo {args.input}...")
    df = pd.read_csv(args.input)
    print(f"  {len(df)} filas cargadas.")

    df_elo = compute_elo(df)

    non_null = df_elo["home_elo"].notna().sum()
    print(f"  Elo calculado para {non_null} partidos.")

    df_elo.to_csv(args.out_csv, index=False)
    df_elo.to_json(args.out_json, orient="records", date_format="iso")
    print(f"Escritos: {args.out_csv}")
    print(f"          {args.out_json}")


if __name__ == "__main__":
    main()
