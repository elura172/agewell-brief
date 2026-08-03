from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_MAX_HITS = int(os.getenv("EVERGREEN_CONTEXT_MAX_HITS", "2"))
DEFAULT_MAX_CHARS = int(os.getenv("EVERGREEN_CONTEXT_MAX_CHARS", "1800"))
STOPWORDS = {
    "about", "after", "again", "also", "been", "being", "between", "could", "does",
    "from", "have", "into", "more", "most", "other", "over", "said", "some", "that",
    "their", "there", "these", "they", "this", "through", "under", "what", "when",
    "where", "which", "while", "with", "would", "your", "health", "study", "research",
}


@dataclass(frozen=True)
class ContextDocument:
    source_id: str
    path: str
    title: str
    kind: str
    text: str


@dataclass(frozen=True)
class ContextHit:
    source_id: str
    path: str
    title: str
    kind: str
    score: int
    excerpt: str

    def prompt_dict(self) -> dict[str, Any]:
        return {
            "source": self.title,
            "source_kind": self.kind,
            "provenance": Path(self.path).name,
            "excerpt": self.excerpt,
            "use": "Background framing only; not current medical evidence.",
        }

    def audit_dict(self) -> dict[str, Any]:
        # Do not write transcript excerpts into the repository's audit trail.
        return {
            "source_id": self.source_id,
            "source": self.title,
            "source_kind": self.kind,
            "provenance": self.path,
            "score": self.score,
        }


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z][a-z0-9'-]{2,}", value.lower())
        if token not in STOPWORDS
    }


def _title(path: Path, text: str) -> str:
    for line in text.splitlines():
        match = re.match(r"^#{1,3}\s+(.+?)\s*$", line)
        if match:
            return match.group(1).strip()
    return path.stem.replace("_", " ").replace("-", " ").strip()


def _kind(label: str, path: Path) -> str:
    value = f"{label} {path}".lower()
    return "spiral_framework" if "spiral" in value or "cellular light" in value else "program_transcript"


def _sources_from_env() -> list[tuple[str, Path, str]]:
    raw = os.getenv("EVERGREEN_CONTEXT_SOURCES_JSON", "")
    if raw:
        try:
            values = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("EVERGREEN_CONTEXT_SOURCES_JSON must be valid JSON") from exc
        if not isinstance(values, list):
            raise RuntimeError("EVERGREEN_CONTEXT_SOURCES_JSON must contain a list")
        result = []
        for value in values:
            if not isinstance(value, dict) or not value.get("path"):
                raise RuntimeError("Each evergreen context source requires a path")
            path = Path(str(value["path"])).expanduser()
            result.append((str(value.get("label", path.name)), path, str(value.get("kind", ""))))
        return result

    raw_dirs = os.getenv("EVERGREEN_CONTEXT_DIRS_JSON", "")
    if not raw_dirs:
        return []
    try:
        dirs = json.loads(raw_dirs)
    except json.JSONDecodeError as exc:
        raise RuntimeError("EVERGREEN_CONTEXT_DIRS_JSON must be valid JSON") from exc
    if not isinstance(dirs, list):
        raise RuntimeError("EVERGREEN_CONTEXT_DIRS_JSON must contain a list")
    return [(Path(str(path)).expanduser().name, Path(str(path)).expanduser(), "") for path in dirs]


def _chunk(text: str, size: int = 900, overlap: int = 120) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks = []
    step = max(1, size - overlap)
    for start in range(0, len(words), step):
        value = " ".join(words[start : start + size]).strip()
        if value:
            chunks.append(value)
        if start + size >= len(words):
            break
    return chunks


def build_context_index() -> list[ContextDocument]:
    documents: list[ContextDocument] = []
    
    # 1. Load structured biophysics pioneer lineage (Mae-Wan Ho, Popp, Pollack, Warburg, Becker, etc.)
    lineage_file = Path(__file__).resolve().parent.parent / "config/biophysics-lineage.json"
    if lineage_file.exists():
        try:
            payload = json.loads(lineage_file.read_text(encoding="utf-8"))
            for p in payload.get("pioneers", []):
                p_name = p.get("name", "")
                p_year = p.get("year", "")
                p_work = p.get("core_work", "")
                p_summary = p.get("summary", "")
                p_app = p.get("application", "")
                p_concepts = ", ".join(p.get("concepts", []))
                
                text_block = (
                    f"Biophysics Pioneer: {p_name} ({p_year}). Core Work: {p_work}. "
                    f"Summary: {p_summary} Key Concepts: {p_concepts}. Application: {p_app}"
                )
                source_id = hashlib.sha256(f"pioneer:{p.get('id')}".encode()).hexdigest()[:16]
                documents.append(
                    ContextDocument(
                        source_id=source_id,
                        path=str(lineage_file),
                        title=f"{p_name} ({p_year}) — {p_work}",
                        kind="biophysics_lineage",
                        text=text_block
                    )
                )
        except Exception as err:
            print(f"Biophysics lineage load warning: {err}")

    # 2. Load environment context sources
    for label, root, explicit_kind in _sources_from_env():
        if not root.exists():
            continue
        paths = [root] if root.is_file() else sorted(set(root.rglob("*.md")) | set(root.rglob("*.txt")))
        for path in paths:
            if path.name.endswith(".backup") or "highlights" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            title = _title(path, text)
            kind = explicit_kind or _kind(label, path)
            for number, chunk in enumerate(_chunk(text)):
                source_id = hashlib.sha256(f"{path}:{number}".encode()).hexdigest()[:16]
                documents.append(ContextDocument(source_id, str(path), title, kind, chunk))
    return documents


def retrieve_context(
    query: str,
    documents: list[ContextDocument],
    max_hits: int = DEFAULT_MAX_HITS,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> list[ContextHit]:
    query_terms = _tokens(query)
    if not query_terms:
        return []
    ranked: list[ContextHit] = []
    for document in documents:
        terms = _tokens(f"{document.title} {document.text}")
        overlap = query_terms & terms
        if not overlap:
            continue
        score = len(overlap) * 3 + sum(1 for term in overlap if term in _tokens(document.title)) * 2
        ranked.append(ContextHit(document.source_id, document.path, document.title, document.kind, score, document.text[:max_chars]))
    ranked.sort(key=lambda hit: (-hit.score, hit.path))
    return ranked[:max_hits]


def context_audit(hits: list[ContextHit]) -> list[dict[str, Any]]:
    return [hit.audit_dict() for hit in hits]
