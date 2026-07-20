from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from fetch import load_yaml, fetch_rss, fetch_http_pages, fetch_html_indexes, filter_items
from classify import analyse
from report import render_html
from emailer import send_email
from persistence import load_seen, save_seen, prune_seen, filter_new_items, mark_items_seen
from watchlist import (
    annotate_watchlist_items,
    sort_by_watchlist_priority,
    build_watchlist_prompt,
    build_watchlist_hits_for_report,
)
from triage import annotate_triage, sort_by_triage_priority, triage_counts, build_triage_prompt

ROOT = Path(__file__).resolve().parents[1]
SEEN_PATH = ROOT / "data" / "seen_items.json"


def main():
    if load_dotenv:
        load_dotenv(ROOT / ".env")

    sources = load_yaml(str(ROOT / "config/sources.yml"))
    keywords = load_yaml(str(ROOT / "config/keywords.yml"))
    watchlist = load_yaml(str(ROOT / "config/watchlist.yml"))
    base_prompt = (ROOT / "prompts/daily_report.md").read_text(encoding="utf-8")
    prompt = base_prompt + "\n\n" + build_watchlist_prompt(watchlist) + "\n\n" + build_triage_prompt()

    items = []
    items += fetch_rss(sources.get("rss", []))
    items += fetch_html_indexes(sources.get("html_indexes", []))
    items += fetch_http_pages(sources.get("http_pages", []))
    items = filter_items(items, keywords.get("include", []), keywords.get("exclude", []))
    items = annotate_watchlist_items(items, watchlist)
    items = sort_by_watchlist_priority(items)
    items = annotate_triage(items)
    items = sort_by_triage_priority(items)

    seen = prune_seen(load_seen(SEEN_PATH), days=int(os.getenv("SEEN_RETENTION_DAYS", "90")))
    new_items = filter_new_items(items, seen)

    print(f"Fetched relevant items: {len(items)}")
    print(f"Already seen items: {len(items) - len(new_items)}")
    watchlist_hits_count = sum(1 for item in new_items if item.get("watchlist_hits"))
    counts = triage_counts(new_items)

    print(f"New items: {len(new_items)}")
    print(f"Watchlist hits in new items: {watchlist_hits_count}")
    print("Triage counts:", counts)

    if not new_items:
        if os.getenv("SEND_EMPTY_REPORTS", "false").lower() not in {"1", "true", "yes"}:
            save_seen(SEEN_PATH, seen)
            print("No new items. Email not sent.")
            return

        report = {
            "executive_summary": "Sem notícias novas face ao histórico local.",
            "opportunities": [],
            "regulatory_developments": [],
            "market_watch": [],
            "critical_alerts": [],
            "top_weekly_opportunities": [],
            "watchlist_hits": []
        }
    else:
        report = analyse(new_items, prompt)
        report["watchlist_hits"] = build_watchlist_hits_for_report(new_items)

    html = render_html(report)
    subject = f"Energy M&A Deal Radar | Portugal | {datetime.now().strftime('%Y-%m-%d')}"
    send_email(subject, html)

    seen = mark_items_seen(seen, new_items)
    save_seen(SEEN_PATH, seen)
    print(f"Seen database updated: {SEEN_PATH}")


if __name__ == "__main__":
    main()
