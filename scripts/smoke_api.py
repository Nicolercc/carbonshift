#!/usr/bin/env python3
"""Small API hardening smoke checks for CarbonShift."""

from __future__ import annotations

import csv
import io
import pathlib
import sys
from urllib.parse import quote

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from flask import abort
from src.web.app import app


SIGNAL_GROUPS = {"risk", "carbon", "compliance", "asbestos", "data_completeness"}


def _fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def _json(response, label: str):
    if not response.is_json:
        _fail(f"{label} returned {response.content_type}, expected JSON")
    return response.get_json()


def _smoke_forced_500():
    raise RuntimeError("smoke forced API 500")


def _smoke_forced_503():
    abort(503)


def _install_smoke_routes() -> None:
    if "_smoke_forced_500" not in app.view_functions:
        app.add_url_rule(
            "/api/_smoke/forced-500",
            endpoint="_smoke_forced_500",
            view_func=_smoke_forced_500,
        )
    if "_smoke_forced_503" not in app.view_functions:
        app.add_url_rule(
            "/api/_smoke/forced-503",
            endpoint="_smoke_forced_503",
            view_func=_smoke_forced_503,
        )


def main() -> int:
    app.config["PROPAGATE_EXCEPTIONS"] = False
    _install_smoke_routes()

    with app.test_client() as client:
        health = client.get("/api/health")
        health_json = _json(health, "/api/health")
        if health.status_code not in (200, 503):
            _fail(f"/api/health returned unexpected status {health.status_code}")
        if "database" not in health_json:
            _fail("/api/health JSON is missing database status")

        missing = client.get("/api/nope")
        _json(missing, "/api/nope")
        if missing.status_code != 404:
            _fail(f"/api/nope returned {missing.status_code}, expected 404")

        logger_disabled = app.logger.disabled
        app.logger.disabled = True
        try:
            forced_503 = client.get("/api/_smoke/forced-503")
            forced_500 = client.get("/api/_smoke/forced-500")
        finally:
            app.logger.disabled = logger_disabled

        _json(forced_503, "/api/_smoke/forced-503")
        if forced_503.status_code != 503:
            _fail(f"forced API 503 returned {forced_503.status_code}")

        _json(forced_500, "/api/_smoke/forced-500")
        if forced_500.status_code != 500:
            _fail(f"forced API 500 returned {forced_500.status_code}")

        if health.status_code == 503:
            print("SKIP: database-backed checks skipped because DB is unavailable")
            return 0

        search = client.get("/api/buildings/search?q=Murray&limit=1")
        search_json = _json(search, "/api/buildings/search")
        if search.status_code != 200:
            _fail(f"/api/buildings/search returned {search.status_code}")
        results = search_json.get("results") or []
        if not results:
            _fail("/api/buildings/search?q=Murray&limit=1 returned no rows")

        bin_val = str(results[0].get("bin") or "")
        if not bin_val:
            _fail("search result is missing bin")

        detail = client.get(f"/api/buildings/{bin_val}")
        detail_json = _json(detail, "/api/buildings/<bin>")
        if detail.status_code != 200:
            _fail(f"/api/buildings/{bin_val} returned {detail.status_code}")
        signal_keys = set((detail_json.get("signals") or {}).keys())
        if signal_keys != SIGNAL_GROUPS:
            _fail(f"/api/buildings/{bin_val} signals were {sorted(signal_keys)}")

        known_bin = "1063355"
        known_detail = client.get(f"/api/buildings/{known_bin}?limit=5")
        known_json = _json(known_detail, f"/api/buildings/{known_bin}")
        if known_detail.status_code == 404:
            print(f"SKIP: known BIN {known_bin} not in database")
        elif known_detail.status_code != 200:
            _fail(f"/api/buildings/{known_bin} returned {known_detail.status_code}")
        else:
            known_signals = set((known_json.get("signals") or {}).keys())
            if known_signals != SIGNAL_GROUPS:
                _fail(f"/api/buildings/{known_bin} signals were {sorted(known_signals)}")

        baseline = client.get(f"/building/{bin_val}/export.csv")
        if baseline.status_code != 200:
            _fail(f"baseline export returned {baseline.status_code}")
        baseline_rows = list(csv.DictReader(io.StringIO(baseline.get_data(as_text=True))))
        if len(baseline_rows) != 1:
            _fail(f"baseline export returned {len(baseline_rows)} rows, expected 1")

        payload = f"{bin_val}' OR '1'='1"
        injected = client.get(f"/building/{quote(payload, safe='')}/export.csv")
        if injected.status_code != 200:
            _fail(f"injection export returned {injected.status_code}")
        injected_rows = list(csv.DictReader(io.StringIO(injected.get_data(as_text=True))))
        if len(injected_rows) > 1:
            _fail("SQL injection payload returned multiple building rows")

    print("OK: API smoke checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
