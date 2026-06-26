"""Shared Socrata API pagination helper used by all fetchers."""

import os
import time
from typing import Generator

import requests


BASE_URL = "https://data.cityofnewyork.us/resource"
PAGE_SIZE = 50_000
RETRY_WAIT = 5  # seconds between retries on transient errors
MAX_RETRIES = 3


def _headers() -> dict:
    token = os.getenv("SOCRATA_APP_TOKEN", "")
    if not token:
        print("WARNING: SOCRATA_APP_TOKEN not set — requests will be heavily throttled")
    return {"X-App-Token": token} if token else {}


def paginate(dataset_id: str, where: str = "", select: str = "") -> Generator[list[dict], None, None]:
    """Yield pages of records from a Socrata dataset."""
    offset = 0
    session = requests.Session()
    session.headers.update(_headers())

    while True:
        params: dict = {"$limit": PAGE_SIZE, "$offset": offset}
        if where:
            params["$where"] = where
        if select:
            params["$select"] = select

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = session.get(f"{BASE_URL}/{dataset_id}.json", params=params, timeout=60)
                resp.raise_for_status()
                break
            except requests.RequestException as exc:
                if attempt == MAX_RETRIES:
                    raise
                print(f"  Transient error ({exc}), retrying in {RETRY_WAIT}s …")
                time.sleep(RETRY_WAIT)

        rows = resp.json()
        if not rows:
            return

        yield rows

        if len(rows) < PAGE_SIZE:
            return

        offset += PAGE_SIZE


def sample(dataset_id: str, n: int = 5) -> list[dict]:
    """Return n rows to inspect field names before writing filter logic."""
    session = requests.Session()
    session.headers.update(_headers())
    resp = session.get(
        f"{BASE_URL}/{dataset_id}.json",
        params={"$limit": n},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()
