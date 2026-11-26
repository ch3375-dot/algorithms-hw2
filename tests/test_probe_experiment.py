import csv
import tempfile
import unittest
from pathlib import Path

from experiments.probe_experiment import (
    CAPACITY,
    TARGET_LOAD_FACTORS,
    CountingChainedHashTable,
    generate_keys,
    load_factor_key_count,
    measure_search_costs,
    render_markdown_table,
    run_experiment,
    write_results,
)


class ProbeExperimentTests(unittest.TestCase):
    def test_key_counts_are_nearest_integers_for_requested_load_factors(self):
        self.assertEqual(CAPACITY, 97)
        self.assertEqual(
            [load_factor_key_count(alpha) for alpha in TARGET_LOAD_FACTORS],
            [24, 49, 97, 194, 388],
        )

    def test_search_cost_counts_nodes_visited_in_each_chain(self):
        table = CountingChainedHashTable(capacity=1)
        keys = ("first", "second", "third")
        for key in keys:
            table.put(key, key)

        successful, unsuccessful = measure_search_costs(
            table,
            keys,
            ("missing-one", "missing-two"),
        )

        self.assertEqual(successful, 2)
        self.assertEqual(unsuccessful, 3)

    def test_experiment_is_reproducible_and_writes_comparison_artifacts(self):
        rows = run_experiment(failure_query_count=20)
        self.assertEqual(rows, run_experiment(failure_query_count=20))
        self.assertEqual([row.target_alpha for row in rows], list(TARGET_LOAD_FACTORS))

        markdown = render_markdown_table(rows)
        self.assertIn("1 + α/2", markdown)
        self.assertIn("실측 α", markdown)

        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "results.csv"
            svg_path = Path(directory) / "results.svg"
            write_results(rows, csv_path, svg_path)

            with csv_path.open(encoding="utf-8", newline="") as result_file:
                csv_rows = list(csv.DictReader(result_file))
            self.assertEqual(len(csv_rows), len(TARGET_LOAD_FACTORS))
            self.assertEqual(csv_rows[0]["key_count"], "24")

            svg = svg_path.read_text(encoding="utf-8")
            self.assertIn("<svg", svg)
            self.assertIn("성공 실측", svg)
            self.assertIn("실패 이론", svg)


if __name__ == "__main__":
    unittest.main()
