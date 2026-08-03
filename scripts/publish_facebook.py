"""Submit released Agewell article copy to Facebook through Upload-Post.

This is intentionally idempotent. The persistent manifest is the source of
truth, so a retry will not submit a second Facebook post for the same article.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ENDPOINT = "https://api.upload-post.com/api/upload_text"


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read_json(path: Path, fallback: object) -> object:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def submit(package: dict[str, object], api_key: str, username: str) -> dict[str, object]:
    article_id = str(package["article"])
    facebook = package["facebook"]
    fields = {
        "user": username,
        "platform[]": "facebook",
        "title": str(facebook["title"]),
        "facebook_link_url": str(facebook["link_url"]),
        "async_upload": "true",
        "request_id": f"agewell-facebook-{article_id}",
    }
    request = Request(
        ENDPOINT,
        data=urlencode(fields).encode("utf-8"),
        headers={
            "Authorization": f"Apikey {api_key}",
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Idempotency-Key": fields["request_id"],
        },
        method="POST",
    )
    with urlopen(request, timeout=45) as response:
        result = json.loads(response.read().decode("utf-8"))
    return {"request_id": fields["request_id"], "response": result}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packages", type=Path, default=Path(".state/social/latest.json"))
    parser.add_argument("--manifest", type=Path, default=Path(".state/social/manifest.json"))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    api_key = os.environ.get("UPLOAD_POST_API_KEY", "").strip()
    username = os.environ.get("UPLOAD_POST_USERNAME", "").strip()
    if not api_key or not username:
        print("Facebook handoff: credentials unavailable; skipped")
        return 1 if args.strict else 0

    payload = read_json(args.packages, {"packages": []})
    manifest = read_json(args.manifest, {"schema_version": 1, "articles": {}})
    failures = 0
    submitted = 0
    for package in payload.get("packages", []):
        article_id = str(package["article"])
        article = manifest.get("articles", {}).get(article_id)
        if not article:
            print(f"Facebook handoff: {article_id} missing from manifest")
            failures += 1
            continue
        state = article.setdefault("platforms", {}).setdefault(
            "facebook", {"status": "pending", "request_id": None, "job_id": None}
        )
        if state.get("status") in {"queued", "processing", "completed"}:
            continue
        try:
            result = submit(package, api_key, username)
            response = result["response"]
            state.update(
                {
                    "status": response.get("status", "queued"),
                    "request_id": response.get("request_id", result["request_id"]),
                    "job_id": response.get("job_id"),
                    "updated_at": now(),
                    "error": None,
                }
            )
            submitted += 1
            print(f"Facebook handoff: submitted {article_id}")
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
            failures += 1
            state.update(
                {
                    "status": "upload_failed",
                    "updated_at": now(),
                    "error": f"{type(error).__name__}: {error}",
                }
            )
            print(f"Facebook handoff: failed {article_id}: {type(error).__name__}")

    manifest["updated_at"] = now()
    write_json(args.manifest, manifest)
    print(f"Facebook handoff: submitted {submitted}; failures {failures}")
    return 1 if args.strict and failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
