from __future__ import annotations

import datetime as dt
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ReleaseCheck:
    article_id: str
    publishable: bool
    reasons: tuple[str, ...]
    source_status: str
    editorial_status: str
    metadata_review_status: str
    visual_review_status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EditionRecorder:
    def __init__(self, root: Path, edition_time: dt.datetime):
        self.edition_id = edition_time.date().isoformat()
        self.run_id = edition_time.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
        self.path = root / self.edition_id / self.run_id
        self.path.mkdir(parents=True, exist_ok=True)

    def write(self, name: str, value: Any) -> Path:
        target = self.path / f"{name}.json"
        target.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return target


def audit_release(
    article_id: str,
    source_url: str,
    story: dict[str, Any],
    metadata_status: str,
    visual_status: str,
    require_human_review: bool = True,
    require_visual_review: bool = True,
    require_metadata_review: bool = True,
) -> ReleaseCheck:
    reasons: list[str] = []
    if not source_url.startswith("https://"):
        reasons.append("original source URL is missing or not HTTPS")
    if not story.get("headline") or not story.get("dek"):
        reasons.append("headline or introduction is missing")
    if len(story.get("bullets", [])) != 3:
        reasons.append("story does not contain exactly three takeaways")
    if require_metadata_review and metadata_status != "approved":
        reasons.append("image metadata alignment is not approved")
    if require_visual_review and visual_status not in {"human-reviewed", "vision-approved"}:
        reasons.append("pixel-level image review is pending")
    if require_human_review:
        reasons.append("human editorial review is pending")
    return ReleaseCheck(
        article_id=article_id,
        publishable=not reasons,
        reasons=tuple(reasons),
        source_status="linked" if source_url.startswith("https://") else "invalid",
        editorial_status="pending" if require_human_review else "automated-checks",
        metadata_review_status=metadata_status,
        visual_review_status=visual_status,
    )
