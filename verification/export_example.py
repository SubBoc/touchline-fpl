"""Extract a public replay from a local trace; no model call or data transformation."""
import argparse
import hashlib
import json
from pathlib import Path


def export(trace_path, config_path):
    trace = json.loads(trace_path.read_text(encoding='utf-8'))
    config = json.loads(config_path.read_text(encoding='utf-8'))
    steps = []
    for step in trace['steps']:
        if 'action' not in step:
            continue
        models = []
        for line in step.get('stdout', '').splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get('type') == 'session.auto_mode_resolved':
                models.append(event['data']['chosenModel'])
        observation = step.get('observation')
        if isinstance(observation, dict) and isinstance(observation.get('snapshot'), dict):
            observation['snapshot'].pop('prototype_version', None)
        steps.append({'models': models, 'action': step['action'], 'observation': observation})
    snapshot = dict(trace['snapshot'])
    snapshot.pop('prototype_version', None)
    return {'producer': 'verification/export_example.py',
            'kind': 'recorded model response; replay, not a new model request',
            'recorded_on': trace_path.name[:4] + '-' + trace_path.name[4:6] + '-' + trace_path.name[6:8],
            'source_trace_sha256': hashlib.sha256(trace_path.read_bytes()).hexdigest(),
            'source_csv_sha256': config['source_sha256'],
            'prompt': trace['prompt'], 'answer': trace['answer'],
            'snapshot': snapshot, 'periods': trace['periods_used'], 'steps': steps}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    parser.add_argument('--output', type=Path, default=Path('results/local/example.json'))
    args = parser.parse_args()
    result = export(args.trace, Path(__file__).resolve().parents[1] / 'app/config.json')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Saved ' + str(args.output))
