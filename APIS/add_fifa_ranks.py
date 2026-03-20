#!/usr/bin/env python3
"""
Enrich parsed match files with FIFA rankings.

Usage:
  python add_fifa_ranks.py --matches data/parsed/matches_all.csv \
    --ranks data/fifa_rankings.csv \
    --out-csv data/parsed/matches_all_with_fifa_ranks.csv

The script expects a FIFA rankings CSV with at least these columns:
  - date (YYYY-MM-DD)
  - country (team name matching matches file)
  - rank (integer ranking: 1,2,3...)

It will add `home_rank`, `away_rank`, `home_rank_date`, `away_rank_date`, and `rank_source`.
"""

import argparse
import pandas as pd
import sys


def load_rankings(path):
    df = pd.read_csv(path, parse_dates=["date"]) 
    df.columns = [c.strip() for c in df.columns]
    if "country" not in df.columns and "team" in df.columns:
        df = df.rename(columns={"team": "country"})
    # try common alternatives for rank column
    if "rank" not in df.columns:
        for alt in ("position", "ranking", "rank_pos"):
            if alt in df.columns:
                df = df.rename(columns={alt: "rank"})
                break
    if "rank" not in df.columns:
        raise SystemExit("Could not find a 'rank' column in rankings file")
    df = df[["date", "country", "rank"]].dropna(subset=["country", "date"]) 
    df = df.sort_values(["country", "date"]) 
    return df


def build_lookup(df):
    lookup = {}
    for country, g in df.groupby("country"):
        lookup[country] = g.reset_index(drop=True)
    return lookup


def find_latest_rank(lookup, country, match_ts):
    """Return (rank, rank_date_iso) or (None, None). match_ts is pd.Timestamp."""
    if country not in lookup:
        return None, None
    g = lookup[country]
    rows = g[g["date"] <= match_ts]
    if rows.empty:
        return None, None
    row = rows.iloc[-1]
    r = int(row["rank"]) if pd.notna(row["rank"]) else None
    return r, row["date"].date().isoformat()


def enrich(matches_path, ranks_path, out_csv, out_json):
    matches = pd.read_csv(matches_path, parse_dates=["date"]) 
    ranks = load_rankings(ranks_path)
    lookup = build_lookup(ranks)

    for c in ("home_team", "away_team"):
        if c not in matches.columns:
            raise SystemExit(f"Column {c} not found in {matches_path}")

    home_ranks = []
    away_ranks = []
    home_rank_dates = []
    away_rank_dates = []

    for _, row in matches.iterrows():
        match_ts = pd.to_datetime(row["date"]) 
        home = row["home_team"]
        away = row["away_team"]
        hr, hdate = find_latest_rank(lookup, home, match_ts)
        ar, adate = find_latest_rank(lookup, away, match_ts)
        home_ranks.append(hr)
        away_ranks.append(ar)
        home_rank_dates.append(hdate)
        away_rank_dates.append(adate)

    matches["home_rank"] = home_ranks
    matches["away_rank"] = away_ranks
    matches["home_rank_date"] = home_rank_dates
    matches["away_rank_date"] = away_rank_dates
    matches["rank_source"] = "FIFA"

    matches.to_csv(out_csv, index=False)
    matches.to_json(out_json, orient="records", date_format="iso")
    print(f"Wrote {out_csv} and {out_json}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--matches", default="data/parsed/matches_all.csv")
    p.add_argument("--ranks", default="data/fifa_rankings.csv")
    p.add_argument("--out-csv", default="data/parsed/matches_all_with_fifa_ranks.csv")
    p.add_argument("--out-json", default="data/parsed/matches_all_with_fifa_ranks.json")
    args = p.parse_args()
    enrich(args.matches, args.ranks, args.out_csv, args.out_json)


if __name__ == "__main__":
    main()
