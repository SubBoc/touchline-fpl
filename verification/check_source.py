"""Compare the included CSV with the pinned upstream source. Does not modify data."""
from pathlib import Path
import hashlib
import json
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    record = json.loads((ROOT / 'results/data_provenance.json').read_text(encoding='utf-8'))
    local = (ROOT / record['source_csv']).read_bytes()
    request = urllib.request.Request(record['download_url'], headers={'User-Agent': 'Touchline-source-verification'})
    with urllib.request.urlopen(request, timeout=30) as response:
        upstream = response.read()
    result = dict(record, local_sha256=hashlib.sha256(local).hexdigest(),
                  upstream_sha256=hashlib.sha256(upstream).hexdigest(), byte_identical=local == upstream)
    result['status'] = 'PASS' if result['byte_identical'] and result['local_sha256'] == record['expected_sha256'] else 'FAIL'
    output = ROOT / 'results/local/data_provenance.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print('Pinned source comparison: ' + result['status'])
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
