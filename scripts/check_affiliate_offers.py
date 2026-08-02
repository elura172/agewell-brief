from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from agewell.affiliates import parse_offer_config, write_health_report


ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    raw = os.getenv("AFFILIATE_OFFERS_JSON", "{}")
    try:
        configured = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"AFFILIATE_OFFERS_JSON is invalid JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(configured, dict):
        print("AFFILIATE_OFFERS_JSON must be a JSON object", file=sys.stderr)
        return 2

    offers = parse_offer_config(configured)
    if not offers:
        print("No ClickBank offers are configured; no link check was needed.")
        return 0

    target = Path(os.getenv("AFFILIATE_HEALTH_FILE", ROOT / ".state/affiliate-health.json"))
    report = write_health_report(target, configured)
    for entry in report["offers"]:
        print(f"{entry['category']}: {entry['name']} -> {entry['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
