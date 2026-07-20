from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import urljoin, urlparse
import time
import feedparser
import requests
import yaml
from bs4 import BeautifulSoup, Tag


DEFAULT_HEADERS = {
    "User-Agent": "Energy M&A Radar/0.3 (+local research tool)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SESSION = requests.Session()
SESSION.headers

PT_MONTHS = {
    "janeiro": "01", "jan": "01",
    "fevereiro": "02", "fev": "02",
    "março": "03", "marco": "03", "mar": "03",
    "abril": "04", "abr": "04",
    "maio": "05", "mai": "05",
    "junho": "06", "jun": "06",
    "julho": "07", "jul": "07",
    "agosto": "08", "ago": "08",
    "setembro": "09", "set": "09",
    "outubro": "10", "out": "10",
    "novembro": "11", "nov": "11",
    "dezembro": "12", "dez": "12",
}

JUNK_URL_PARTS = (
    "mailto:", "javascript:", "#", "/cookies", "/privacidade", "/privacy", "/contactos",
    "/contacts", "/mapa", "/sitemap", "/glossario", "/glossário", "/login", "/search",
    "facebook.com", "twitter.com", "x.com/", "linkedin.com/share", "whatsapp://",
)

DEFAULT_CONNECT_TIMEOUT = 10
DEFAULT_READ_TIMEOUT = 30


def load_yaml(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def _matches_any(text: str, terms: Iterable[str]) -> bool:
    blob = (text or "").lower()
    return any((term or "").lower() in blob for term in terms)


def _normalise_date(value: str) -> str:
    """Return ISO-ish date when possible; otherwise return the original cleaned value."""
    value = _clean(value)
    if not value:
        return ""

    # 2026-06-24
    m = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", value)
    if m:
        y, mo, d = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"

    # 24/06/2026 or 24-06-2026
    m = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b", value)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"

    # 24 junho 2026, 24 de junho de 2026, 24 Jun 2026
    m = re.search(
        r"\b(\d{1,2})\s+(?:de\s+)?([A-Za-zçÇãÃéÉ]+)\s+(?:de\s+)?(20\d{2})\b",
        value,
        flags=re.IGNORECASE,
    )
    if m:
        d, month_name, y = m.groups()
        mo = PT_MONTHS.get(month_name.lower().replace("ç", "c")) or PT_MONTHS.get(month_name.lower())
        if mo:
            return f"{y}-{mo}-{int(d):02d}"

    return value


def _extract_date(text: str) -> str:
    """Best-effort extraction of common PT/EU dates from surrounding text."""
    text = text or ""
    patterns = [
        r"\b20\d{2}-\d{1,2}-\d{1,2}\b",
        r"\b\d{1,2}[/-]\d{1,2}[/-]20\d{2}\b",
        r"\b\d{1,2}\s+(?:de\s+)?(?:jan(?:eiro)?|fev(?:ereiro)?|mar(?:ço|co)?|abr(?:il)?|mai(?:o)?|jun(?:ho)?|jul(?:ho)?|ago(?:sto)?|set(?:embro)?|out(?:ubro)?|nov(?:embro)?|dez(?:embro)?)\s+(?:de\s+)?20\d{2}\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            return _normalise_date(m.group(0))
    return datetime.now(timezone.utc).date().isoformat()


def _is_bad_url(url: str) -> bool:
    low = (url or "").lower()
    return any(part in low for part in JUNK_URL_PARTS)


def _strip_noise(soup: BeautifulSoup) -> BeautifulSoup:
    for selector in [
        "script", "style", "noscript", "svg", "form", "iframe", "header", "footer", "nav",
        ".cookie", ".cookies", ".breadcrumb", ".breadcrumbs", ".social", ".share", ".menu",
        "[role=navigation]", "[aria-label*=breadcrumb]",
    ]:
        for tag in soup.select(selector):
            tag.decompose()
    return soup


def _nearest_context(a: Tag) -> str:
    """Get text around a link without pulling the whole page."""
    candidate = a
    for parent in a.parents:
        if not isinstance(parent, Tag):
            continue
        name = parent.name.lower()
        cls = " ".join(parent.get("class", [])).lower()
        if name in {"article", "li"} or any(token in cls for token in ["card", "item", "result", "noticia", "destaque", "consulta", "comunicado", "listing"]):
            candidate = parent
            break
        if name in {"main", "body"}:
            break
    return _clean(candidate.get_text(" ", strip=True))


def _title_from_anchor(a: Tag, context: str = "") -> str:
    title = _clean(a.get_text(" ", strip=True))
    if len(title) >= 8:
        return title
    for attr in ["title", "aria-label"]:
        val = _clean(a.get(attr, ""))
        if len(val) >= 8:
            return val
    # Try headings nearby.
    for parent in a.parents:
        if not isinstance(parent, Tag):
            continue
        heading = parent.find(["h1", "h2", "h3", "h4"])
        if heading:
            val = _clean(heading.get_text(" ", strip=True))
            if len(val) >= 8:
                return val
    # Last resort: first sentence-like chunk of context.
    return context[:160]


def _fetch_detail(item_url: str, timeout: int = 15) -> tuple[str, str]:
    """Fetch detail page and return (summary, published). Best effort only."""
    try:
        r = SESSION.get(item_url, headers=DEFAULT_HEADERS, timeout=(DEFAULT_CONNECT_TIMEOUT, timeout))
        r.raise_for_status()
        content_type = r.headers.get("Content-Type", "").lower()
        if "pdf" in content_type or item_url.lower().endswith(".pdf"):
            return "", ""
        soup = _strip_noise(BeautifulSoup(r.text, "html.parser"))

        date = ""
        time_tag = soup.find("time")
        if time_tag:
            date = time_tag.get("datetime") or time_tag.get_text(" ", strip=True)
        if not date:
            date = _extract_date(soup.get_text(" ", strip=True)[:3000])

        main = soup.find("main") or soup.find("article") or soup.body or soup
        text = _clean(main.get_text(" ", strip=True))
        return text[:3000], _normalise_date(date) if date else ""
    except Exception as exc:
        print(f"[WARN] Detail fetch failed for {item_url}: {type(exc).__name__}: {exc}", flush=True)
        return "", ""


def _make_item(source: str, source_type: str, title: str, url: str, summary: str, published: str, parser: str | None = None) -> dict:
    return {
        "id": _id(url + title),
        "source": source,
        "source_type": source_type,
        "parser": parser or "generic",
        "title": title[:240],
        "url": url,
        "summary": summary[:3000],
        "published": published or datetime.now(timezone.utc).date().isoformat(),
    }


def fetch_rss(sources):
    """Fetch RSS/Atom feeds with explicit HTTP timeouts.

    feedparser's direct URL mode can wait indefinitely on some hosts. We download
    each feed with requests first, then pass the response bytes to feedparser.
    A failed or slow source is logged and skipped without stopping the radar.
    """
    items = []
    failures = []

    for src in sources or []:
        name = src.get("name", src.get("url", "RSS"))
        url = src["url"]
        timeout = int(src.get("timeout", DEFAULT_READ_TIMEOUT))
        started = time.monotonic()
        print(f"[SOURCE] RSS start: {name}", flush=True)

        try:
            response = SESSION.get(
                url,
                headers=DEFAULT_HEADERS,
                timeout=(DEFAULT_CONNECT_TIMEOUT, timeout),
            )
            response.raise_for_status()
            feed = feedparser.parse(response.content)

            if getattr(feed, "bozo", False) and not getattr(feed, "entries", []):
                raise ValueError(f"Invalid feed: {getattr(feed, 'bozo_exception', 'unknown parse error')}")

        except Exception as exc:
            elapsed = time.monotonic() - started
            failures.append(name)
            print(
                f"[SOURCE] RSS failed: {name} after {elapsed:.1f}s — "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )
            continue

        limit = int(src.get("limit", 30))
        source_include = _as_list(src.get("include_text_terms"))
        source_exclude = _as_list(src.get("exclude_text_terms"))
        source_count = 0

        for e in feed.entries[:limit]:
            title = _clean(getattr(e, "title", ""))
            link = _clean(getattr(e, "link", ""))
            summary = _clean(
                BeautifulSoup(
                    getattr(e, "summary", ""),
                    "html.parser",
                ).get_text(" ", strip=True)
            )
            published = getattr(e, "published", "") or getattr(e, "updated", "") or ""
            blob = f"{title} {summary} {link}"

            if not title:
                continue
            if source_include and not _matches_any(blob, source_include):
                continue
            if source_exclude and _matches_any(blob, source_exclude):
                continue

            items.append(_make_item(
                source=name,
                source_type="rss",
                title=title,
                url=link,
                summary=summary,
                published=published,
                parser="rss",
            ))
            source_count += 1

        elapsed = time.monotonic() - started
        print(
            f"[SOURCE] RSS done: {name} — {source_count} items in {elapsed:.1f}s",
            flush=True,
        )

    if failures:
        print(
            f"[WARN] RSS sources skipped ({len(failures)}): {', '.join(failures)}",
            flush=True,
        )

    return items


def fetch_http_pages(pages):
    """Fallback mode: one whole web page becomes one item. Use sparingly."""
    items = []
    for page in pages or []:
        name = page.get("name", page.get("url", "HTTP page"))
        started = time.monotonic()
        print(f"[SOURCE] HTTP start: {name}", flush=True)
        try:
            r = SESSION.get(
                page["url"],
                headers=DEFAULT_HEADERS,
                timeout=(DEFAULT_CONNECT_TIMEOUT, int(page.get("timeout", DEFAULT_READ_TIMEOUT))),
            )
            r.raise_for_status()
            soup = _strip_noise(BeautifulSoup(r.text, "html.parser"))
            text = _clean(soup.get_text(" ", strip=True))
            title = _clean(soup.title.get_text(" ", strip=True)) if soup.title else page["name"]
            items.append(_make_item(
                source=name,
                source_type="http_page",
                title=title,
                url=page["url"],
                summary=text[:2500],
                published=datetime.now(timezone.utc).date().isoformat(),
                parser="http_page",
            ))
            elapsed = time.monotonic() - started
            print(f"[SOURCE] HTTP done: {name} in {elapsed:.1f}s", flush=True)
        except Exception as exc:
            elapsed = time.monotonic() - started
            print(
                f"[SOURCE] HTTP failed: {name} after {elapsed:.1f}s — "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )
    return items


def _generic_index_items(page: dict, soup: BeautifulSoup) -> list[dict]:
    items = []
    seen_urls = set()
    name = page.get("name", page.get("url", "HTML index"))
    url = page["url"]
    base_url = page.get("base_url", url)
    limit = int(page.get("limit", 25))
    include_link_patterns = _as_list(page.get("include_link_patterns"))
    include_text_terms = _as_list(page.get("include_text_terms"))
    exclude_text_terms = _as_list(page.get("exclude_text_terms"))
    fetch_detail = bool(page.get("fetch_detail", False))

    count = 0
    for a in soup.find_all("a", href=True):
        href = a.get("href") or ""
        item_url = urljoin(base_url, href)
        if item_url in seen_urls or _is_bad_url(item_url):
            continue

        context = _nearest_context(a)
        title = _title_from_anchor(a, context)
        blob = f"{title} {context} {item_url}"

        if not title or len(title) < int(page.get("min_title_chars", 8)):
            continue
        if include_link_patterns and not any(pattern in item_url for pattern in include_link_patterns):
            continue
        if include_text_terms and not _matches_any(blob, include_text_terms):
            continue
        if exclude_text_terms and _matches_any(blob, exclude_text_terms):
            continue

        published = _extract_date(context)
        summary = context
        if fetch_detail:
            detail, detail_date = _fetch_detail(item_url, timeout=int(page.get("detail_timeout", 15)))
            if detail:
                summary = detail
            if detail_date:
                published = detail_date

        seen_urls.add(item_url)
        items.append(_make_item(name, "html_index", title, item_url, summary, published, parser=page.get("parser", "generic")))
        count += 1
        if count >= limit:
            break
    return items


def _official_link_allowed(parser: str, item_url: str) -> bool:
    """Tighter URL filtering for ERSE/DGEG/REN index pages."""
    parsed = urlparse(item_url)
    path = parsed.path.lower()
    host = parsed.netloc.lower()

    if parser == "erse":
        return "erse.pt" in host and (
            "/comunicacao/comunicados/" in path
            or "/comunicacao/destaques/" in path
            or "/atividade/consultas-publicas/" in path
            or "/biblioteca/atos-e-documentos-da-erse/" in path
        )

    if parser == "dgeg":
        return "dgeg.gov.pt" in host and (
            "/pt/destaques/" in path
            or "/pt/areas-setoriais/energia/" in path
            or "/pt/estatistica/energia/" in path
        )

    if parser == "ren_mercado":
        return "mercado.ren.pt" in host and (
            "/comunicacao/noticias/" in path
            or "/remit-iip" in path
            or "noticia_" in path
            or "/paginas/" in path
        )

    if parser == "ren_corporate":
        return "ren.pt" in host and (
            "/media/noticias" in path
            or "/noticias" in path
            or "/pt-pt/media" in path
        )

    return True


def _official_index_items(page: dict, soup: BeautifulSoup) -> list[dict]:
    """Parser for official ERSE/DGEG/REN index pages.

    Goal: one official document/news/consultation per item, not one noisy page blob.
    The selectors are deliberately broad, but URL gates are strict by source.
    """
    parser = page.get("parser", "generic")
    name = page.get("name", page.get("url", "Official index"))
    base_url = page.get("base_url", page["url"])
    include_text_terms = _as_list(page.get("include_text_terms"))
    exclude_text_terms = _as_list(page.get("exclude_text_terms"))
    limit = int(page.get("limit", 25))
    fetch_detail = bool(page.get("fetch_detail", True))

    candidates = []
    seen = set()

    # Prefer content areas; fall back to the whole stripped soup.
    roots = soup.select("main, article, .content, .container, .view-content, .listing, .list, .results") or [soup]

    for root in roots:
        for a in root.find_all("a", href=True):
            raw_href = a.get("href") or ""
            item_url = urljoin(base_url, raw_href)
            if item_url in seen or _is_bad_url(item_url):
                continue
            if not _official_link_allowed(parser, item_url):
                continue

            context = _nearest_context(a)
            title = _title_from_anchor(a, context)
            blob = f"{title} {context} {item_url}"

            # Official index pages contain lots of generic links. Be ruthless.
            if not title or len(title) < int(page.get("min_title_chars", 10)):
                continue
            if exclude_text_terms and _matches_any(blob, exclude_text_terms):
                continue
            if include_text_terms and not _matches_any(blob, include_text_terms):
                # Let explicit watch/regulatory pages through if URL is source-specific, but avoid generic corporate filler.
                if parser not in {"erse", "dgeg", "ren_mercado"}:
                    continue

            published = _extract_date(context)
            summary = context
            if fetch_detail:
                detail, detail_date = _fetch_detail(item_url, timeout=int(page.get("detail_timeout", 15)))
                if detail and len(detail) > len(summary):
                    summary = detail
                if detail_date:
                    published = detail_date

            seen.add(item_url)
            candidates.append(_make_item(name, "official_index", title, item_url, summary, published, parser=parser))
            if len(candidates) >= limit:
                break
        if len(candidates) >= limit:
            break

    return candidates


def fetch_html_indexes(indexes):
    """Extract individual news/consultation/decision links from index pages.

    Supports parser-specific handling via `parser:` in sources.yml:
    - erse
    - dgeg
    - ren_mercado
    - ren_corporate

    If no parser is specified, falls back to generic link extraction.
    """
    items = []

    for page in indexes or []:
        name = page.get("name", page.get("url", "HTML index"))
        url = page["url"]
        parser = page.get("parser", "generic")

        started = time.monotonic()
        print(f"[SOURCE] INDEX start: {name} (parser={parser})", flush=True)

        try:
            r = SESSION.get(
                url,
                headers=DEFAULT_HEADERS,
                timeout=(DEFAULT_CONNECT_TIMEOUT, int(page.get("timeout", DEFAULT_READ_TIMEOUT))),
            )
            r.raise_for_status()
            soup = _strip_noise(BeautifulSoup(r.text, "html.parser"))
        except Exception as exc:
            elapsed = time.monotonic() - started
            print(
                f"[SOURCE] INDEX failed: {name} after {elapsed:.1f}s — "
                f"{type(exc).__name__}: {exc}",
                flush=True,
            )
            continue

        if parser in {"erse", "dgeg", "ren_mercado", "ren_corporate"}:
            parsed = _official_index_items(page, soup)
        else:
            parsed = _generic_index_items(page, soup)

        elapsed = time.monotonic() - started
        print(
            f"[SOURCE] INDEX done: {name} — {len(parsed)} items in {elapsed:.1f}s "
            f"(parser={parser})",
            flush=True,
        )
        items.extend(parsed)

    return items


def filter_items(items, include, exclude):
    out, seen = [], set()
    inc = [x.lower() for x in include or []]
    exc = [x.lower() for x in exclude or []]

    for item in items or []:
        blob = f"{item.get('title','')} {item.get('summary','')} {item.get('url','')}".lower()
        if item["id"] in seen:
            continue
        if exc and any(x in blob for x in exc):
            continue
        if any(x in blob for x in inc):
            out.append(item)
            seen.add(item["id"])
    return out
