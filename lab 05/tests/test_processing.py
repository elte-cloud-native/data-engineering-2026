"""Offline checks for the prepared batch-processing example."""

import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "starter"))
from process_sensors import SOURCE, check_input, check_outputs, process_file  # noqa: E402


class ProcessingTests(unittest.TestCase):
    def test_expected_clean_and_rejected_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            summary = process_file(SOURCE, output)
            check_outputs(output)
            self.assertEqual(summary["input_rows"], 10)
            self.assertEqual(summary["clean_rows"], 5)
            self.assertEqual(summary["rejected_rows"], 5)
            self.assertEqual(len(summary["reasons"]), 5)
            with (output / "silver/sensors_clean.csv").open(newline="", encoding="utf-8") as stream:
                clean = list(csv.DictReader(stream))
            self.assertEqual(clean[0]["temperature_f"], "70.7")
            with (output / "quarantine/sensors_rejected.csv").open(newline="", encoding="utf-8") as stream:
                rejected = list(csv.DictReader(stream))
            self.assertEqual({row["reason"] for row in rejected}, set(summary["reasons"]))

    def test_rerun_produces_the_same_derived_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            process_file(SOURCE, output)
            before = {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()}
            process_file(SOURCE, output)
            after = {path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()}
            self.assertEqual(before, after)

    def test_bad_header_fails_before_writing_outputs(self):
        bad = SOURCE.with_name("sensors_bad_header.csv")
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            with self.assertRaisesRegex(ValueError, "Expected CSV header"):
                check_input(bad)
            with self.assertRaisesRegex(ValueError, "Expected CSV header"):
                process_file(bad, output)
            self.assertFalse(list(output.rglob("*")))


if __name__ == "__main__":
    unittest.main()
