import unittest

from screening_logic import calculate_heuristic_mix, count_candidate_strategies


class ScreeningLogicTests(unittest.TestCase):
    def row(self, capacity=100.0, wind=5.0, solar=1200.0):
        return {
            "Frei_MVA": capacity,
            "Wind_ms": wind,
            "Solar_kWh": solar,
            "Farbe_Netz": [34, 139, 34, 180],
        }

    def test_no_free_capacity_is_not_a_candidate(self):
        result = calculate_heuristic_mix(
            self.row(capacity=0.0, wind=6.0, solar=1400.0),
            target_wind=4.0,
            target_solar=950.0,
        )
        self.assertEqual(result[1], "Keine freie Netzkapazität")
        self.assertEqual(result[2:5], (0.0, 0.0, 0.0))

    def test_wind_only_candidate_allocation(self):
        result = calculate_heuristic_mix(
            self.row(capacity=100.0, wind=5.0, solar=800.0),
            target_wind=4.0,
            target_solar=950.0,
        )
        self.assertEqual(result[1], "Windpark + BESS (heuristisch)")
        self.assertEqual(result[2:5], (125.0, 0.0, 25.0))

    def test_pv_only_candidate_allocation(self):
        result = calculate_heuristic_mix(
            self.row(capacity=100.0, wind=3.0, solar=1200.0),
            target_wind=4.0,
            target_solar=950.0,
        )
        self.assertEqual(result[1], "PV-Anlage + BESS (heuristisch)")
        self.assertEqual(result[2:5], (0.0, 135.0, 35.0))

    def test_hybrid_candidate_allocation(self):
        result = calculate_heuristic_mix(
            self.row(capacity=100.0, wind=5.0, solar=1200.0),
            target_wind=4.0,
            target_solar=950.0,
        )
        self.assertEqual(result[1], "Hybrides Wind-PV-System + BESS (heuristisch)")
        self.assertGreater(result[2], 0.0)
        self.assertGreater(result[3], 0.0)
        self.assertEqual(result[4], 20.0)

    def test_low_resource_node_is_not_a_candidate(self):
        result = calculate_heuristic_mix(
            self.row(capacity=100.0, wind=3.0, solar=900.0),
            target_wind=4.0,
            target_solar=950.0,
        )
        self.assertEqual(result[1], "Geringes Potenzial")
        self.assertEqual(result[2:5], (0.0, 0.0, 0.0))

    def test_empty_candidate_list_returns_zero_counts(self):
        counts = count_candidate_strategies([])
        self.assertEqual(sum(counts.values()), 0)
        self.assertEqual(len(counts), 3)

    def test_zero_capacity_does_not_increase_candidate_counts(self):
        strategies = [
            calculate_heuristic_mix(self.row(capacity=0.0), 4.0, 950.0)[1],
            calculate_heuristic_mix(self.row(capacity=100.0), 4.0, 950.0)[1],
        ]
        counts = count_candidate_strategies(strategies)
        self.assertEqual(sum(counts.values()), 1)


if __name__ == "__main__":
    unittest.main()
