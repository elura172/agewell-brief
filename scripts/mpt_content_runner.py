"""Run the local MoneyPrinterTurbo handoff and publish its social jobs.

This worker is intentionally separate from Cloudflare/GitHub Actions because
video rendering is long-running and requires the local MoneyPrinterTurbo
installation, FFmpeg, and media-provider access.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import mimetypes
import subprocess
import tomllib
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

MANIFEST = Path(".state/social/manifest.json")
MPT_HOME = Path("/Users/mirrr/MoneyPrinterTurbo")
ARTICLE_BASE = "https://agewellbrief.com"


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def mpt_config() -> dict:
    return tomllib.loads((MPT_HOME / "config.toml").read_text(encoding="utf-8"))["app"]


def pending_articles(manifest: dict) -> list[dict]:
    items = []
    for article in manifest.get("articles", {}).values():
        video = article.get("video_job")
        if not video or not Path(video).exists():
            continue
        job = load(Path(video))
        platforms = article.get("platforms", {})
        if job.get("status") in {"ready_for_mpt", "generated", "uploaded", "upload_failed"}:
            video_pending = any(
                platforms.get(name, {}).get("status") not in {"completed", "queued", "processing"}
                for name in ("tiktok", "youtube")
            )
            facebook_pending = platforms.get("facebook", {}).get("status") not in {"completed", "queued", "processing"}
            if video_pending or facebook_pending:
                items.append({
                    "article": article,
                    "job": job,
                    "video_path": Path(job.get("video_path", "")),
                    "video_pending": video_pending,
                    "facebook_pending": facebook_pending,
                })
    return items


def run_mpt(job: dict) -> tuple[Path, str]:
    args = [
        "uv", "run", "--no-project", "--python", "3.11", "python", "mpt_agent.py",
        "--subject", str(job["subject"]), "--",
        "--voice-name", str(job.get("voice_name", "en-US-AvaNeural")),
        "--text-fore-color", str(job.get("text_fore_color", "#FEFEFE")),
        "--highlight-color", str(job.get("highlight_color", "#F59E0B")),
        "--stroke-color", str(job.get("stroke_color", "#0B0F19")),
        "--stroke-width", str(job.get("stroke_width", 2)),
        "--font-size", str(job.get("font_size", 48)),
        "--subtitle-bottom-margin", str(job.get("subtitle_bottom_margin", 210)),
        "--max-words-per-line", str(job.get("max_words_per_line", 3)),
        "--active-word-scale", str(job.get("active_word_scale", 1.12)),
        "--subtitle-bg-color", str(job.get("subtitle_bg_color", "rgba(11, 15, 25, 0.75)")),
        "--subtitle-bg-padding", str(job.get("subtitle_bg_padding", 12)),
        "--subtitle-glow-enabled",
    ]
    result = subprocess.run(args, cwd=MPT_HOME / "docs/skill", capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"MoneyPrinterTurbo failed with exit code {result.returncode}")
    values = {}
    for line in result.stdout.splitlines():
        if line.startswith("VIDEO_FILE=") or line.startswith("TASK_DIR=") or line.startswith("LOG_FILE="):
            key, value = line.split("=", 1)
            values[key] = value.strip()
    if not values.get("VIDEO_FILE"):
        raise RuntimeError("MoneyPrinterTurbo completed without a VIDEO_FILE result")
    return Path(values["VIDEO_FILE"]), values.get("TASK_DIR", "")


def multipart(fields: list[tuple[str, str]], video: Path) -> tuple[bytes, str]:
    boundary = "----AgewellBoundary" + uuid.uuid4().hex
    chunks: list[bytes] = []
    for name, value in fields:
        chunks.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            str(value).encode(), b"\r\n",
        ])
    mime = mimetypes.guess_type(video.name)[0] or "video/mp4"
    chunks.extend([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="video"; filename="{video.name}"\r\n'.encode(),
        f"Content-Type: {mime}\r\n\r\n".encode(), video.read_bytes(), b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ])
    return b"".join(chunks), boundary


def upload_video(config: dict, article: dict, job: dict, video: Path) -> dict:
    article_id = article["article_id"]
    request_id = f"agewell-video-{article_id}"
    fields = [
        ("user", config["upload_post_username"]), ("platform[]", "tiktok"), ("platform[]", "youtube"),
        ("title", article["title"]), ("youtube_title", article["title"][:100]),
        ("youtube_description", f"{article['title']}\n\nRead the full brief: {article['article_url']}"),
        ("privacyStatus", "public"), ("post_mode", "DIRECT_POST"), ("is_aigc", "true"),
        ("containsSyntheticMedia", "true"), ("defaultLanguage", "en"), ("defaultAudioLanguage", "en-US"),
        ("async_upload", "true"), ("request_id", request_id),
    ]
    body, boundary = multipart(fields, video)
    request = urllib.request.Request(
        "https://api.upload-post.com/api/upload", data=body, method="POST",
        headers={"Authorization": f"Apikey {config['upload_post_api_key']}", "Content-Type": f"multipart/form-data; boundary={boundary}", "Idempotency-Key": request_id},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def upload_facebook(config: dict, article: dict, package: dict) -> dict:
    request_id = f"agewell-facebook-{article['article_id']}"
    title = package["facebook"]["title"]
    fields = {
        "user": config["upload_post_username"], "platform[]": "facebook", "title": title,
        "facebook_link_url": article["article_url"], "async_upload": "true", "request_id": request_id,
    }
    request = urllib.request.Request(
        "https://api.upload-post.com/api/upload_text", data=urllib.parse.urlencode(fields).encode(), method="POST",
        headers={"Authorization": f"Apikey {config['upload_post_api_key']}", "Content-Type": "application/x-www-form-urlencoded", "Idempotency-Key": request_id},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def set_job_status(article: dict, job: dict, status: str, **extra: object) -> None:
    job.update({"status": status, "updated_at": now(), **extra})
    save(Path(article["video_job"]), job)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-items", type=int, default=1)
    parser.add_argument("--publish", action="store_true", help="submit generated media to Upload-Post")
    args = parser.parse_args()
    manifest = load(MANIFEST)
    config = mpt_config()
    if args.publish and not config.get("upload_post_api_key"):
        raise SystemExit("Upload-Post is not configured in MoneyPrinterTurbo config.toml")

    processed = 0
    dirty = False
    items = pending_articles(manifest)[: args.max_items]
    if not items:
        print("MPT content runner: no pending content jobs")
        return 0
    for item in items:
        dirty = True
        article, job, video_path = item["article"], item["job"], item["video_path"]
        if item["video_pending"] and not video_path.is_file():
            video_path, task_dir = run_mpt(job)
            set_job_status(article, job, "generated", video_path=str(video_path), task_dir=task_dir)
        if not args.publish:
            print(f"MPT dry run: generated/ready {article['article_id']}")
            processed += 1
            continue
        if item["facebook_pending"]:
            try:
                facebook_state = manifest["articles"][article["article_id"]]["platforms"]["facebook"]
                record = load(Path(article["content_record"]))
                result = upload_facebook(config, article, record["article"])
                facebook_state.update({
                    "status": "queued", "request_id": result.get("request_id"),
                    "job_id": result.get("job_id"), "updated_at": now(),
                })
            except (OSError, urllib.error.HTTPError, urllib.error.URLError) as error:
                manifest["articles"][article["article_id"]]["platforms"]["facebook"].update({
                    "status": "upload_failed", "last_error": type(error).__name__, "updated_at": now(),
                })
        if item["video_pending"]:
            try:
                result = upload_video(config, article, job, video_path)
                for platform in ("tiktok", "youtube"):
                    manifest["articles"][article["article_id"]]["platforms"][platform].update({
                        "status": "queued", "request_id": result.get("request_id"), "job_id": result.get("job_id"), "updated_at": now(),
                    })
                set_job_status(article, job, "uploaded", upload_request_id=result.get("request_id"), upload_job_id=result.get("job_id"))
                processed += 1
            except (OSError, urllib.error.HTTPError, urllib.error.URLError, IsADirectoryError) as error:
                set_job_status(article, job, "upload_failed", last_error=type(error).__name__)
                print(f"MPT upload failed for {article['article_id']}: {type(error).__name__}")
        elif item["facebook_pending"]:
            processed += 1
    if dirty:
        manifest["updated_at"] = now()
        save(MANIFEST, manifest)
    print(f"MPT content runner: processed {processed} article(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
