"""Load the complete fingerprinted season without altering raw input."""
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
VERSION=json.loads((ROOT/'app/version.json').read_text(encoding='utf-8'))['prototype_version']


def load_snapshot():
    taxonomy=json.loads((ROOT/'fpl_data_taxonomy.json').read_text(encoding='utf-8'))
    config=json.loads((ROOT/'app/config.json').read_text(encoding='utf-8'))
    source=(ROOT/config['source_csv']).resolve()
    if not source.is_relative_to(ROOT):
        raise ValueError('Source path escapes the repository')
    if hashlib.sha256(source.read_bytes()).hexdigest()!=config['source_sha256']:
        raise ValueError('Raw source fingerprint changed')
    with source.open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.DictReader(stream)
        if reader.fieldnames!=taxonomy['original_column_order']:
            raise ValueError('Unexpected CSV schema')
        raw=list(reader)
    history=[]
    seen=set()
    for row in raw:
        token=tuple(row.values())
        if token not in seen:
            seen.add(token)
            history.append(row)
    print(f'[load] {len(raw)} raw fixture rows')
    print(f'[dedup] {len(raw)} -> {len(history)}; fully identical copies only')
    keys=[(r['element'],r['fixture']) for r in history]
    if len(set(keys))!=len(keys):
        raise ValueError('Conflicting player-fixture records')
    for row in history:
        for field in ('GW','element','fixture','minutes','total_points','value'):
            number=float(row[field])
            if not math.isfinite(number) or not number.is_integer():
                raise ValueError(f'Invalid integer: {field}')
        if (not 1<=int(row['GW'])<=38 or int(row['value'])<=0 or
                int(row['minutes'])<0 or int(row['element'])<1 or int(row['fixture'])<1):
            raise ValueError('Invalid gameweek, price, minutes or identifier')
        if row['round']!=row['GW'] or row['position'] not in taxonomy['fields']['position']['allowed_values']:
            raise ValueError('Invalid round or position')
        for field in ('expected_goals','expected_assists'):
            if row[field]=='':
                continue
            number=float(row[field])
            if not math.isfinite(number) or number<0:
                raise ValueError(f'Invalid {field}')
    available={int(row['GW']) for row in history}
    if available!=set(range(config['first_gameweek'],config['last_gameweek']+1)):
        raise ValueError('Configured season coverage does not match raw gameweeks')
    return {'scenario':config,'players':list(catalogue_at(history,config['last_gameweek']).values())},history


def catalogue_at(history,end):
    eligible=[row for row in history if int(row['GW'])<=end]
    print(f'[price cutoff] {len(history)} -> {len(eligible)} fixture rows at/before GW{end}')
    players={}
    for row in sorted(eligible,key=lambda r:(int(r['GW']),r['kickoff_time'],int(r['fixture']))):
        players[str(row['element'])]={'id':str(row['element']),'name':row['name'],
            'team':row['team'],'position':row['position'],'price':float(row['value'])/10,
            'price_gameweek':int(row['GW'])}
    print(f'[catalogue] {len(eligible)} fixture rows -> {len(players)} player snapshots')
    return players
