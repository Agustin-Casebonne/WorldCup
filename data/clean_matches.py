#!/usr/bin/env python3
import re
import argparse
from pymongo import MongoClient, UpdateOne


def extract_team_name(s: str):
    if not s:
        return None
    # remove parenthesis content and trailing venue after '@'
    s = re.sub(r"\(.*?\)", "", s)
    s = s.split('@')[0]
    # keep unicode letters, spaces, hyphens, apostrophes
    matches = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿñÑçÇ'’·\-]+(?:\s+[A-Za-zÀ-ÖØ-öø-ÿñÑçÇ'’·\-]+)*", s)
    if not matches:
        return s.strip()
    # pick the longest plausible match
    name = max(matches, key=len).strip()
    name = re.sub(r"\s+", " ", name)
    return name


def parse_score(v):
    if v is None:
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    s = str(v)
    m = re.search(r"(\d+)", s)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    return None


def clean_winner_field(winner_raw, home_score, away_score, home_team, away_team):
    # try to extract winner from existing field
    if winner_raw:
        name = extract_team_name(str(winner_raw))
        if name:
            return name
    # fallback to derive from scores
    if home_score is not None and away_score is not None:
        if home_score > away_score:
            return home_team
        if away_score > home_score:
            return away_team
    return None


def normalize_stage(stage):
    if not stage:
        return None
    s = str(stage)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def main():
    parser = argparse.ArgumentParser(description='Clean and normalize matches collection')
    parser.add_argument('--mongo-uri', default='mongodb://localhost:27017', help='MongoDB URI')
    parser.add_argument('--db', default='worldcup', help='Database name')
    parser.add_argument('--collection', default='matches', help='Collection name')
    parser.add_argument('--batch', type=int, default=500, help='Bulk write batch size')
    parser.add_argument('--dry-run', action='store_true', help='Do not write changes, only show samples')
    parser.add_argument('--limit', type=int, default=0, help='Limit processed documents (0 = all)')
    args = parser.parse_args()

    client = MongoClient(args.mongo_uri)
    db = client[args.db]
    coll = db[args.collection]

    query = {}
    cursor = coll.find(query)
    if args.limit > 0:
        cursor = cursor.limit(args.limit)

    bulk_ops = []
    changed = 0
    inspected = 0

    for doc in cursor:
        inspected += 1
        updates = {}
        # clean teams
        home_raw = doc.get('home_team')
        away_raw = doc.get('away_team')
        home_clean = extract_team_name(home_raw) if home_raw is not None else None
        away_clean = extract_team_name(away_raw) if away_raw is not None else None

        if home_clean and home_clean != (home_raw or '').strip():
            updates['home_team'] = home_clean
        if away_clean and away_clean != (away_raw or '').strip():
            updates['away_team'] = away_clean

        # scores
        home_score = parse_score(doc.get('home_score'))
        away_score = parse_score(doc.get('away_score'))
        if home_score is not None and home_score != doc.get('home_score'):
            updates['home_score'] = home_score
        if away_score is not None and away_score != doc.get('away_score'):
            updates['away_score'] = away_score

        # normalize stage
        stage_clean = normalize_stage(doc.get('stage'))
        if stage_clean and stage_clean != (doc.get('stage') or '').strip():
            updates['stage'] = stage_clean

        # winner
        winner_clean = clean_winner_field(doc.get('winner'), home_score, away_score, home_clean or doc.get('home_team'), away_clean or doc.get('away_team'))
        if winner_clean and winner_clean != (doc.get('winner') or '').strip():
            updates['winner'] = winner_clean

        if updates:
            changed += 1
            if args.dry_run:
                print('DOC _id=', doc.get('_id'))
                print(' BEFORE:', {k: doc.get(k) for k in updates.keys()})
                print(' AFTER :', updates)
                print('---')
            else:
                bulk_ops.append(UpdateOne({'_id': doc['_id']}, {'$set': updates}))

        if not args.dry_run and len(bulk_ops) >= args.batch:
            coll.bulk_write(bulk_ops)
            print(f'Applied {len(bulk_ops)} updates...')
            bulk_ops = []

    if not args.dry_run and bulk_ops:
        coll.bulk_write(bulk_ops)
        print(f'Applied final {len(bulk_ops)} updates.')

    print(f'Inspected {inspected} documents, changed {changed} documents (dry_run={args.dry_run}).')


if __name__ == '__main__':
    main()
