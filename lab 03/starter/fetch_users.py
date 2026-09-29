"""Prepared helper: save one public API response as a local JSON file."""

import json
from pathlib import Path

import requests


URL = "https://jsonplaceholder.typicode.com/users"
TARGET = Path("landing/users/2025/09/02/source=api/users.json")


def main() -> None:
    response = requests.get(URL, timeout=15)
    response.raise_for_status()
    users = response.json()
    if not isinstance(users, list):
        raise ValueError("The API did not return the expected list of users")

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(users, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(users)} users to {TARGET}")


if __name__ == "__main__":
    main()
