"""A fixed, explicitly labelled replay. Does not load the CSV or invoke a model."""
import copy
import json
from snapshot import ROOT, VERSION


def load_demo():
    example = json.loads((ROOT / 'results/example.json').read_text(encoding='utf-8'))
    snapshot = dict(example['snapshot'], prototype_version=VERSION,
                    recorded_demo=True, example_question=example['prompt'])

    def replay(question):
        if question.strip() != example['prompt'].strip():
            raise ValueError('Recorded demo: use the example question. Start live mode for new research.')
        return {'answer': example['answer'], 'trace': 'recorded-example',
                'snapshot': copy.deepcopy(snapshot), 'periods': copy.deepcopy(example['periods']),
                'evidence': {'recorded_demo': True, 'source_csv_sha256': example['source_csv_sha256'],
                             'periods': copy.deepcopy(example['periods']),
                             'steps': copy.deepcopy(example['steps'])}}

    return snapshot, replay
