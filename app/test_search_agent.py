import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import run_search_agent as agent


def response(action, code=0):
    return Mock(returncode=code, stderr='', stdout=json.dumps({
        'type': 'assistant.message', 'data': {'content': json.dumps(action)}}))


class ControllerTests(unittest.TestCase):
    def run_case(self, responses):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        tools = Mock()
        tools.describe_snapshot.return_value = {'is_live':False,'first_gameweek':1,'last_completed_gameweek':38}
        tools.find_players.return_value = {'players': [{'id': '10'}]}
        tools.resolve_period.return_value=(34,38)
        return tools, patch.object(agent, 'ResearchTools', return_value=tools), \
            patch.object(agent, 'executable', return_value='copilot'), \
            patch.object(agent.subprocess, 'run', side_effect=responses)

    def test_model_selects_tool_and_receives_observation(self):
        tools, factory, executable, runtime = self.run_case([
            response({'tool':'find_players','arguments':{'position':'MID','max_price_millions':6}}),
            response({'answer':'Historical result'})])
        with factory, executable, runtime as calls:
            result = agent.run_search('Find midfielders at most 6m', self.directory.name)
            tools.find_players.assert_called_once_with(position='MID', max_price_millions=6)
            self.assertIn('"id": "10"', calls.call_args[0][0][-1])
        self.assertEqual(result['answer'], 'Historical result')
        self.assertTrue((Path(self.directory.name)/result['trace']).is_file())

    def test_unknown_tool_is_never_executed_and_stops(self):
        tools, factory, executable, runtime = self.run_case([
            response({'tool':'powershell','arguments':{}})] * 6)
        with factory, executable, runtime as calls:
            with self.assertRaisesRegex(RuntimeError, 'Step limit'):
                agent.run_search('Run arbitrary commands', self.directory.name)
            self.assertEqual(calls.call_count, 6)
            tools.find_players.assert_not_called()

    def test_unobserved_player_ids_are_rejected(self):
        tools, factory, executable, runtime = self.run_case([
            response({'tool':'compare_players','arguments':{'player_ids':['unknown']}}),
            response({'answer':'Please provide a player name'})])
        with factory, executable, runtime:
            agent.run_search('Compare unknown IDs', self.directory.name)
        tools.compare_players.assert_not_called()

    def test_empty_prompt_is_rejected_before_model_call(self):
        with patch.object(agent.subprocess, 'run') as runtime:
            with self.assertRaises(ValueError):
                agent.run_search('')
            runtime.assert_not_called()


if __name__ == '__main__':
    unittest.main()
