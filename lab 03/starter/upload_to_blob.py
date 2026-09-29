"""Prepared helper: check landing paths and upload the files to Azure Bronze."""

import argparse
import os
from datetime import date
from pathlib import Path


LANDING = Path(__file__).resolve().parents[1] / "landing"
ALLOWED = {"sales": ("file", ".csv"), "users": ("api", ".json")}


def validate_path(relative_path: Path) -> None:
    """Check the simple path convention used by this exercise."""
    parts = relative_path.parts
    if len(parts) != 6:
        raise ValueError(f"Expected domain/YYYY/MM/DD/source=.../filename: {relative_path}")

    domain, year, month, day, source_part, filename = parts
    if domain not in ALLOWED:
        raise ValueError(f"Unknown domain in {relative_path}")
    try:
        if len(year) != 4 or len(month) != 2 or len(day) != 2:
            raise ValueError
        date(int(year), int(month), int(day))
    except ValueError as exc:
        raise ValueError(f"Invalid YYYY/MM/DD date in {relative_path}") from exc

    expected_source, expected_suffix = ALLOWED[domain]
    if source_part != f"source={expected_source}":
        raise ValueError(f"Expected source={expected_source} in {relative_path}")
    if not filename or Path(filename).suffix.lower() != expected_suffix:
        raise ValueError(f"Expected a {expected_suffix} file in {relative_path}")


def landing_files(root: Path) -> list[tuple[Path, str]]:
    if not root.is_dir():
        raise ValueError(f"Landing folder not found: {root}. Complete Part 1 first.")

    files = sorted(path for path in root.rglob("*") if path.is_file())
    if not files:
        raise ValueError(f"No files found in {root}. Complete Part 1 first.")

    result = []
    for path in files:
        relative = path.relative_to(root)
        validate_path(relative)
        result.append((path, relative.as_posix()))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Show planned paths; do not contact Azure")
    parser.add_argument("--landing", type=Path, default=LANDING, help=argparse.SUPPRESS)
    args = parser.parse_args()

    try:
        # Check all paths before any upload, so a bad folder cannot be silently skipped.
        files = landing_files(args.landing)
    except ValueError as exc:
        parser.error(str(exc))

    if args.dry_run:
        for _, blob_name in files:
            print(f"READY {blob_name}")
        print("Dry run complete: Azure was not contacted.")
        return 0

    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        parser.error("Set AZURE_STORAGE_CONNECTION_STRING before uploading to Azure")

    from azure.storage.blob import BlobServiceClient

    container_name = os.getenv("AZURE_STORAGE_CONTAINER", "bronze")
    container = BlobServiceClient.from_connection_string(connection_string).get_container_client(container_name)
    for path, blob_name in files:
        blob = container.get_blob_client(blob_name)
        if blob.exists():
            print(f"SKIP existing path: {blob_name}")
            continue
        with path.open("rb") as stream:
            blob.upload_blob(stream, overwrite=False)
        print(f"UPLOADED {blob_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
