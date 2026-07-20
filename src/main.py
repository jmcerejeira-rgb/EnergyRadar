from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from time import perf_counter
from dotenv import load_dotenv

from fetch import load_yaml, fetch_rss, fetch_http_pages, fetch_html_indexes, filter_items
from classify import analyse
from report import render_html
from emailer import send_email
from persistence import load_seen, save_seen, prune_seen, filter_new_items, mark_items_seen
from watchlist import annotate_watchlist_items, sort_by_watchlist_priority, build_watchlist_prompt

ROOT = Path(__file__).resolve().parents[1]
SEEN_PATH = ROOT / "data/seen_items.json"
MAX_AGE_DAYS = int(os.getenv("MAX_NEWS_AGE_DAYS", "30"))
MAX_ITEMS_FOR_AI = int(os.getenv("MAX_ITEMS_FOR_AI", "50"))

def _parse_date(value):
    if not value: return None
    try:
        dt = parsedate_to_datetime(str(value))
        return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
    except Exception:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z","+00:00"))
            return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
        except Exception:
            return None

def _recent(item):
    dt = _parse_date(item.get("published"))
    return dt is None or dt >= datetime.now(timezone.utc)-timedelta(days=MAX_AGE_DAYS)

def _prepare(items):
    out=[]
    for i,item in enumerate(items[:MAX_ITEMS_FOR_AI],1):
        x=dict(item); x["source_id"]=i
        x["title"]=str(x.get("title",""))[:500]; x["summary"]=str(x.get("summary",""))[:1800]
        out.append(x)
    return out

def _catalog(items):
    return {int(x["source_id"]): {k:x.get(k,"") for k in ("title","source","published","url")} for x in items}

def _prompt(watchlist):
    parts=[]
    for name in ("system_context.md","daily_report.md","editorial_rules.md","scoring_rules.md","deal_patterns.md"):
        parts.append((ROOT/"prompts"/name).read_text(encoding="utf-8"))
    parts.append(build_watchlist_prompt(watchlist))
    return "\n\n".join(parts)

def main():
    start=perf_counter()
    load_dotenv(ROOT/".env")
    sources=load_yaml(str(ROOT/"config/sources.yml"))
    keywords=load_yaml(str(ROOT/"config/keywords.yml"))
    watchlist=load_yaml(str(ROOT/"config/watchlist.yml"))
    items=[]
    items += fetch_rss(sources.get("rss",[]))
    items += fetch_html_indexes(sources.get("html_indexes",[]))
    items += fetch_http_pages(sources.get("http_pages",[]))
    items=filter_items(items, keywords.get("include",[]), keywords.get("exclude",[]))
    items=[x for x in items if _recent(x)]
    items=sort_by_watchlist_priority(annotate_watchlist_items(items,watchlist))
    seen=prune_seen(load_seen(SEEN_PATH), int(os.getenv("SEEN_RETENTION_DAYS","90")))
    new_items=filter_new_items(items,seen,int(os.getenv("EDITORIAL_DEDUP_DAYS","7")))
    if not new_items and os.getenv("SEND_EMPTY_REPORTS","false").lower() not in {"1","true","yes"}:
        save_seen(SEEN_PATH,seen); print("No new items. Email not sent."); return
    prepared=_prepare(new_items)
    report=analyse(prepared,_prompt(watchlist)) if prepared else {
        "dashboard":{"setores_ativos":[],"geografias":[]},"prioridades":[],
        "opportunities":[],"market_watch":[],"regulatory_developments":[]
    }
    html=render_html(report,_catalog(prepared))
    subject=f"Infrastructure & Energy M&A Radar | Iberia | {datetime.now().strftime('%Y-%m-%d')}"
    send_email(subject,html)
    save_seen(SEEN_PATH,mark_items_seen(seen,new_items))
    print(f"Finished in {perf_counter()-start:.1f}s; analysed {len(prepared)} items.")

if __name__=="__main__":
    main()
