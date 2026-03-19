#!/usr/bin/env python3
"""
mongo_ingest.py

Improved ingest script: normaliza tipos, añade campos derivados útiles para ML
y permite previsualizar antes de insertar.

Campos añadidos/normalizados:
 - `date`: Python `datetime` (BSON Date)
 - `home_rank`, `away_rank`: ints o `None`
 - `home_rank_obj`, `away_rank_obj`: {rank:int, rank_date:datetime}
 - `rank_diff`: home_rank - away_rank (int o None)
 - `is_home_favourite`: True/False/None
 - `home_days_since_last_match`, `away_days_since_last_match`: int o None
 - `ingested_at`: datetime UTC

Usage examples:
  # preview first doc without inserting
  python mongo_ingest.py --input data/parsed/matches_all_with_fifa_ranks.json --preview

  # insert to local MongoDB
  python mongo_ingest.py --input data/parsed/matches_all_with_fifa_ranks.json \
    --mongo-uri mongodb://localhost:27017 --db worldcup --collection matches

"""

import argparse
import json
import csv
import os
from datetime import datetime, timezone
from pymongo import MongoClient
from typing import List, Dict, Any, Optional


def load_json(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_csv(path: str) -> List[Dict[str, Any]]:
    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def parse_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    # Try ISO first
    try:
        return datetime.fromisoformat(s)
    except Exception:
        pass
    # Try common date formats
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    # Last resort: try parsing YYYY-MM
    try:
        return datetime.strptime(s, "%Y-%m")
    except Exception:
        return None


def to_int(v: Optional[Any]) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, int):
        return v
    s = str(v).strip()
    if s == "":
        return None
    try:
        return int(float(s))
    except Exception:
        return None


import re

def _is_valid_row(r: Dict[str, Any]) -> bool:
    """Return False for rows that are clearly malformed/corrupt."""
    home = (r.get('home_team') or '').strip()
    away = (r.get('away_team') or '').strip()
    if not home or not away:
        return False
    # date lines baked into field: 'Fri Jun/9   Germany', 'Mon Jun/12 ...'
    if re.match(r'^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s', home):
        return False
    # match summary on one line: 'Brazil v Croatia'
    if ' v ' in home or ' v ' in away:
        return False
    # single punct/char away_team like ')'
    if len(away) <= 2 and not away.isalpha():
        return False
    return True


def normalize_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    skipped = 0
    norm = []
    for r in rows:
        # skip rows with corrupt team names (date lines baked into field)
        if not _is_valid_row(r):
            skipped += 1
            continue
        doc = dict(r)  # shallow copy
        # parse date
        doc_date = parse_date(r.get('date'))
        if doc_date:
            doc['date'] = doc_date
        # scores
        doc['home_score'] = to_int(r.get('home_score'))
        doc['away_score'] = to_int(r.get('away_score'))
        # ranks
        hr = to_int(r.get('home_rank'))
        ar = to_int(r.get('away_rank'))
        doc['home_rank'] = hr
        doc['away_rank'] = ar
        # rank dates
        hrd = parse_date(r.get('home_rank_date'))
        ard = parse_date(r.get('away_rank_date'))
        doc['home_rank_obj'] = {'rank': hr, 'rank_date': hrd} if (hr is not None or hrd) else None
        doc['away_rank_obj'] = {'rank': ar, 'rank_date': ard} if (ar is not None or ard) else None
        doc['rank_source'] = r.get('rank_source') or 'FIFA'
        norm.append(doc)
    if skipped:
        print(f'Skipped {skipped} malformed rows (corrupt team names).')
    return norm


def compute_derived(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Sort by date to compute days since last match per team
    rows_sorted = sorted(rows, key=lambda x: x.get('date') or datetime.min)
    last_date = {}
    for doc in rows_sorted:
        home = doc.get('home_team')
        away = doc.get('away_team')
        date = doc.get('date')
        # days since last match
        def days_since(team):
            if team is None or date is None:
                return None
            prev = last_date.get(team)
            if prev is None:
                return None
            return (date - prev).days

        doc['home_days_since_last_match'] = days_since(home)
        doc['away_days_since_last_match'] = days_since(away)

        # update last_date after computing for both teams
        if home:
            last_date[home] = date
        if away:
            last_date[away] = date

        # rank diff and favourite
        hr = doc.get('home_rank')
        ar = doc.get('away_rank')
        if hr is not None and ar is not None:
            doc['rank_diff'] = hr - ar
            doc['is_home_favourite'] = True if hr < ar else False
        else:
            doc['rank_diff'] = None
            doc['is_home_favourite'] = None

        # ingested timestamp (timezone-aware UTC)
        doc['ingested_at'] = datetime.now(timezone.utc)

    return rows_sorted


def preview_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    # convert datetimes to ISO for pretty print
    out = {}
    for k, v in doc.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        elif isinstance(v, dict):
            out[k] = {kk: (vv.isoformat() if isinstance(vv, datetime) else vv) for kk, vv in v.items()}
        else:
            out[k] = v
    return out


def insert_documents(docs: List[Dict[str, Any]], mongo_uri: str, db_name: str, coll_name: str, batch_size: int = 1000):
    client = MongoClient(mongo_uri)
    # detect existing DB with different case and use its exact name to avoid MongoDB error
    try:
        existing = client.list_database_names()
        for n in existing:
            if n.lower() == db_name.lower() and n != db_name:
                db_name = n
                break
    except Exception:
        pass
    db = client[db_name]
    coll = db[coll_name]
    total = 0
    for i in range(0, len(docs), batch_size):
        batch = docs[i:i+batch_size]
        res = coll.insert_many(batch)
        total += len(res.inserted_ids)
    return total


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', default='data/parsed/matches_all_with_elo.json')
    p.add_argument('--format', choices=['json', 'csv'], default='json')
    p.add_argument('--mongo-uri', default=os.environ.get('MONGO_URI', 'mongodb://localhost:27017'))
    p.add_argument('--db', default='worldcup')
    p.add_argument('--collection', default='matches')
    p.add_argument('--batch-size', type=int, default=1000)
    p.add_argument('--preview', action='store_true', help='Print one sample document and exit')
    args = p.parse_args()

    if args.format == 'json':
        rows = load_json(args.input)
    else:
        rows = load_csv(args.input)

    norm = normalize_rows(rows)
    docs = compute_derived(norm)

    if args.preview:
        if docs:
            print(json.dumps(preview_doc(docs[0]), ensure_ascii=False, indent=2))
        else:
            print('{}')
        return

    if not docs:
        print('No documents to insert.')
        return

    total = insert_documents(docs, args.mongo_uri, args.db, args.collection, args.batch_size)
    print(f'Inserted {total} documents into {args.db}.{args.collection}')


if __name__ == '__main__':
    main()
