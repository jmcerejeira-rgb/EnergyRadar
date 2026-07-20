from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from time import perf_counter
from pathlib import Path

from dotenv import load_dotenv

from fetch import load_yaml, fetch_rss, fetch_http_pages, fetch_html_indexes, filter_items
from classify import analyse
from report import render_html
from emailer import send_email
from persistence import load_seen, save_seen, prune_seen, filter_new_items, mark_items_seen
from watchlist import annotate_watchlist_items, sort_by_watchlist_priority, build_watchlist_prompt
from triage import annotate_triage, sort_by_triage_priority, triage_counts, build_triage_prompt

ROOT = Path(__file__).resolve().parents[1]
SEEN_PATH = ROOT / "data" / "seen_items.json"
MAX_AGE_DAYS = int(os.getenv("MAX_NEWS_AGE_DAYS", "30"))
MAX_ITEMS_FOR_AI = int(os.getenv("MAX_ITEMS_FOR_AI", "40"))


def _parse_date(value):
    if not value:
        return None
    text = str(value).strip()
    try:
        dt = parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    clean = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _is_recent(item, max_age_days=MAX_AGE_DAYS):
    dt = _parse_date(item.get("published"))
    if dt is None:
        # Keep undated items, but the model is instructed to be conservative.
        return True
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    return dt >= cutoff


def _prepare_for_ai(items):
    prepared = []
    for source_id, item in enumerate(items[:MAX_ITEMS_FOR_AI], start=1):
        clean = dict(item)
        clean["source_id"] = source_id
        clean["summary"] = str(clean.get("summary", ""))[:1800]
        clean["title"] = str(clean.get("title", ""))[:500]
        prepared.append(clean)
    return prepared


def _source_catalog(items):
    catalog = {}
    for item in items:
        sid = int(item["source_id"])
        catalog[sid] = {
            "source_id": sid,
            "title": item.get("title", ""),
            "source": item.get("source", ""),
            "published": item.get("published", ""),
            "url": item.get("url", ""),
        }
    return catalog


def main():
    started_at = perf_counter()
    print("[STEP 1/6] Loading configuration...", flush=True)
    load_dotenv(ROOT / ".env")

    sources = load_yaml(str(ROOT / "config/sources.yml"))
    keywords = load_yaml(str(ROOT / "config/keywords.yml"))
    watchlist = load_yaml(str(ROOT / "config/watchlist.yml"))
    base_prompt = (ROOT / "prompts/daily_report.md").read_text(encoding="utf-8")
    prompt = base_prompt + "\n\n" + build_watchlist_prompt(watchlist) + "\n\n" + build_triage_prompt()

    print("[STEP 2/6] Fetching and filtering sources...", flush=True)
    items = []
    items += fetch_rss(sources.get("rss", []))
    items += fetch_html_indexes(sources.get("html_indexes", []))
    items += fetch_http_pages(sources.get("http_pages", []))
    items = filter_items(items, keywords.get("include", []), keywords.get("exclude", []))
    items = [item for item in items if _is_recent(item)]
    items = annotate_watchlist_items(items, watchlist)
    items = sort_by_watchlist_priority(items)
    items = annotate_triage(items)
    items = sort_by_triage_priority(items)

    print("[STEP 3/6] Loading seen-items history...", flush=True)
    seen = prune_seen(load_seen(SEEN_PATH), days=int(os.getenv("SEEN_RETENTION_DAYS", "90")))
    new_items = filter_new_items(items, seen)

    print(f"Fetched relevant recent items: {len(items)}", flush=True)
    print(f"Already seen items: {len(items) - len(new_items)}", flush=True)
    print(f"New items: {len(new_items)}", flush=True)
    print("Triage counts:", triage_counts(new_items), flush=True)

    if not new_items:
        if os.getenv("SEND_EMPTY_REPORTS", "false").lower() not in {"1", "true", "yes"}:
            save_seen(SEEN_PATH, seen)
            print("No new items. Email not sent.", flush=True)
            return
        report = {
            "today_in_30_seconds": ["Sem notícias novas face ao histórico."],
            "executive_summary": "Sem novidades materiais.",
            "banker_actions": [],
            "opportunities": [],
            "market_watch": [],
            "regulatory_developments": [],
        }
        catalog = {}
    else:
        ai_items = _prepare_for_ai(new_items)
        catalog = _source_catalog(ai_items)
        print(f"[STEP 4/6] Analysing {len(ai_items)} items with OpenAI...", flush=True)
        report = analyse(ai_items, prompt)

    print("[STEP 5/6] Rendering and sending email...", flush=True)
    html = render_html(report, catalog)
    subject = f"Energy M&A Radar | Portugal | {datetime.now().strftime('%Y-%m-%d')}"
    send_email(subject, html)

    seen = mark_items_seen(seen, new_items)
    save_seen(SEEN_PATH, seen)
    print(f"Seen database updated: {SEEN_PATH}", flush=True)
    print(f"[STEP 6/6] Finished in {perf_counter() - started_at:.1f}s", flush=True)


if __name__ == "__main__":
    main()
