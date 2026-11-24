"""Known-answer tests for research tools; no model calls or network needed."""

import contextlib
import copy
import io
import unittest

from search_tools import ResearchTools


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.data = {"scenario": {"season": "test_season", "first_gameweek": 1, "last_gameweek": 7}, "players": [
            {"id": "1", "name": "Alpha", "position": "MID", "team": "A", "price": 5.0},
            {"id": "2", "name": "Beta", "position": "MID", "team": "B", "price": 5.1},
            {"id": "3", "name": "Gamma", "position": "FWD", "team": "C", "price": 4.0},
            {"id": "4", "name": "Delta", "position": "MID", "team": "D", "price": 4.0}]}
        def row(element, gw, fixture, minutes, points, xg):
            return {"element": str(element), "GW": str(gw), "fixture": str(fixture), "minutes": str(minutes),
                    "total_points": str(points), "expected_goals": str(xg), "expected_assists": "0.1",
                    "name": self.data["players"][element-1]["name"],
                    "position": self.data["players"][element-1]["position"],
                    "team": self.data["players"][element-1]["team"],
                    "value": str(round(self.data["players"][element-1]["price"]*10)),
                    "kickoff_time": f"2025-01-{gw:02d}T15:00:00Z"}
        self.history = [row(1,2,10,90,100,10), row(1,6,11,90,4,.4), row(1,6,12,90,6,.6),
                        row(2,6,11,90,10,.6), row(2,7,13,90,10,.6),
                        row(3,6,12,90,3,.1), row(3,7,13,90,3,.1), row(4,7,13,0,0,0)]
        self.tools = ResearchTools(self.data, self.history)
        self.silence = contextlib.redirect_stdout(io.StringIO())
        self.silence.__enter__()

    def tearDown(self):
        self.silence.__exit__(None, None, None)

    def test_budget_position_and_exact_double_gameweek_totals(self):
        result = self.tools.find_players("MID", 5.0)
        self.assertEqual([p["id"] for p in result["players"]], ["1"])
        player = result["players"][0]
        self.assertEqual((player["minutes"], player["points"], player["xg"]), (180,10,1))
        self.assertAlmostEqual(player["xg_per90"], .5)
        self.assertEqual(player["points_per_million"], 2)
        self.assertEqual(self.tools.find_players("MID",5.0,price_inclusive=False)["players"], [])

    def test_empty_pool_does_not_relax_constraints(self):
        result = self.tools.find_players("MID", 3)
        self.assertEqual(result["players"], [])
        self.assertEqual(result["constraints"]["max_price_millions"], 3)

    def test_zero_minutes_and_missing_numeric_evidence(self):
        comparison = self.tools.compare_players(["4"])["players"][0]
        self.assertIsNone(comparison["xg_per90"])
        history = copy.deepcopy(self.history)
        history[1]["expected_goals"] = ""
        tools = ResearchTools(self.data, history)
        result = tools.find_players("MID",5,metric="xg_per90")
        self.assertEqual(result["players"], [])
        self.assertIsNone(tools.compare_players(["1"])["players"][0]["xg"])

    def test_future_and_duplicate_fixture_records_are_rejected(self):
        future = copy.deepcopy(self.history)
        future[0]["GW"] = "8"
        with self.assertRaises(ValueError): ResearchTools(self.data, future)
        with self.assertRaises(ValueError): ResearchTools(self.data, self.history + [self.history[0]])

    def test_invalid_scope_and_arguments(self):
        for kwargs in ({"position":"GK", "max_price_millions":5},
                       {"position":"MID", "max_price_millions":float('nan')},
                       {"position":"MID", "max_price_millions":5,"window_gameweeks":8},
                       {"position":"MID", "max_price_millions":5,"limit":100}):
            with self.assertRaises(ValueError): self.tools.find_players(**kwargs)
        with self.assertRaises(ValueError): self.tools.compare_players(["999"])

    def test_lookup_and_comparison_are_grounded_in_snapshot(self):
        self.assertEqual(self.tools.lookup_players("alpha")["matches"][0]["id"], "1")
        self.assertEqual(self.tools.lookup_players("unknown")["matches"], [])
        result = self.tools.compare_players(["1","2"])
        self.assertEqual([p["points"] for p in result["players"]], [10,20])
        self.assertFalse(result["snapshot"]["is_live"])
        self.assertFalse(result["snapshot"]["forecast_available"])


if __name__ == "__main__":
    unittest.main()
