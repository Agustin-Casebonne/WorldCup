#!/usr/bin/env python3
import re
import os
import csv
import json
import argparse
from pathlib import Path

MONTH_MAP = {
    'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
    'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
    'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12',
}

_MN = (
    r'Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
    r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?'
)

# Standalone date line (month-first): "July 13", "Sun Nov 20"
_STANDALONE_DATE_RE = re.compile(
    r'^(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\.?\s+)?(' + _MN + r')\s+(\d{1,2})(?:[-\u2013]\d{1,2})?\s*$',
    re.IGNORECASE,
)

# Inline date at start of line (day-first): "16 June  ", "31 May  "
_INLINE_DATE_RE = re.compile(r'^(\d{1,2})\s+(' + _MN + r')\s+', re.IGNORECASE)

# Bullet stage prefix lines: "▪ Group A", "▪ Semi-finals"
_BULLET_RE = re.compile(r'^[\u25aa\u2022*]+\s+(.+)')

# Plain stage keyword lines (only when no X-Y score in line)
_PLAIN_STAGE_RE = re.compile(
    r'^(?:Group|Round|Quarter|Semi|Third|Final|Playoff|Play.off|Matchday)\b',
    re.IGNORECASE,
)

_CSV_FIELDS = ['tournament', 'stage', 'date', 'home_team', 'away_team',
               'home_score', 'away_score', 'venue', 'winner']


def parse_cup_file(path, tournament_name):
    matches = []
    current_stage = None
    current_date = None
    year = tournament_name.split('--')[0] if '--' in tournament_name else None

    with path.open(encoding='utf-8', errors='ignore') as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            # Skip title / comment lines
            if line.startswith('=') or line.startswith('#'):
                continue
            # Strip match number prefix: "(3)" or "(14)"
            line = re.sub(r'^\(\d+\)\s*', '', line).strip()
            if not line:
                continue
            # Bullet stage header (▪ Group A / ▪ Semi-finals)
            bm = _BULLET_RE.match(line)
            if bm:
                current_stage = bm.group(1).split('|')[0].strip()
                continue
            # Skip group membership / schedule table lines (contain '|' but no bullet)
            if '|' in line:
                continue
            # Standalone date: "July 13", "Sun Nov 20"
            sdm = _STANDALONE_DATE_RE.match(line)
            if sdm:
                month_num = MONTH_MAP.get(sdm.group(1)[:3].lower(), '00')
                current_date = f'{year}-{month_num}-{sdm.group(2).zfill(2)}' if year else None
                continue
            # Inline date at start: "16 June ...", "31 May ..."
            idm = _INLINE_DATE_RE.match(line)
            if idm:
                month_num = MONTH_MAP.get(idm.group(2)[:3].lower(), '00')
                current_date = f'{year}-{month_num}-{idm.group(1).zfill(2)}' if year else None
                line = line[idm.end():].strip()
            # Strip time prefix: "19:00 ..."
            line = re.sub(r'^\d{1,2}:\d{2}\s+', '', line).strip()
            if not line:
                continue
            # Plain stage keyword (must have no X-Y score in line)
            if _PLAIN_STAGE_RE.match(line) and not re.search(r'\b\d+[-\u2013\u2014]\d+\b', line):
                current_stage = line.strip()
                continue
            # Skip scorer notes starting with '('
            if line.startswith('('):
                continue
            # Split venue
            venue = None
            if ' @ ' in line:
                line, venue = line.split(' @ ', 1)
                line = line.strip()
                venue = venue.strip()
            # Find the main score X-Y
            sm = re.search(r'\b(\d+)[-\u2013\u2014](\d+)\b', line)
            if not sm:
                continue
            home = line[:sm.start()].strip()
            home_score = int(sm.group(1))
            away_score = int(sm.group(2))
            rest = line[sm.end():].strip()
            # Strip a.e.t. / halftime notation — find first uppercase char as team start
            nm = re.match(r'^[^A-Z\u00C0-\u00D6\u00D8-\u00DE]*(.+)$', rest)
            away = nm.group(1).strip() if nm else rest.strip()
            away = re.sub(r'\s*\(.*\)$', '', away).strip()
            if not home or not away:
                continue
            winner = home if home_score > away_score else (away if away_score > home_score else 'Draw')
            matches.append({
                'tournament': tournament_name,
                'stage': current_stage,
                'date': current_date,
                'home_team': home,
                'away_team': away,
                'home_score': home_score,
                'away_score': away_score,
                'venue': venue,
                'winner': winner,
            })
    return matches


def discover_and_parse(data_dir, out_dir, import_mongo=False, mongo_uri=None, db_name=None):
    out_dir.mkdir(parents=True, exist_ok=True)
    all_matches = []
    per_year = {}
    for root, dirs, files in os.walk(data_dir):
        for fname in files:
            if fname.lower() in ('cup.txt', 'cup_finals.txt'):
                full = Path(root) / fname
                tournament_name = Path(root).name
                print(f'Parsing {full} as tournament {tournament_name}')
                ms = parse_cup_file(full, tournament_name)
                if ms:
                    year = tournament_name.split('--')[0] if '--' in tournament_name else tournament_name
                    per_year.setdefault(year, []).extend(ms)
                    all_matches.extend(ms)
    for year, ms in per_year.items():
        (out_dir / f'matches_{year}.json').write_text(
            json.dumps(ms, ensure_ascii=False, indent=2), encoding='utf-8')
        csv_file = out_dir / f'matches_{year}.csv'
        with csv_file.open('w', newline='', encoding='utf-8') as fh:
            w = csv.DictWriter(fh, fieldnames=_CSV_FIELDS, extrasaction='ignore')
            w.writeheader()
            w.writerows(ms)
        print(f'Wrote {len(ms)} rows for {year}')
    combined_json = out_dir / 'matches_all.json'
    combined_json.write_text(json.dumps(all_matches, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Wrote {len(all_matches)} matches to {combined_json}')
    combined_csv = out_dir / 'matches_all.csv'
    with combined_csv.open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=_CSV_FIELDS, extrasaction='ignore')
        w.writeheader()
        w.writerows(all_matches)
    print(f'Wrote combined CSV to {combined_csv}')
    if import_mongo:
        try:
            from pymongo import MongoClient
        except Exception:
            print('pymongo not available')
            return
        client = MongoClient(mongo_uri)
        db = client[db_name]
        if all_matches:
            db['matches'].insert_many(all_matches)
            print(f'Inserted {len(all_matches)} docs into {db_name}.matches')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Parse openfootball cup files to JSON/CSV')
    ap.add_argument('--data-dir', default='data/openfootball')
    ap.add_argument('--out-dir', default='data/parsed')
    ap.add_argument('--import-mongo', action='store_true')
    ap.add_argument('--mongo-uri')
    ap.add_argument('--db', default='worldcup')
    args = ap.parse_args()
    if args.import_mongo and not args.mongo_uri:
        ap.error('--import-mongo requires --mongo-uri')
    discover_and_parse(Path(args.data_dir), Path(args.out_dir),
                       import_mongo=args.import_mongo, mongo_uri=args.mongo_uri, db_name=args.db)
