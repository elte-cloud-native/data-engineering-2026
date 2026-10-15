"""Prepared batch processor: raw sensor CSV -> clean, rejected, and counts."""

import argparse
import csv
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/sensors.csv"
OUTPUT = ROOT / "output"
SOURCE_FIELDS = ["event_id", "sensor_id", "event_timestamp", "temperature_c"]
CLEAN_FIELDS = SOURCE_FIELDS + ["temperature_f"]
REJECTED_FIELDS = SOURCE_FIELDS + ["reason"]


def check_input(source=SOURCE):
    if not source.is_file():
        raise ValueError(f"Input file not found: {source}")
    with source.open(newline="", encoding="utf-8") as stream:
        fields = csv.DictReader(stream).fieldnames
    if fields != SOURCE_FIELDS:
        raise ValueError(f"Expected CSV header {SOURCE_FIELDS}, found {fields}")
    print(f"INPUT OK: {source}")


def classify(row, accepted_ids):
    event_id = (row.get("event_id") or "").strip()
    sensor_id = (row.get("sensor_id") or "").strip()
    timestamp = (row.get("event_timestamp") or "").strip()
    temperature_text = (row.get("temperature_c") or "").strip()

    if not event_id or not sensor_id:
        return None, "missing_identifier"
    if event_id in accepted_ids:
        return None, "duplicate_event_id"
    try:
        event_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if event_time.tzinfo is None:
            raise ValueError("Time zone required")
    except ValueError:
        return None, "invalid_timestamp"
    if not temperature_text:
        return None, "missing_temperature"
    try:
        temperature = float(temperature_text)
    except ValueError:
        return None, "non_numeric_temperature"
    if not math.isfinite(temperature) or not -50 <= temperature <= 100:
        return None, "out_of_range_temperature"

    accepted_ids.add(event_id)
    clean = {
        "event_id": event_id,
        "sensor_id": sensor_id,
        "event_timestamp": event_time.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "temperature_c": f"{temperature:.1f}",
        "temperature_f": f"{temperature * 9 / 5 + 32:.1f}",
    }
    return clean, None


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def process_file(source=SOURCE, output=OUTPUT):
    check_input(source)
    clean, rejected, accepted_ids = [], [], set()
    with source.open(newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            result, reason = classify(row, accepted_ids)
            if reason:
                rejected.append({**{field: row.get(field) or "" for field in SOURCE_FIELDS}, "reason": reason})
            else:
                clean.append(result)

    write_csv(output / "silver/sensors_clean.csv", CLEAN_FIELDS, clean)
    write_csv(output / "quarantine/sensors_rejected.csv", REJECTED_FIELDS, rejected)
    summary = {
        "input_rows": len(clean) + len(rejected),
        "clean_rows": len(clean),
        "rejected_rows": len(rejected),
        "reasons": dict(sorted(Counter(row["reason"] for row in rejected).items())),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"PROCESSED: {summary['clean_rows']} clean, {summary['rejected_rows']} rejected")
    return summary


def check_outputs(output=OUTPUT):
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    with (output / "silver/sensors_clean.csv").open(newline="", encoding="utf-8") as stream:
        clean = list(csv.DictReader(stream))
    with (output / "quarantine/sensors_rejected.csv").open(newline="", encoding="utf-8") as stream:
        rejected = list(csv.DictReader(stream))
    if len(clean) != summary["clean_rows"] or len(rejected) != summary["rejected_rows"]:
        raise ValueError("Output counts do not match summary.json")
    if len(clean) + len(rejected) != summary["input_rows"] or not clean:
        raise ValueError("Some input rows are missing, or no clean rows remain")
    if len({row["event_id"] for row in clean}) != len(clean):
        raise ValueError("Duplicate event IDs found in Silver output")
    print("QUALITY CHECK OK: every input row is accounted for")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", type=Path, default=SOURCE)
    args = parser.parse_args()
    try:
        process_file(args.input)
        check_outputs()
    except (OSError, ValueError) as exc:
        parser.exit(1, f"PROCESSING FAILED: {exc}\n")


if __name__ == "__main__":
    main()
