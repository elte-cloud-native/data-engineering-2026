"""Optional helper: copy the local Kafka landing file to Azure Bronze."""

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "landing"
FILE = LANDING / "sensors/2025/09/02/source=kafka/sensor_events.json"


def main():
    if not FILE.is_file():
        raise SystemExit("Landing file not found. Run consumer_to_landing.py first.")
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        raise SystemExit("Set AZURE_STORAGE_CONNECTION_STRING as in Lab 03.")

    from azure.storage.blob import BlobServiceClient

    container_name = os.getenv("AZURE_STORAGE_CONTAINER", "bronze")
    blob_name = FILE.relative_to(LANDING).as_posix()
    container = BlobServiceClient.from_connection_string(connection_string).get_container_client(container_name)
    blob = container.get_blob_client(blob_name)
    if blob.exists():
        print(f"SKIP existing Blob path: {blob_name}")
        return
    with FILE.open("rb") as stream:
        blob.upload_blob(stream, overwrite=False)
    print(f"UPLOADED {container_name}/{blob_name}")


if __name__ == "__main__":
    main()
