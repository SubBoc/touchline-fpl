import copy
import json
from pathlib import Path
import unittest
import test_search_tools as tool_cases
import test_search_agent as controller_cases
from test_search_agent import response
from periods import requested_interval
from search_tools import ResearchTools


class IntervalToolTests(unittest.TestCase):
    setUp=tool_cases.ResearchTests.setUp
    tearDown=tool_cases.ResearchTests.tearDown
    def test_configuration_defaults_are_used(self):
        self.tools.config.update(default_window_gameweeks=2,minimum_minutes=270)
        self.assertEqual(self.tools.resolve_period(),(6,7))
        self.assertEqual(self.tools.find_players('MID',6)['players'],[])
    def test_first_interval_uses_only_first_rows_and_old_price(self):
        first=self.tools.compare_players(['1'],start_gameweek=1,end_gameweek=2)['players'][0]
        self.assertEqual((first['points'],first['minutes'],first['price_millions']),(100,90,5))
        altered=copy.deepcopy(self.history)
        for row in altered:
            if int(row['GW'])>2:
                row['value']='100'
                row['total_points']='9999'
        result=ResearchTools(self.data,altered).compare_players(['1'],start_gameweek=1,end_gameweek=2)['players'][0]
        self.assertEqual(result,first)

    def test_inclusive_range_double_gameweek(self):
        result=self.tools.compare_players(['1'],start_gameweek=6,end_gameweek=6)['players'][0]
        self.assertEqual((result['minutes'],result['points']),(180,10))
        self.assertEqual((result['window_start_gw'],result['window_end_gw']),(6,6))

    def test_invalid_or_conflicting_intervals_are_rejected(self):
        for arguments in ({'start_gameweek':1},{'start_gameweek':5,'end_gameweek':2},
                          {'start_gameweek':0,'end_gameweek':5},
                          {'start_gameweek':1,'end_gameweek':8},
                          {'start_gameweek':True,'end_gameweek':5},
                          {'window_gameweeks':5,'start_gameweek':1,'end_gameweek':5}):
            with self.subTest(arguments=arguments),self.assertRaises(ValueError):
                self.tools.compare_players(['1'],**arguments)

    def test_no_future_price_for_a_player_not_yet_in_the_data(self):
        result=self.tools.compare_players(['4'],start_gameweek=1,end_gameweek=2)['players'][0]
        self.assertIsNone(result['price_millions'])
        self.assertIsNone(result['points'])
        self.assertIsNone(result['team'])
        self.assertTrue(result['warnings'])


class PeriodPhraseTests(unittest.TestCase):
    def test_first_last_explicit_and_full_season_are_distinct(self):
        for prompt,expected in (
            ('Compare over the first five completed gameweeks',(1,5)),
            ("Xhaka performance over the first 10 GWs",(1,10)),
            ('Over the last five completed gameweeks',(34,38)),
            ('Compare GW 15–19',(15,19)),
            ('Rank over the entire 2025/26 season up to and including GW 38',(1,38)),
            ('Rank midfielders over the 25/26 season',(1,38)),
            ('Recent form please',None),('Recent form this season',None)):
            with self.subTest(prompt=prompt):
                self.assertEqual(requested_interval(prompt,1,38),expected)


class PeriodControllerTests(unittest.TestCase):
    run_case=controller_cases.ControllerTests.run_case
    def test_wrong_trailing_window_is_rejected_before_tool_execution(self):
        import run_search_agent as agent
        wrong={'position':'MID','max_price_millions':6,'window_gameweeks':5}
        correct={'position':'MID','max_price_millions':6,'start_gameweek':1,'end_gameweek':5}
        tools,factory,executable,runtime=self.run_case([
            response({'tool':'find_players','arguments':wrong}),
            response({'tool':'find_players','arguments':correct}),
            response({'answer':'Results for the requested interval'})])
        tools.resolve_period.side_effect=[(34,38),(1,5)]
        with factory,executable,runtime:
            result=agent.run_search('Find midfielders at most 6m over the first five completed gameweeks',self.directory.name)
        tools.find_players.assert_called_once_with(**correct)
        trace=json.loads((Path(self.directory.name)/result['trace']).read_text())
        self.assertIn('Requested interval',trace['steps'][0]['validation_error'])
        self.assertEqual(trace['periods_used'],[[1,5]])
        self.assertEqual(trace['prototype_version'],'v4')


if __name__=='__main__':
    unittest.main()
