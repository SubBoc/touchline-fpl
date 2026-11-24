"""Replay contracts: no dataset/model access and no answer for a different question."""
import unittest
from unittest.mock import patch
from recorded_demo import load_demo


class RecordedDemoTests(unittest.TestCase):
    def test_replay_does_not_load_data_or_call_model(self):
        with patch('snapshot.load_snapshot', side_effect=AssertionError('CSV accessed')), patch('subprocess.run', side_effect=AssertionError('Model called')):
            snapshot, replay = load_demo()
            result = replay(snapshot['example_question'])
        self.assertTrue(snapshot['recorded_demo'])
        self.assertTrue(result['evidence']['recorded_demo'])
        self.assertEqual(result['periods'], [[1, 5]])
        self.assertTrue(result['evidence']['steps'])

    def test_other_question_cannot_receive_the_saved_answer(self):
        _, replay = load_demo()
        with self.assertRaisesRegex(ValueError, 'Recorded demo'):
            replay('Predict next week')

    def test_replay_returns_fresh_observations(self):
        snapshot, replay = load_demo()
        first = replay(snapshot['example_question'])
        first['evidence']['steps'].clear()
        self.assertTrue(replay(snapshot['example_question'])['evidence']['steps'])


if __name__ == '__main__':
    unittest.main()
