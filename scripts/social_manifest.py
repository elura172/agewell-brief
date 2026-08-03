"""Maintain the persistent social/content-factory manifest."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

MANIFEST_VERSION = 1
DEFAULT_MANIFEST = Path(".state/social/manifest.json")


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read_json(path: Path, fallback: object) -> object:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def default_platform() -> dict[str, object]:
    return {"status": "pending", "request_id": None, "job_id": None, "updated_at": now()}


def sync(packages_path: Path, manifest_path: Path) -> int:
    payload = read_json(packages_path, {"packages": []})
    manifest = read_json(
        manifest_path,
        {"schema_version": MANIFEST_VERSION, "updated_at": now(), "articles": {}},
    )
    articles = manifest.setdefault("articles", {})
    records_root = Path(".state/content-records")
    video_root = Path(".state/video-jobs")

    for package in payload.get("packages", []):
        article_id = str(package["article"])
        previous = articles.get(article_id, {})
        platforms = previous.get("platforms", {})
        for platform in ("facebook", "tiktok", "youtube"):
            platforms.setdefault(platform, default_platform())
        record = {
            "schema_version": 1,
            "generated_at": now(),
            "article": package,
            "platforms": platforms,
        }
        record_path = records_root / f"{article_id}.json"
        video_job_path = video_root / f"{article_id}.json"
        write_json(record_path, record)
        write_json(video_job_path, package["mpt_job"])
        articles[article_id] = {
            "article_id": article_id,
            "article_url": package["url"],
            "title": package["content_record"]["title"],
            "category": package["category"],
            "content_record": str(record_path),
            "video_job": str(video_job_path),
            "platforms": platforms,
            "updated_at": now(),
        }

    manifest["schema_version"] = MANIFEST_VERSION
    manifest["updated_at"] = now()
    write_json(manifest_path, manifest)
    print(f"Social manifest: synchronized {len(payload.get('packages', []))} package(s)")
    return 0


def register(args: argparse.Namespace) -> int:
    manifest = read_json(args.manifest, {"schema_version": MANIFEST_VERSION, "articles": {}})
    article = manifest.setdefault("articles", {}).get(args.article_id)
    if not article:
        raise SystemExit(f"Unknown article_id: {args.article_id}")
    platform = article.setdefault("platforms", {}).setdefault(args.platform, default_platform())
    platform.update({"status": "queued", "request_id": args.request_id, "job_id": args.job_id, "updated_at": now()})
    manifest["updated_at"] = now()
    write_json(args.manifest, manifest)
    print(f"Social manifest: registered {args.platform} job for {args.article_id}")
    return 0


def status(args: argparse.Namespace) -> int:
    key = os.environ.get("UPLOAD_POST_API_KEY", "").strip()
    if not key:
        print("Social status: UPLOAD_POST_API_KEY not configured; nothing reconciled")
        return 0
    manifest = read_json(args.manifest, {"schema_version": MANIFEST_VERSION, "articles": {}})
    changed = 0
    for article in manifest.get("articles", {}).values():
        for platform, state in article.get("platforms", {}).items():
            request_id = state.get("request_id")
            if not request_id or state.get("status") in {"completed", "failed"}:
                continue
            url = "https://api.upload-post.com/api/uploadposts/status?" + urlencode({"request_id": request_id})
            request = Request(url, headers={"Authorization": f"Apikey {key}"})
            try:
                with urlopen(request, timeout=20) as response:
                    result = json.loads(response.read().decode("utf-8"))
            except (HTTPError, URLError, TimeoutError) as error:
                state["last_error"] = type(error).__name__
                state["updated_at"] = now()
                changed += 1
                continue
            for item in result.get("results", []):
                if item.get("platform") != platform:
                    continue
                state.update(
                    {
                        "status": item.get("status", result.get("status", "processing")),
                        "success": item.get("success"),
                        "post_id": item.get("post_id"),
                        "url": item.get("url"),
                        "updated_at": now(),
                    }
                )
                changed += 1
    if changed:
        manifest["updated_at"] = now()
        write_json(args.manifest, manifest)
    print(f"Social status: reconciled {changed} platform state(s)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    sync_parser = subparsers.add_parser("sync")
    sync_parser.add_argument("--packages", type=Path, default=Path(".state/social/latest.json"))
    sync_parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    register_parser = subparsers.add_parser("register")
    register_parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    register_parser.add_argument("--article-id", required=True)
    register_parser.add_argument("--platform", choices=["facebook", "tiktok", "youtube"], required=True)
    register_parser.add_argument("--request-id", required=True)
    register_parser.add_argument("--job-id", required=True)
    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    if args.command == "sync":
        return sync(args.packages, args.manifest)
    if args.command == "register":
        return register(args)
    return status(args)


if __name__ == "__main__":
    raise SystemExit(main())
