from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any

from jinja2 import Environment, select_autoescape


def _fmt(value: Any, fallback: str = "-") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _score(value: Any) -> str:
    labels = {5: "Acionável", 4: "Forte", 3: "Monitorizar", 2: "Baixa prioridade"}
    try:
        number = int(value)
    except Exception:
        return "-"
    return f"{number}/5 — {labels.get(number, '')}".strip(" —")


def _source_index(report: dict, catalog: dict) -> tuple[list[dict], dict[int, int]]:
    """Build a compact, consecutive source list and collapse duplicate URLs."""
    ordered_ids: list[int] = []
    for section in ("opportunities", "market_watch", "regulatory_developments"):
        for item in report.get(section, []):
            for sid in item.get("source_ids", []):
                try:
                    sid = int(sid)
                except Exception:
                    continue
                if sid not in ordered_ids:
                    ordered_ids.append(sid)

    sources: list[dict] = []
    source_map: dict[int, int] = {}
    url_to_display: dict[str, int] = {}

    for sid in ordered_ids:
        source = catalog.get(sid) or {}
        url = str(source.get("url") or "").strip()
        if not url:
            continue
        normalized = url.rstrip("/").lower()
        if normalized in url_to_display:
            source_map[sid] = url_to_display[normalized]
            continue

        display_id = len(sources) + 1
        url_to_display[normalized] = display_id
        source_map[sid] = display_id
        entry = dict(source)
        entry["display_id"] = display_id
        sources.append(entry)

    return sources, source_map


TEMPLATE = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
body { font-family: Arial, Helvetica, sans-serif; color:#17212b; line-height:1.45; max-width:820px; margin:auto; }
h2 { margin-bottom:3px; }
h3 { margin:24px 0 10px; border-bottom:1px solid #d9e0e7; padding-bottom:5px; }
.meta { color:#66737f; font-size:12px; }
.hero { background:#f3f6f8; padding:14px 18px; margin:16px 0; border-radius:6px; }
.action { background:#fff8e6; padding:12px 16px; border-left:4px solid #c58b00; margin:14px 0; }
.card { border:1px solid #d9e0e7; border-radius:6px; padding:13px 15px; margin-bottom:10px; }
.title { font-size:16px; font-weight:bold; }
.label { color:#66737f; font-size:12px; text-transform:uppercase; letter-spacing:.04em; margin-top:8px; }
.refs { color:#3b668c; font-weight:bold; white-space:nowrap; }
.score { font-size:12px; color:#52616f; }
.empty { color:#66737f; font-style:italic; }
.sources { font-size:12px; color:#52616f; }
.sources li { margin-bottom:7px; }
a { color:#185b8d; }
ul { padding-left:20px; }
</style>
</head>
<body>
<h2>Energy M&A Radar | Portugal | {{ date }}</h2>
<p class="meta">Leitura diária de originação. Informação sujeita a confirmação nas fontes originais.</p>

<div class="hero">
<b>Hoje em 30 segundos</b>
<ul>
{% for bullet in r.today_in_30_seconds %}<li>{{ bullet }}</li>{% endfor %}
</ul>
{% if r.executive_summary %}<div>{{ r.executive_summary }}</div>{% endif %}
</div>

<div class="action">
<b>O que faria hoje</b>
{% if r.banker_actions %}
<ul>{% for action in r.banker_actions %}<li>{{ action }}</li>{% endfor %}</ul>
{% else %}
<div>Hoje não identifiquei nenhuma ação comercial prioritária.</div>
{% endif %}
</div>

<h3>Oportunidades M&A</h3>
{% for o in r.opportunities %}
<div class="card">
<div class="title">{{ o.empresa }} — {{ o.setor }} <span class="refs">{{ o.source_ids | refs }}</span></div>
<div class="score">{{ o.pais }} | {{ o.score | score }}</div>
<div class="label">O que aconteceu</div><div>{{ o.descricao }}</div>
<div class="label">Trigger</div><div>{{ o.trigger }}</div>
<div class="label">Ângulo M&A</div><div>{{ o.angulo_ma }}</div>
<div class="label">Próximo passo</div><div>{{ o.proximo_passo }}</div>
</div>
{% else %}<p class="empty">Sem oportunidades M&A acionáveis.</p>{% endfor %}

<h3>Notícias que merecem leitura</h3>
{% for m in r.market_watch %}
<div class="card">
<div class="title">{{ m.titulo }} <span class="refs">{{ m.source_ids | refs }}</span></div>
<div class="score">{{ m.score | score }}</div>
<div class="label">Porque importa</div><div>{{ m.porque_importa }}</div>
<div class="label">Leitura M&A</div><div>{{ m.leitura_ma }}</div>
{% if m.acao %}<div class="label">Ação</div><div>{{ m.acao }}</div>{% endif %}
</div>
{% else %}<p class="empty">Sem notícias adicionais que justifiquem leitura.</p>{% endfor %}

<h3>Regulação material</h3>
{% for d in r.regulatory_developments %}
<div class="card">
<div class="title">{{ d.tema }} <span class="refs">{{ d.source_ids | refs }}</span></div>
<div class="score">{{ d.score | score }}</div>
<div class="label">Desenvolvimento</div><div>{{ d.desenvolvimento }}</div>
<div class="label">Impacto</div><div>{{ d.impacto }}</div>
<div class="label">Potencial impacto em ativos</div><div>{{ d.implicacao_ma }}</div>
</div>
{% else %}<p class="empty">Sem alterações regulatórias materiais.</p>{% endfor %}

{% if sources %}
<h3>Fontes</h3>
<ol class="sources">
{% for s in sources %}
<li value="{{ s.display_id }}">
<b>{{ s.source }}</b>{% if s.published %} — {{ s.published }}{% endif %}<br>
{{ s.title }} — <a href="{{ s.url }}">abrir fonte</a>
</li>
{% endfor %}
</ol>
{% endif %}
</body>
</html>
"""


def render_html(report: dict, catalog: dict | None = None) -> str:
    report = dict(report or {})
    for key in (
        "today_in_30_seconds", "banker_actions", "opportunities",
        "market_watch", "regulatory_developments",
    ):
        report.setdefault(key, [])
    report.setdefault("executive_summary", "")

    catalog = catalog or {}
    sources, source_map = _source_index(report, catalog)

    def refs_filter(source_ids) -> str:
        refs = []
        seen = set()
        for sid in source_ids or []:
            try:
                display_id = source_map.get(int(sid))
            except Exception:
                continue
            if display_id and display_id not in seen:
                refs.append(f"[{display_id}]")
                seen.add(display_id)
        return " ".join(refs)

    env = Environment(autoescape=select_autoescape(default=True))
    env.filters["fmt"] = _fmt
    env.filters["score"] = _score
    env.filters["refs"] = refs_filter

    return env.from_string(TEMPLATE).render(
        r=report,
        sources=sources,
        date=datetime.now().strftime("%Y-%m-%d"),
    )
