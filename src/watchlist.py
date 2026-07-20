from __future__ import annotations
from typing import Any

def _entities(config: dict[str, Any]) -> list[dict[str, Any]]:
    return list((config or {}).get("entities") or [])

def annotate_watchlist_items(items: list[dict], config: dict) -> list[dict]:
    entities = _entities(config)
    result = []
    for item in items:
        text = " ".join(str(item.get(k, "")) for k in ("title", "summary", "source")).lower()
        hits = []
        max_priority = 0
        for entity in entities:
            name = str(entity.get("name", "")).strip()
            if name and name.lower() in text:
                hits.append(name)
                max_priority = max(max_priority, int(entity.get("priority", 0) or 0))
        enriched = dict(item)
        enriched["watchlist_hits"] = hits
        enriched["watchlist_priority"] = max_priority
        result.append(enriched)
    return result

def sort_by_watchlist_priority(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda x: int(x.get("watchlist_priority", 0) or 0), reverse=True)

def build_watchlist_prompt(config: dict) -> str:
    lines = ["WATCHLIST:"]
    for entity in _entities(config):
        lines.append(
            f"- {entity.get('name')}: prioridade {entity.get('priority', 0)}; "
            f"geografias {', '.join(entity.get('geographies') or [])}; "
            f"setores {', '.join(entity.get('sectors') or [])}."
        )
    lines.append("Uma menção à watchlist, por si só, não é trigger transacional.")
    return "\n".join(lines)
