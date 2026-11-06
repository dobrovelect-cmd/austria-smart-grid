import unittest

from capacity_matching import index_api_stations, station_match_key


class CapacityMatchingTests(unittest.TestCase):
    def test_case_and_footnote_markers_are_ignored(self):
        self.assertEqual(
            station_match_key("Netz Burgenland GmbH", "UW Eisenstadt**"),
            station_match_key("NETZ BURGENLAND GMBH", "uw eisenstadt"),
        )

    def test_accent_variants_are_normalized(self):
        self.assertEqual(
            station_match_key("Netz Burgenland GmbH", "UW Güssing"),
            station_match_key("Netz Burgenland GmbH", "UW GÜSSING"),
        )

    def test_api_uid_is_not_part_of_the_matching_key(self):
        record = {
            "uid": "a-newly-generated-id",
            "networkOperator": "Netz Burgenland GmbH",
            "substationName": "UW Eisenstadt",
            "availableCapacity": 12.5,
        }
        indexed = index_api_stations([record])
        self.assertIs(
            indexed[station_match_key("Netz Burgenland GmbH", "UW Eisenstadt")],
            record,
        )

    def test_ambiguous_operator_name_pair_is_rejected(self):
        first = {
            "uid": "100",
            "networkOperator": "Netz Burgenland GmbH",
            "substationName": "UW Eisenstadt",
        }
        second = {
            "uid": "200",
            "networkOperator": "NETZ BURGENLAND GMBH",
            "substationName": "UW Eisenstadt**",
        }
        with self.assertRaises(ValueError):
            index_api_stations([first, second])


if __name__ == "__main__":
    unittest.main()
