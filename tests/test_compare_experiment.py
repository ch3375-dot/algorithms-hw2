import csv
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from experiments.compare_experiment import (
    CAPACITY,
    TARGET_LOAD_FACTORS,
    render_markdown_tables,
    run_experiment,
    write_outputs,
)


class CompareExperimentTests(unittest.TestCase):
    def test_comparison_is_reproducible_and_contains_theory_and_measurements(self):
        rows = run_experiment(failure_query_count=30)

        self.assertEqual(rows, run_experiment(failure_query_count=30))
        self.assertEqual(CAPACITY, 97)
        self.assertEqual(
            [row.target_alpha for row in rows],
            list(TARGET_LOAD_FACTORS),
        )
        self.assertEqual(len(rows), 9)
        for row in rows:
            self.assertEqual(
                row.key_count,
                int(row.target_alpha * CAPACITY + 0.5),
            )
            self.assertEqual(row.bucket_count, CAPACITY)
            self.assertGreaterEqual(row.chaining_successful_actual, 1)
            self.assertGreaterEqual(row.linear_successful_actual, 1)

        tables = render_markdown_tables(rows)
        self.assertIn("체이닝", tables)
        self.assertIn("선형 탐지", tables)
        self.assertIn("1 + α/2", tables)
        self.assertIn("(1 + 1/(1-α)²)/2", tables)

    def test_writes_csv_and_two_valid_svg_graphs(self):
        rows = run_experiment(failure_query_count=30)
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "compare_results.csv"
            success_svg_path = Path(directory) / "compare_success.svg"
            failure_svg_path = Path(directory) / "compare_failure.svg"

            write_outputs(rows, csv_path, success_svg_path, failure_svg_path)

            with csv_path.open(encoding="utf-8", newline="") as result_file:
                csv_rows = list(csv.DictReader(result_file))
            self.assertEqual(len(csv_rows), 9)
            self.assertIn("linear_unsuccessful_theory", csv_rows[0])

            success_svg = ET.parse(success_svg_path).getroot()
            failure_svg = ET.parse(failure_svg_path).getroot()
            self.assertTrue(success_svg.tag.endswith("svg"))
            self.assertTrue(failure_svg.tag.endswith("svg"))
            self.assertIn(
                "성공 탐색",
                "".join(success_svg.itertext()),
            )
            self.assertIn(
                "실패 탐색",
                "".join(failure_svg.itertext()),
            )


if __name__ == "__main__":
    unittest.main()
