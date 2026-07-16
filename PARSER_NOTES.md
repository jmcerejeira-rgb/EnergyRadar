# ERSE / DGEG / REN parsers

This version adds source-specific parsers inside `src/fetch.py`.

## What changed

The previous `fetch_html_indexes()` treated official pages as generic lists of links. That worked, but official portals include menus, cookie links, navigation and duplicate links, so the feed was noisy.

The new version supports a `parser:` key in `config/sources.yml`:

```yaml
parser: erse
parser: dgeg
parser: ren_mercado
parser: ren_corporate
```

When one of these parsers is set, the scraper applies stricter URL gates and extracts one item per official article/document/consultation.

## Fields extracted

Each parsed item includes:

- `title`
- `url`
- `summary`
- `published`
- `source`
- `source_type`
- `parser`

For official pages, `source_type` becomes:

```text
official_index
```

## Detail fetching

For official pages, `fetch_detail: true` makes the script open each detail page and use the article/body text as a better summary.

This improves the OpenAI analysis, but it is slower. If runs are too slow, set:

```yaml
fetch_detail: false
```

on the relevant source.

## Caveat

These are robust best-effort parsers, not guaranteed APIs. ERSE/DGEG/REN can change page structures without notice. The code keeps a generic fallback path, but official data should eventually be pulled through APIs/endpoints where available.
