"""Fetch read-only ClickBank affiliate analytics by Agewell tracking ID."""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / ".state/clickbank-analytics.json"
BASE_URL = os.getenv("CLICKBANK_API_BASE", "https://api.clickbank.com/rest/1.3/analytics")
METRICS = (
    "DIMENSION_VALUE",
    "HOP_COUNT",
    "SALE_COUNT",
    "NET_SALE_AMOUNT",
    "REFUND_COUNT",
    "REFUND_AMOUNT",
    "EARNINGS_PER_HOP",
)


def fetch_report(api_key: str, account: str, start: str, end: str) -> tuple[int, object]:
    params = {
        "account": account,
        "startDate": start,
        "endDate": end,
        "orderBy": "NET_SALE_AMOUNT",
        "sortAscending": "false",
    }
    params["select"] = list(METRICS)
    # ClickBank documents the route with uppercase placeholders, but the
    # deployed REST service expects the concrete role/dimension path lowercase.
    url = f"{BASE_URL}/affiliate/tracking_id?{urllib.parse.urlencode(params, doseq=True)}"
    request = urllib.request.Request(
        url,
        headers={"Authorization": api_key, "Accept": "application/json", "User-Agent": "AgewellBrief/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return int(getattr(response, "status", 200)), json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read(1000).decode("utf-8", errors="replace").strip()
        raise RuntimeError(
            f"ClickBank analytics rejected the request with HTTP {exc.code}. "
            "Confirm the API key has the Analytics role and the account nickname is correct. "
            f"Response: {detail[:300]}"
        ) from exc


def main() -> int:
    api_key = os.getenv("CLICKBANK_API_KEY", "")
    account = os.getenv("CLICKBANK_ACCOUNT_NICKNAME", "")
    if not api_key or not account:
        print("CLICKBANK_API_KEY and CLICKBANK_ACCOUNT_NICKNAME are required", file=sys.stderr)
        return 2

    today = dt.date.today()
    start = os.getenv("CLICKBANK_START_DATE", (today - dt.timedelta(days=30)).isoformat())
    end = os.getenv("CLICKBANK_END_DATE", today.isoformat())
    status, payload = fetch_report(api_key, account, start, end)
    report = {
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "account": account,
        "start_date": start,
        "end_date": end,
        "http_status": status,
        "metrics": list(METRICS),
        "data": payload,
        "note": "Read-only performance data. Use it to tune offer rotation; it does not change editorial selection or health claims.",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote ClickBank analytics for {start} through {end} to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
