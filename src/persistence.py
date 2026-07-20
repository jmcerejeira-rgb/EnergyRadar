from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


def load_seen(path: Path) -> dict:
    """Load already processed item IDs from disk."""
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        # If the file becomes corrupted, do not crash the whole radar.
        return {}


def save_seen(path: Path, seen: dict) -> None:
    """Persist already processed item IDs to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2, sort_keys=True)


def prune_seen(seen: dict, days: int = 90) -> dict:
    """Keep the seen database small by removing old entries."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    pruned = {}

    for item_id, meta in seen.items():
        first_seen = meta.get("first_seen") if isinstance(meta, dict) else None
        if not first_seen:
            continue

        try:
            dt = datetime.fromisoformat(first_seen.replace("Z", "+00:00"))
        except ValueError:
            continue

        if dt >= cutoff:
            pruned[item_id] = meta

    return pruned


def filter_new_items(items: Iterable[dict], seen: dict) -> list[dict]:
    """Return only items whose ID is not present in the seen database."""
    return [item for item in items if item.get("id") and item["id"] not in seen]


def mark_items_seen(seen: dict, items: Iterable[dict]) -> dict:
    """Add processed items to the seen database."""
    now = datetime.now(timezone.utc).isoformat()

    for item in items:
        item_id = item.get("id")
        if not item_id:
            continue

        seen[item_id] = {
            "first_seen": now,
            "source": item.get("source", ""),
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "published": item.get("published", ""),
        }

    return seen
