from __future__ import annotations

import re
import unicodedata
from typing import Any


def _norm(text: str) -> str:
    """Normalise text for case/accent-insensitive matching."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text.lower()).strip()


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return []


def get_watchlist_terms(watchlist: dict) -> dict[str, list[str]]:
    """Return watchlist terms grouped by category."""
    return {
        "companies": _as_list(watchlist.get("companies")),
        "buyers_investors": _as_list(watchlist.get("buyers_investors")),
    }


def find_watchlist_hits(item: dict, watchlist: dict) -> dict[str, list[str]]:
    """Find exact-ish watchlist mentions in title/summary/source."""
    text = _norm(" ".join([
        str(item.get("title", "")),
        str(item.get("summary", "")),
        str(item.get("source", "")),
    ]))

    hits: dict[str, list[str]] = {}
    for category, terms in get_watchlist_terms(watchlist).items():
        matched = []
        for term in terms:
            norm_term = _norm(term)
            if not norm_term:
                continue

            # Word-ish boundary matching avoids matching tiny terms inside larger words.
            # Still tolerant of accents/case because both sides are normalised.
            pattern = r"(?<!\w)" + re.escape(norm_term) + r"(?!\w)"
            if re.search(pattern, text):
                matched.append(term)

        if matched:
            hits[category] = matched

    return hits


def annotate_watchlist_items(items: list[dict], watchlist: dict) -> list[dict]:
    """Add watchlist metadata to each item without mutating the original list."""
    annotated = []
    for item in items:
        new_item = dict(item)
        hits = find_watchlist_hits(new_item, watchlist)
        new_item["watchlist_hits"] = hits
        new_item["watchlist_priority"] = 1 if hits else 0
        annotated.append(new_item)
    return annotated


def sort_by_watchlist_priority(items: list[dict]) -> list[dict]:
    """Put watchlist hits first, then keep stable-ish ordering by source/title."""
    return sorted(
        items,
        key=lambda x: (
            int(x.get("watchlist_priority", 0)),
            len(x.get("summary", "") or ""),
        ),
        reverse=True,
    )


def build_watchlist_prompt(watchlist: dict) -> str:
    terms = get_watchlist_terms(watchlist)
    companies = ", ".join(terms.get("companies", [])) or "nenhuma"
    buyers = ", ".join(terms.get("buyers_investors", [])) or "nenhum"

    return f"""
Watchlist interna:
- Empresas/targets a monitorizar: {companies}
- Compradores/investidores a monitorizar: {buyers}

Regras específicas da watchlist:
1. Dá prioridade analítica a notícias que mencionem empresas da watchlist.
2. Não transformes uma simples menção numa oportunidade M&A sem trigger concreto.
3. Se uma empresa da watchlist surgir sem trigger transacional, classifica no máximo como score 3.
4. Se surgirem compradores/investidores da watchlist, usa-os apenas quando a notícia suportar essa ligação.
5. No campo "proximo_passo", sugere uma ação comercial concreta quando houver hit da watchlist.
""".strip()


def build_watchlist_hits_for_report(items: list[dict]) -> list[dict]:
    """Create a compact report section with only items that hit the watchlist."""
    rows = []
    for item in items:
        hits = item.get("watchlist_hits") or {}
        if not hits:
            continue
        rows.append({
            "title": item.get("title", ""),
            "source": item.get("source", ""),
            "published": item.get("published", ""),
            "url": item.get("url", ""),
            "companies": ", ".join(hits.get("companies", [])),
            "buyers_investors": ", ".join(hits.get("buyers_investors", [])),
        })
    return rows
