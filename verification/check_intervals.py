"""Separate pandas recomputation from raw CSV; no hosted model calls.

Generated and run by Codex. This is automated cross-check evidence, not a new
owner-executed or independently authored verification.
"""
import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
from search_tools import ResearchTools


def main():
    taxonomy=json.loads((ROOT/'fpl_data_taxonomy.json').read_text(encoding='utf-8'))
    config=json.loads((ROOT/'app/config.json').read_text(encoding='utf-8'))
    source=ROOT/config['source_csv']
    source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    assert source_hash==config['source_sha256']
    raw=pd.read_csv(source,encoding='utf-8-sig',dtype={'element':'string'})
    assert list(raw.columns)==taxonomy['original_column_order']
    clean=raw.drop_duplicates().copy()
    print(f'[pandas dedup] {len(raw)} -> {len(clean)}; exact full-row duplicates only')
    assert not clean.duplicated(['element','fixture']).any()
    for field in ('GW','fixture','minutes','total_points','expected_goals','expected_assists','value'):
        clean[field]=pd.to_numeric(clean[field],errors='raise')
    tools=ResearchTools()
    report={'producer':'verification/check_intervals.py','prototype_version':'v4',
            'source_csv':config['source_csv'],'source_sha256':source_hash,
            'raw_rows':len(raw),'deduplicated_rows':len(clean),'python':sys.version.split()[0],
            'pandas':pd.__version__,'method':'Separate pandas aggregation of raw CSV versus stdlib tools; same author, automated execution.','cases':[]}

    def frame(start,end):
        prior=clean.loc[clean['GW'].le(end)].copy()
        print(f'[pandas price filter] {len(clean)} -> {len(prior)} rows through GW{end}')
        latest=prior.sort_values(['GW','kickoff_time','fixture']).drop_duplicates('element',keep='last').set_index('element')
        print(f'[pandas snapshot] {len(prior)} -> {len(latest)} players')
        window=clean.loc[clean['GW'].between(start,end)].copy()
        print(f'[pandas window] {len(clean)} -> {len(window)} rows for GW{start}–{end}')
        grouped=window.groupby('element').agg(
            minutes=('minutes',lambda s:s.sum(min_count=len(s))),
            points=('total_points',lambda s:s.sum(min_count=len(s))),
            xg=('expected_goals',lambda s:s.sum(min_count=len(s))),
            xa=('expected_assists',lambda s:s.sum(min_count=len(s))),
            fixture_count=('fixture','size'))
        print(f'[pandas aggregate] {len(window)} -> {len(grouped)} players with interval rows')
        result=latest[['name','position','team','value','GW']].join(grouped,validate='one_to_one')
        print(f'[pandas join] {len(latest)} -> {len(result)} player records')
        empty=result['fixture_count'].isna()
        result.loc[empty,['minutes','points','xg','xa']]=0
        result['price_millions']=result['value']/10
        result['price_gameweek']=result['GW']
        result['points_per_million']=result['points']/result['price_millions']
        denominator=result['minutes'].where(result['minutes'].gt(0))
        for name in ('xg','xa'):
            result[name+'_per90']=90*result[name]/denominator
        result['xgi_per90']=90*(result['xg']+result['xa'])/denominator
        return result

    def compare_values(actual,expected,start,end):
        assert (actual['window_start_gw'],actual['window_end_gw'])==(start,end)
        for field in ('minutes','points','xg','xa','price_millions','price_gameweek',
                      'points_per_million','xg_per90','xa_per90','xgi_per90'):
            value=expected[field]
            if pd.isna(value):
                assert actual[field] is None,(field,actual[field],value)
            else:
                assert actual[field] is not None and math.isclose(actual[field],float(value),rel_tol=1e-10,abs_tol=1e-10),(field,actual[field],value)
        for field in ('name','position','team'):
            assert actual[field]==expected[field]

    for start,end in ((1,5),(1,10),(15,19),(34,38),(1,38)):
        expected=frame(start,end)
        with contextlib.redirect_stdout(io.StringIO()):
            actual=tools.compare_players(['668','329'],start_gameweek=start,end_gameweek=end)
        for player in actual['players']:
            compare_values(player,expected.loc[player['id']],start,end)
        report['cases'].append({'kind':'named-player comparison','start_gameweek':start,
                                'end_gameweek':end,'players':actual['players'],'status':'PASS'})
    for start,end,metric in ((1,38,'points'),(1,19,'points'),(1,5,'points'),(34,38,'xgi_per90')):
        expected=frame(start,end)
        pool=expected.loc[expected['position'].eq('MID') & expected['price_millions'].le(6)
                          & expected['minutes'].ge(180) & expected[metric].notna()].reset_index()
        print(f'[pandas eligibility] {len(expected)} -> {len(pool)} MID/price/minutes records')
        ordered=pool.sort_values([metric,'minutes','name','element'],ascending=[False,False,True,True]).head(5)
        print(f'[pandas limit] {len(pool)} -> {len(ordered)} shortlisted players')
        with contextlib.redirect_stdout(io.StringIO()):
            actual=tools.find_players('MID',6,metric=metric,start_gameweek=start,end_gameweek=end)
        assert actual['eligible_count']==len(pool)
        assert [p['id'] for p in actual['players']]==ordered['element'].tolist()
        for player in actual['players']:
            compare_values(player,expected.loc[player['id']],start,end)
        report['cases'].append({'kind':'MID shortlist','metric':metric,'budget_millions':6,
            'start_gameweek':start,'end_gameweek':end,'eligible_count':len(pool),'players':actual['players'],'status':'PASS'})
    report['status']='PASS'
    target=ROOT/'results/local/raw_recomputation.json'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print('Saved pandas cross-checks: '+str(target.relative_to(ROOT)))


if __name__=='__main__':
    main()
