"""Prepared helper: save retained Kafka records to a local landing file."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "landing/sensors/2025/09/02/source=kafka/sensor_events.json"


def as_landing_record(message):
    """Keep the event value and the Kafka coordinates needed to identify it."""
    return {
        "topic": message.topic,
        "partition": message.partition,
        "offset": message.offset,
        "key": message.key.decode("utf-8") if message.key is not None else None,
        "value": json.loads(message.value.decode("utf-8")),
    }


def main():
    if TARGET.exists():
        print(f"SKIP existing landing file: {TARGET}")
        return

    from kafka import KafkaConsumer

    consumer = KafkaConsumer(
        "sensor-data",
        bootstrap_servers="localhost:9092",
        auto_offset_reset="earliest",
        group_id=None,
        enable_auto_commit=False,
        consumer_timeout_ms=5000,
    )
    try:
        records = [as_landing_record(message) for message in consumer]
    finally:
        consumer.close()

    if not records:
        raise SystemExit("No Kafka records found. Complete Parts 1–4 first.")

    # Stable file order for inspection; Kafka itself promises order per partition.
    records.sort(key=lambda record: (record["partition"], record["offset"]))
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with TARGET.open("x", encoding="utf-8") as stream:
        json.dump(records, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    print(f"Saved {len(records)} Kafka records to {TARGET}")


if __name__ == "__main__":
    main()
