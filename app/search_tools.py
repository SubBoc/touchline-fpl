"""Historical season research with inclusive gameweek intervals."""
import math
from snapshot import VERSION,catalogue_at

METRICS=('points_per_million','points','xg_per90','xa_per90','xgi_per90')
POSITIONS=('MID','FWD')


class ResearchTools:
    def __init__(self,data=None,history=None):
        if data is None:
            from snapshot import load_snapshot
            data,history=load_snapshot()
        self.config=data['scenario']
        self.history=history or []
        self.first,self.last=self.config['first_gameweek'],self.config['last_gameweek']
        if any(not self.first<=int(row['GW'])<=self.last for row in self.history):
            raise ValueError('History outside configured coverage')
        keys=[(str(row['element']),str(row['fixture'])) for row in self.history]
        if len(set(keys))!=len(keys):
            raise ValueError('Duplicate player-fixture records')
        self.players={str(p['id']):p for p in data['players']}

    def describe_snapshot(self):
        return {'prototype_version':VERSION,'season':self.config['season'],
            'first_gameweek':self.first,'last_completed_gameweek':self.last,
            'available_positions':list(POSITIONS),'available_metrics':list(METRICS),
            'period_contract':'inclusive start_gameweek/end_gameweek OR trailing window_gameweeks',
            'price_basis':'latest recorded fixture-row price at/before requested end gameweek',
            'is_live':False,'forecast_available':False,
            'limitations':['injury availability is unknown','historical prices are not live or verified deadline-time prices',
                           'recorded prices may predate the interval end','statistics describe played matches, not future returns']}

    @staticmethod
    def _limit(limit):
        if type(limit) is not int or not 1<=limit<=10:
            raise ValueError('limit must be an integer from 1 to 10')
        return limit

    def resolve_period(self,window_gameweeks=None,start_gameweek=None,end_gameweek=None):
        if start_gameweek is not None or end_gameweek is not None:
            if window_gameweeks is not None:
                raise ValueError('Choose an explicit interval OR a trailing window, not both')
            if type(start_gameweek) is not int or type(end_gameweek) is not int:
                raise ValueError('Supply both inclusive start_gameweek and end_gameweek as integers')
            start,end=start_gameweek,end_gameweek
        else:
            length=self.config.get('default_window_gameweeks',5) if window_gameweeks is None else window_gameweeks
            if type(length) is not int or length<1:
                raise ValueError('window_gameweeks must be a positive integer')
            start,end=self.last-length+1,self.last
        if not self.first<=start<=end<=self.last:
            raise ValueError(f'Interval must lie within GW{self.first}–{self.last}')
        return start,end

    def lookup_players(self,query,limit=5):
        if not isinstance(query,str) or not query.strip():
            raise ValueError('A non-empty player or club search is required')
        limit=self._limit(limit)
        pool=[p for p in self.players.values() if query.strip().casefold() in p['name'].casefold()
              or query.strip().casefold() in p['team'].casefold()]
        print(f'[lookup filter] {len(self.players)} -> {len(pool)} name/club matches')
        selected=sorted(pool,key=lambda p:(p['name'],p['id']))[:limit]
        print(f'[lookup limit] {len(pool)} -> {len(selected)} records')
        return {'matches':[{k:p[k] for k in ('id','name','position','team')} for p in selected],
            'matching_count':len(pool),'truncated':len(pool)>limit,
            'note':'Identity lookup only; use a statistics tool for period-specific prices and results.'}

    @staticmethod
    def _number(value):
        try:
            number=float(value)
            return number if math.isfinite(number) else None
        except (TypeError,ValueError):
            return None

    def _evidence(self,identity,player,rows,start,end):
        warnings=[]
        def total(field):
            if player is None:
                return None
            values=[self._number(row.get(field)) for row in rows]
            if any(v is None for v in values):
                warnings.append(f'missing or invalid {field}; aggregate unavailable')
                return None
            return sum(values)
        minutes,points=total('minutes'),total('total_points')
        xg,xa=total('expected_goals'),total('expected_assists')
        price=player['price'] if player else None
        if price is not None and (not math.isfinite(price) or price<=0):
            raise ValueError('Historical price must be finite and positive')
        if player is None:
            warnings.append('no record at/before interval end; future prices/statistics not substituted')
        elif not rows:
            warnings.append('no fixture rows in interval; absent gameweeks contribute zero totals')
        if player and player['price_gameweek']<end:
            warnings.append('latest recorded price predates interval end')
        rate=lambda value:90*value/minutes if minutes and value is not None else None
        return {'id':identity['id'],'name':identity['name'],'position':identity['position'],
            'team':player['team'] if player else None,'price_millions':price,
            'price_gameweek':player['price_gameweek'] if player else None,
            'window_start_gw':start,'window_end_gw':end,'minutes':minutes,'points':points,
            'xg':xg,'xa':xa,'points_per_million':points/price if price and points is not None else None,
            'xg_per90':rate(xg),'xa_per90':rate(xa),
            'xgi_per90':rate(xg+xa) if xg is not None and xa is not None else None,'warnings':warnings}

    def find_players(self,position,max_price_millions,metric='points_per_million',window_gameweeks=None,
                     minimum_minutes=None,limit=5,price_inclusive=True,start_gameweek=None,end_gameweek=None):
        if position not in POSITIONS:
            raise ValueError('Research supports MID and FWD only')
        price=self._number(max_price_millions)
        if isinstance(max_price_millions,bool) or price is None or price<=0:
            raise ValueError('Specify a positive budget in millions')
        if metric not in METRICS:
            raise ValueError('Unknown ranking metric')
        if minimum_minutes is None:
            minimum_minutes=self.config.get('minimum_minutes',180)
        if type(minimum_minutes) is not int or minimum_minutes<0 or type(price_inclusive) is not bool:
            raise ValueError('Invalid minutes floor or price bound')
        limit=self._limit(limit)
        start,end=self.resolve_period(window_gameweeks,start_gameweek,end_gameweek)
        catalogue=catalogue_at(self.history,end)
        pool=[p for p in catalogue.values() if p['position']==position and
              (p['price']<=price if price_inclusive else p['price']<price)]
        print(f'[candidate filter] {len(catalogue)} -> {len(pool)} position/price candidates')
        rows=[r for r in self.history if start<=int(r['GW'])<=end]
        print(f'[interval filter] {len(self.history)} -> {len(rows)} fixture rows for GW{start}–{end}')
        grouped={}
        for row in rows:
            grouped.setdefault(str(row['element']),[]).append(row)
        records=[self._evidence(p,p,grouped.get(p['id'],[]),start,end) for p in pool]
        eligible=[p for p in records if p['minutes'] is not None and p['minutes']>=minimum_minutes and p[metric] is not None]
        print(f'[evidence filter] {len(records)} -> {len(eligible)} eligible records')
        eligible.sort(key=lambda p:(-p[metric],-p['minutes'],p['name'],p['id']))
        selected=eligible[:limit]
        print(f'[shortlist limit] {len(eligible)} -> {len(selected)} records')
        return {'snapshot':self.describe_snapshot(),'constraints':{'position':position,'max_price_millions':price,
            'price_inclusive':price_inclusive,'metric':metric,'start_gameweek':start,'end_gameweek':end,
            'minimum_minutes':minimum_minutes},'eligible_count':len(eligible),'players':selected,
            'interpretation':'Historical research; prices at/before interval end; no forecast'}

    def compare_players(self,player_ids,window_gameweeks=None,start_gameweek=None,end_gameweek=None):
        if not isinstance(player_ids,list) or not 1<=len(player_ids)<=3:
            raise ValueError('Compare one to three observed player IDs')
        ids=[str(x) for x in player_ids]
        if len(set(ids))!=len(ids) or any(x not in self.players for x in ids):
            raise ValueError('Unknown or duplicate player IDs')
        if any(self.players[x]['position'] not in POSITIONS for x in ids):
            raise ValueError('Research supports MID and FWD only')
        start,end=self.resolve_period(window_gameweeks,start_gameweek,end_gameweek)
        catalogue=catalogue_at(self.history,end)
        rows=[r for r in self.history if str(r['element']) in ids and start<=int(r['GW'])<=end]
        print(f'[comparison filter] {len(self.history)} -> {len(rows)} player/interval fixture rows')
        players=[self._evidence(self.players[x],catalogue.get(x),[r for r in rows if str(r['element'])==x],start,end) for x in ids]
        result={'snapshot':self.describe_snapshot(),'players':players}
        if len(players)==2:
            result['second_minus_first']={key:round(players[1][key]-players[0][key],8)
                if all(p[key] is not None for p in players) else None for key in ('points','minutes','price_millions')}
        return result
