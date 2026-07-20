from __future__ import annotations
import hashlib, json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

def _now() -> datetime:
    return datetime.now(timezone.utc)

def _normalise_url(url: str) -> str:
    try:
        p = urlsplit(url.strip())
        query = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith(("utm_", "fbclid", "gclid"))]
        return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), urlencode(query), ""))
    except Exception:
        return url.strip().lower()

def item_key(item: dict) -> str:
    base = _normalise_url(str(item.get("url") or ""))
    if not base:
        base = f"{item.get('source','')}|{item.get('title','')}".lower().strip()
    return hashlib.sha256(base.encode("utf-8")).hexdigest()

def editorial_key(item: dict) -> str:
    text = " ".join(str(item.get(k) or "") for k in ("title", "source")).lower()
    words = [w for w in "".join(c if c.isalnum() else " " for c in text).split() if len(w) > 3]
    return hashlib.sha256(" ".join(sorted(set(words))[:30]).encode("utf-8")).hexdigest()

def load_seen(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_seen(path: Path, seen: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(seen, ensure_ascii=False, indent=2), encoding="utf-8")

def prune_seen(seen: dict, days: int = 90) -> dict:
    cutoff = _now() - timedelta(days=days)
    out = {}
    for key, value in (seen or {}).items():
        try:
            when = datetime.fromisoformat(value["seen_at"])
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            if when >= cutoff:
                out[key] = value
        except Exception:
            continue
    return out

def filter_new_items(items: list[dict], seen: dict, editorial_days: int = 7) -> list[dict]:
    cutoff = _now() - timedelta(days=editorial_days)
    recent_editorial = set()
    for value in (seen or {}).values():
        try:
            when = datetime.fromisoformat(value["seen_at"])
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            if when >= cutoff and value.get("editorial_key"):
                recent_editorial.add(value["editorial_key"])
        except Exception:
            pass
    result = []
    for item in items:
        if item_key(item) in seen:
            continue
        if editorial_key(item) in recent_editorial:
            continue
        result.append(item)
    return result

def mark_items_seen(seen: dict, items: list[dict]) -> dict:
    out = dict(seen or {})
    stamp = _now().isoformat()
    for item in items:
        out[item_key(item)] = {
            "seen_at": stamp,
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "editorial_key": editorial_key(item),
        }
    return out
