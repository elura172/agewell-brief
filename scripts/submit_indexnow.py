"""Submit changed public URLs to IndexNow after a successful publication run."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def load_key() -> str:
    key_file = os.environ.get(
        "INDEXNOW_KEY_FILE", "public/c82fc24c87f9437da381a53fd326273d.txt"
    )
    value = Path(key_file).read_text(encoding="utf-8").strip()
    if not value:
        raise ValueError(f"IndexNow key file is empty: {key_file}")
    return value


def submit(urls: list[str]) -> int:
    if not urls:
        print("IndexNow: no changed article URLs to submit")
        return 0

    key = load_key()
    host = os.environ.get("PUBLIC_SITE_URL", "https://agewellbrief.com").rstrip("/")
    payload = {
        "host": host.removeprefix("https://").removeprefix("http://"),
        "key": key,
        "keyLocation": f"{host}/{Path(os.environ.get('INDEXNOW_KEY_FILE', 'public/c82fc24c87f9437da381a53fd326273d.txt')).name}",
        "urlList": urls,
    }
    request = Request(
        "https://api.indexnow.org/indexnow",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            print(f"IndexNow: submitted {len(urls)} URL(s), HTTP {response.status}")
    except HTTPError as error:
        print(f"IndexNow: submission rejected, HTTP {error.code}")
        return 1
    except URLError as error:
        print(f"IndexNow: network error: {error.reason}")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--urls-file", required=True)
    args = parser.parse_args()
    urls = [line.strip() for line in Path(args.urls_file).read_text().splitlines() if line.strip()]
    return submit(urls)


if __name__ == "__main__":
    raise SystemExit(main())
