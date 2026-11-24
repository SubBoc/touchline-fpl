"""Run portfolio checks and save fresh evidence; no hosted model requests."""
from datetime import datetime, timezone
import hashlib
import http.client
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    target = ROOT / 'results/local'
    target.mkdir(parents=True, exist_ok=True)
    source = ROOT / json.loads((ROOT / 'app/config.json').read_text())['source_csv']
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    report = {'producer': 'verification/verify.py', 'created_utc': datetime.now(timezone.utc).isoformat(),
              'python': sys.version.split()[0], 'source_sha256_before': before,
              'scope': 'Synthetic unit tests, separate raw-data recomputation, contract and HTTP checks; no new live-model evaluation.', 'checks': []}

    def check(name, expected, observed, frame):
        passed = expected == observed
        report['checks'].append({'name': name, 'source_frame': frame, 'expected': expected,
                                 'observed': observed, 'status': 'PASS' if passed else 'FAIL'})
        print(name + ': ' + ('PASS' if passed else 'FAIL'), flush=True)
        if not passed:
            raise AssertionError(name)

    def run(name, command):
        proc = subprocess.run(command, cwd=ROOT, capture_output=True, encoding='utf-8', errors='replace')
        (target / (name + '.txt')).write_text('Command: ' + ' '.join(command) + '\n\nPROGRAM OUTPUT\n' + proc.stdout + proc.stderr, encoding='utf-8')
        check(name, 0, proc.returncode, 'executed command; see results/local/' + name + '.txt')
        report['checks'][-1]['command'] = ['python' if command[0] == sys.executable else 'node', *command[1:]]
        report['checks'][-1]['program_output'] = proc.stdout + proc.stderr

    server = None
    try:
        run('unit_tests', [sys.executable, '-X', 'utf8', '-m', 'unittest', 'discover', '-s', 'app', '-p', 'test_*.py'])
        run('live_data_and_assets', [sys.executable, '-X', 'utf8', 'app/serve.py', '--check'])
        run('recorded_demo_and_assets', [sys.executable, '-X', 'utf8', 'app/serve.py', '--demo', '--check'])
        run('data_contract', [sys.executable, '-X', 'utf8', 'verification/check_data_contract.py'])
        run('raw_recomputation', [sys.executable, '-X', 'utf8', 'verification/check_intervals.py'])
        node = shutil.which('node')
        if not node:
            raise RuntimeError('Node.js is required for the complete verification, including JavaScript syntax.')
        run('javascript_syntax', [node, '--check', 'app/web/app.js'])
        example = json.loads((ROOT / 'results/example.json').read_text(encoding='utf-8'))
        recomputed = json.loads((target / 'raw_recomputation.json').read_text(encoding='utf-8'))
        expected = next(case['players'] for case in recomputed['cases'] if case['kind'] == 'named-player comparison' and case['start_gameweek'] == 1 and case['end_gameweek'] == 5)
        observed = next(step['observation']['players'] for step in example['steps'] if step['action']['tool'] == 'compare_players')
        fields = ('id', 'name', 'points', 'minutes', 'price_millions', 'price_gameweek', 'xg', 'xa')
        compact = lambda rows: [{key: row[key] for key in fields} for row in rows]
        check('recorded_example_statistics', compact(expected), compact(observed), 'separate raw-CSV pandas recomputation versus saved tool observations')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        server = subprocess.Popen([sys.executable, '-X', 'utf8', 'app/serve.py', '--demo', '--port', str(port)], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                connection = http.client.HTTPConnection('127.0.0.1', port, timeout=2)
                connection.request('GET', '/api/snapshot')
                response = connection.getresponse()
                snapshot = json.loads(response.read())
                connection.close()
                break
            except OSError:
                time.sleep(.1)
        else:
            raise RuntimeError('Demo server failed to start')
        check('demo_snapshot_label', True, snapshot.get('recorded_demo'), 'HTTP GET /api/snapshot on actual demo server')
        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        connection.request('POST', '/api/search', json.dumps({'question': example['prompt']}), {'Content-Type': 'application/json', 'Origin': f'http://127.0.0.1:{port}'})
        response = connection.getresponse()
        result = json.loads(response.read())
        connection.close()
        check('demo_http_answer', (200, example['answer'], True), (response.status, result.get('answer'), result.get('evidence', {}).get('recorded_demo')), 'actual demo HTTP response versus results/example.json')
        check('raw_source_unchanged', before, hashlib.sha256(source.read_bytes()).hexdigest(), 'raw CSV fingerprint before versus after checks')
        report['status'] = 'PASS'
    except Exception as exc:
        report.update(status='FAIL', error=f'{type(exc).__name__}: {exc}')
    finally:
        if server is not None:
            server.terminate()
            server.wait(timeout=10)
        output = target / 'verification.json'
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('Verification: ' + report.get('status', 'FAIL') + '; report: results/local/verification.json')
    return 0 if report.get('status') == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
