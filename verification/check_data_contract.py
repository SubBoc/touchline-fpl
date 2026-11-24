"""Check dictionary/runtime agreement using real inputs and declared metric rules.

No model requests. Reference frames are explicit: current dictionary, runtime
interfaces, cleaned raw fixture rows and named synthetic fixture frames.
"""
import contextlib
import ast
from datetime import datetime, timedelta, timezone
import hashlib
import inspect
import io
import json
import math
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))


def main():
    taxonomy_file = ROOT / 'fpl_data_taxonomy.json'
    taxonomy = json.loads(taxonomy_file.read_text(encoding='utf-8'))
    config = json.loads((ROOT / 'app/config.json').read_text(encoding='utf-8'))
    version = json.loads((ROOT / 'app/version.json').read_text(encoding='utf-8'))['prototype_version']
    source = ROOT / config['source_csv']
    raw_before = hashlib.sha256(source.read_bytes()).hexdigest()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8]
    output = ROOT / 'results/local' / ('taxonomy_contract-' + stamp)
    output.mkdir(parents=True, exist_ok=False)
    report = {
        'producer': 'verification/check_data_contract.py',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'taxonomy_version': taxonomy['taxonomy_version'], 'prototype_version': version,
        'taxonomy_sha256': hashlib.sha256(taxonomy_file.read_bytes()).hexdigest(),
        'source_csv': config['source_csv'], 'source_sha256_before': raw_before,
        'scope': 'Current data-contract consistency and synthetic behaviour; no new model request or general accuracy claim.',
        'checks': [], 'metric_cases': [],
    }
    counts = io.StringIO()

    def check(name, expected, observed, frame):
        match = expected == observed
        report['checks'].append({'name': name, 'source_frame': frame,
                                 'expected': expected, 'observed': observed,
                                 'status': 'PASS' if match else 'FAIL'})
        if not match:
            raise ValueError(name + ' differs from its declared reference')

    def rejected(name, function, frame):
        try:
            function()
        except ValueError:
            observed = 'ValueError'
        else:
            observed = 'accepted'
        check(name, 'ValueError', observed, frame)

    try:
        from search_tools import ResearchTools, METRICS, POSITIONS
        from snapshot import load_snapshot
        check('all_source_fields_defined_once', sorted(taxonomy['original_column_order']), sorted(taxonomy['fields']), 'ordered source schema versus current field definitions')
        roles = [name for names in taxonomy['field_roles'].values() for name in names]
        check('field_roles_cover_schema_once', sorted(taxonomy['original_column_order']), sorted(roles), 'current field-role partition')
        check('application_version', version, taxonomy['active_agent']['prototype_version'], 'app/version.json')
        for key in ('season', 'first_gameweek', 'last_gameweek', 'source_csv'):
            check('active_' + key, config[key], taxonomy['active_agent'][key], 'app/config.json')
        check('supported_positions', list(POSITIONS), taxonomy['controlled_vocabularies']['research_positions'], 'executed tool vocabulary')
        check('active_position_subset', list(POSITIONS), taxonomy['active_agent']['supported_positions'], 'executed tool vocabulary')
        check('ranking_metrics', list(METRICS), taxonomy['controlled_vocabularies']['ranking_metrics'], 'executed tool vocabulary')
        check('active_ranking_metrics', list(METRICS), taxonomy['active_agent']['ranking_metrics'], 'executed tool vocabulary')
        check('raw_position_vocabulary', taxonomy['fields']['position']['allowed_values'], taxonomy['controlled_vocabularies']['raw_positions'], 'current source-field definition')
        for name in taxonomy['controlled_vocabularies']['tools']:
            actual = [key for key in inspect.signature(getattr(ResearchTools, name)).parameters if key != 'self']
            check('parameters_' + name, taxonomy['query_contract']['tool_parameters'][name], actual, 'Python method signature versus declared tool parameters')
        controller = ast.parse((ROOT / 'app/run_search_agent.py').read_text(encoding='utf-8'))
        allowed = next(node.value for node in ast.walk(controller) if isinstance(node, ast.Assign)
                       and any(isinstance(target, ast.Name) and target.id == 'allowed' for target in node.targets))
        controller_tools = list(ast.literal_eval(allowed.generators[0].iter))
        check('controller_tool_allowlist', taxonomy['controlled_vocabularies']['tools'], controller_tools,
              'literal allowlist in the executed controller versus declared tool vocabulary')
        parameters = inspect.signature(ResearchTools.find_players).parameters
        for declared, implemented in (('default_ranking_metric', 'metric'),
                                      ('price_cap_inclusive_default', 'price_inclusive'),
                                      ('default_shortlist_limit', 'limit')):
            check(declared, taxonomy['query_contract'][declared], parameters[implemented].default,
                  'current method defaults versus declared query defaults')
        check('configured_default_window', config['default_window_gameweeks'], taxonomy['query_contract']['default_window_gameweeks'], 'app/config.json')
        check('configured_minutes_floor', config['minimum_minutes'], taxonomy['query_contract']['minimum_minutes_default'], 'app/config.json')
        with contextlib.redirect_stdout(counts):
            actual_data, clean_history = load_snapshot()
        check('runtime_loader_accepts_configured_source', config['source_sha256'], raw_before, 'fingerprinted raw CSV, executed loader schema/type/key/coverage validation')
        invalid_time = []
        for index, row in enumerate(clean_history):
            try:
                value = datetime.fromisoformat(row['kickoff_time'].replace('Z', '+00:00'))
                valid = value.tzinfo is not None and value.utcoffset() == timedelta(0)
            except (TypeError, ValueError):
                valid = False
            if not valid:
                invalid_time.append({'cleaned_row': index, 'element': row['element'], 'fixture': row['fixture']})
        check('UTC_kickoff_timestamps', [], invalid_time, 'cleaned fixture rows returned by the fingerprinted raw loader; exact-copy removal already reported')
        report['cleaned_fixture_rows_checked'] = len(clean_history)

        # Synthetic records are independent of the real CSV and have named,
        # visible inputs. They exercise the documented arithmetic and timing.
        def row(player, gw, fixture, minutes, points, xg, xa, value, position='MID'):
            return {'element': str(player), 'GW': str(gw), 'fixture': str(fixture),
                    'minutes': str(minutes), 'total_points': str(points),
                    'expected_goals': str(xg), 'expected_assists': str(xa),
                    'value': str(value), 'name': {1: 'Alpha', 2: 'Beta', 3: 'Gamma', 4: 'Keeper'}[player],
                    'position': position, 'team': 'Club', 'kickoff_time': f'2025-08-{gw:02d}T12:00:00Z'}
        history = [row(1, 1, 101, 90, 2, .2, .1, 50),
                   row(1, 2, 102, 90, 4, .3, .2, 55),
                   row(1, 2, 103, 90, 6, .5, .3, 55),
                   row(1, 6, 104, 90, 100, 9, 9, 120),
                   row(2, 1, 101, 0, 0, 0, 0, 40, 'FWD'),
                   row(3, 6, 104, 90, 10, 1, 1, 60),
                   row(4, 1, 101, 90, 15, 0, 0, 45, 'GK')]
        data = {'scenario': config, 'players': [
            {'id': '1', 'name': 'Alpha', 'team': 'Club', 'position': 'MID', 'price': 12},
            {'id': '2', 'name': 'Beta', 'team': 'Club', 'position': 'FWD', 'price': 4},
            {'id': '3', 'name': 'Gamma', 'team': 'Club', 'position': 'MID', 'price': 6},
            {'id': '4', 'name': 'Keeper', 'team': 'Club', 'position': 'GK', 'price': 4.5},
        ]}
        report['synthetic_source_frame'] = history
        definitions = taxonomy['derived_fields']

        def reference(player, records, start, end):
            prior = [r for r in records if r['element'] == player and int(r['GW']) <= end]
            counts.write(f'[synthetic price filter] {len(records)} -> {len(prior)} rows for player {player} at/before GW{end}\n')
            latest = max(prior, key=lambda r: (int(r['GW']), r['kickoff_time'], int(r['fixture']))) if prior else None
            interval = [r for r in records if r['element'] == player and start <= int(r['GW']) <= end]
            counts.write(f'[synthetic interval filter] {len(records)} -> {len(interval)} rows for player {player} in GW{start}–{end}\n')
            values = {}
            for definition in definitions:
                kind = definition['aggregation']
                if kind == 'sum':
                    source_name = definition['source_fields'][0]
                    try:
                        numbers = [float(r[source_name]) for r in interval]
                    except (ValueError, TypeError, KeyError):
                        numbers = [float('nan')]
                    value = sum(numbers) if latest and all(math.isfinite(n) for n in numbers) else None
                elif kind == 'latest_price':
                    value = float(latest[definition['source_fields'][0]]) * definition['scale'] if latest else None
                elif kind == 'latest_price_gameweek':
                    value = int(latest['GW']) if latest else None
                elif kind == 'ratio':
                    numerator = [values[name] for name in definition['numerator_metrics']]
                    denominator = values[definition['denominator_metric']]
                    value = (definition['scale'] * sum(numerator) / denominator
                             if denominator is not None and denominator > 0 and all(n is not None for n in numerator) else None)
                else:
                    raise ValueError('Unknown declared aggregation: ' + kind)
                values[definition['name']] = value
            return values

        missing = [dict(r) for r in history]
        missing[1]['expected_goals'] = ''
        cases = [
            ('double_gameweek_and_early_price', '1', history, 1, 2),
            ('zero_minutes', '2', history, 1, 2),
            ('no_record_at_interval_end', '3', history, 1, 2),
            ('missing_measurement', '1', missing, 1, 2),
            ('known_player_without_interval_rows', '1', history, 3, 4),
        ]
        for name, player, records, start, end in cases:
            expected = reference(player, records, start, end)
            with contextlib.redirect_stdout(counts):
                actual = ResearchTools(data, records).compare_players([player], start_gameweek=start, end_gameweek=end)['players'][0]
            for key, value in expected.items():
                observed = actual[key]
                equal = observed is None if value is None else observed is not None and math.isclose(value, observed, rel_tol=1e-10, abs_tol=1e-10)
                check(name + '_' + key, True, equal, 'named synthetic fixture frame evaluated with current dictionary aggregation definitions')
            report['metric_cases'].append({'case': name, 'player_id': player, 'period': [start, end],
                                           'expected': expected, 'observed': {key: actual[key] for key in expected},
                                           'warnings': actual['warnings']})
        with contextlib.redirect_stdout(counts):
            tools = ResearchTools(data, history)
            defaults = tools.find_players('MID', 6)
            check('executed_minutes_default', taxonomy['query_contract']['minimum_minutes_default'],
                  defaults['constraints']['minimum_minutes'], 'synthetic tool execution with omitted minutes argument')
            lower, upper = taxonomy['query_contract']['shortlist_limit_bounds']
            for boundary in (lower, upper):
                check('accepted_limit_' + str(boundary), boundary, tools._limit(boundary),
                      'declared inclusive shortlist limit boundaries')
            rejected('limit_below_declared_range', lambda: tools._limit(lower - 1), 'declared shortlist limit boundaries')
            rejected('limit_above_declared_range', lambda: tools._limit(upper + 1), 'declared shortlist limit boundaries')
            check('default_period', [config['last_gameweek'] - config['default_window_gameweeks'] + 1, config['last_gameweek']], list(tools.resolve_period()), 'configured defaults versus executed resolver')
            rejected('mixed_period_forms', lambda: tools.resolve_period(2, 1, 2), 'documented mutually exclusive interval forms')
            rejected('out_of_bounds_period', lambda: tools.resolve_period(start_gameweek=0, end_gameweek=2), 'configured inclusive season bounds')
            rejected('missing_interval_end', lambda: tools.resolve_period(start_gameweek=1), 'complete explicit interval requirement')
            rejected('unsupported_research_position', lambda: tools.find_players('GK', 6), 'raw GK label is valid but research support is MID/FWD only')
            rejected('unsupported_comparison_position', lambda: tools.compare_players(['4'], start_gameweek=1, end_gameweek=2), 'raw GK label is valid but research support is MID/FWD only')
            rejected('unknown_metric', lambda: tools.find_players('MID', 6, metric='forecast_points'), 'declared ranking-metric vocabulary')
        report['status'] = 'PASS'
    except Exception as exc:
        report.update(status='FAIL', error=f'{type(exc).__name__}: {exc}')
    finally:
        raw_after = hashlib.sha256(source.read_bytes()).hexdigest()
        report['source_sha256_after'] = raw_after
        report['raw_unchanged'] = raw_after == raw_before
        if not report['raw_unchanged']:
            report['status'] = 'FAIL'
        (output / 'row_counts.txt').write_text(counts.getvalue(), encoding='utf-8')
        (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        print(counts.getvalue(), end='', flush=True)
        print('Taxonomy contract: ' + report['status'], flush=True)
        print('Report: ' + str((output / 'report.json').relative_to(ROOT)), flush=True)
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
