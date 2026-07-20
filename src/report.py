from __future__ import annotations

from datetime import datetime
from typing import Any

from jinja2 import Environment, select_autoescape


def _source_index(report: dict, catalog: dict):
    ids: list[int] = []
    sources: list[dict] = []
    mapping: dict[int, int] = {}
    by_url: dict[str, int] = {}

    for section in ("opportunities", "market_watch", "regulatory_developments"):
        for item in report.get(section, []):
            for sid in item.get("source_ids", []):
                sid_int = int(sid)
                if sid_int not in ids:
                    ids.append(sid_int)

    for sid in ids:
        src = catalog.get(int(sid), {})
        url = str(src.get("url") or "").strip()
        normalised_url = url.rstrip("/").casefold()
        if not normalised_url:
            continue

        if normalised_url in by_url:
            mapping[int(sid)] = by_url[normalised_url]
            continue

        number = len(sources) + 1
        by_url[normalised_url] = number
        mapping[int(sid)] = number
        sources.append({**src, "display_id": number})

    return sources, mapping


def _normalise_report(report: dict | None) -> dict:
    r = dict(report or {})
    r.setdefault("dashboard", {})
    r["dashboard"].setdefault("setores_ativos", [])
    r["dashboard"].setdefault("geografias", [])

    for key in (
        "prioridades",
        "opportunities",
        "market_watch",
        "regulatory_developments",
    ):
        r.setdefault(key, [])

    # Counts come from the rendered sections, never from model-written prose.
    r["counts"] = {
        "opportunities": len(r["opportunities"]),
        "market_watch": len(r["market_watch"]),
        "regulation": len(r["regulatory_developments"]),
    }

    # No commercial-priority section without a genuine opportunity.
    if not r["opportunities"]:
        r["prioridades"] = []

    return r


TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
body{font-family:Arial,sans-serif;color:#17212b;line-height:1.38;max-width:820px;margin:auto;padding:8px}
h1{font-size:21px;margin:0 0 3px}
h2{font-size:16px;margin:23px 0 9px;border-bottom:1px solid #d9e0e7;padding-bottom:5px}
.meta,.small{color:#66737f;font-size:12px}
.dashboard{background:#f3f6f8;border-radius:7px;padding:11px 13px;margin:15px 0}
.dashboard-row{margin:3px 0;font-size:13px}
.card{border:1px solid #d9e0e7;border-radius:7px;padding:11px 13px;margin-bottom:8px}
.title{font-size:14px;font-weight:bold}
.details{color:#52616f;font-size:12px;margin-top:2px}
.label{font-size:10px;text-transform:uppercase;color:#66737f;margin-top:7px;font-weight:bold}
.refs{color:#185b8d;font-size:11px}
table{border-collapse:collapse;width:100%;font-size:12px}
th,td{border-bottom:1px solid #e4e8ec;text-align:left;padding:7px;vertical-align:top}
.sources{font-size:11px;color:#52616f;padding-left:21px}
.sources li{margin-bottom:7px}
.empty{font-style:italic;color:#66737f;font-size:13px}
a{color:#185b8d}
</style>
</head>
<body>
<h1>Infrastructure &amp; Energy M&amp;A Radar | Iberia</h1>
<div class="meta">{{ date }} · Briefing diário de originação</div>

<div class="dashboard">
<div class="dashboard-row"><b>Oportunidades acionáveis:</b> {{ r.counts.opportunities }}</div>
<div class="dashboard-row"><b>Monitorização:</b> {{ r.counts.market_watch }}</div>
<div class="dashboard-row"><b>Regulação:</b> {{ r.counts.regulation }}</div>
<div class="dashboard-row"><b>Setores:</b> {{ r.dashboard.setores_ativos|join(', ') or '—' }}</div>
<div class="dashboard-row"><b>Geografias:</b> {{ r.dashboard.geografias|join(', ') or '—' }}</div>
</div>

{% if r.prioridades %}
<h2>Prioridades de hoje</h2>
<table>
<tr><th>Prioridade</th><th>Empresa/ativo</th><th>Tipo</th><th>Ação</th></tr>
{% for p in r.prioridades %}
<tr><td>{{ p.prioridade }}</td><td>{{ p.empresa }}</td><td>{{ p.tipo }}</td><td>{{ p.acao }}</td></tr>
{% endfor %}
</table>
{% endif %}

<h2>Oportunidades</h2>
{% for o in r.opportunities %}
<div class="card">
<div class="title">{{ o.empresa }} — {{ o.pais }} <span class="refs">{{ o.source_ids|refs }}</span></div>
<div class="details">{{ o.tipo }} · Deal Score {{ o.deal_score }}/100 · Confiança: {{ o.confianca }}</div>
<div class="label">Porque interessa</div>
<div>{{ o.porque_interessa }}</div>
<div class="label">Próximo passo</div>
<div>{{ o.proximo_passo }}</div>
</div>
{% else %}
<p class="empty">Nenhuma oportunidade acionável identificada.</p>
{% endfor %}

{% if r.market_watch %}
<h2>Monitorização</h2>
{% for m in r.market_watch %}
<div class="card">
<div class="title">{{ m.titulo }} — {{ m.pais }} <span class="refs">{{ m.source_ids|refs }}</span></div>
<div>{{ m.resumo }}</div>
</div>
{% endfor %}
{% endif %}

{% if r.regulatory_developments %}
<h2>Regulação</h2>
{% for d in r.regulatory_developments %}
<div class="card">
<div class="title">{{ d.tema }} — {{ d.pais }} <span class="refs">{{ d.source_ids|refs }}</span></div>
<div>{{ d.resumo }}</div>
</div>
{% endfor %}
{% endif %}

{% if sources %}
<h2>Fontes</h2>
<ol class="sources">
{% for s in sources %}
<li value="{{ s.display_id }}">
<b>{{ s.source or 'Fonte' }}</b>{% if s.published %} — {{ s.published }}{% endif %}<br>
{{ s.title }} — <a href="{{ s.url }}">abrir fonte</a>
</li>
{% endfor %}
</ol>
{% endif %}
</body>
</html>"""


def render_html(report: dict, catalog: dict | None = None) -> str:
    r = _normalise_report(report)
    sources, mapping = _source_index(r, catalog or {})

    def refs(values: Any) -> str:
        output: list[str] = []
        for value in values or []:
            sid = int(value)
            if sid in mapping:
                output.append(f"[{mapping[sid]}]")
        return " ".join(output)

    env = Environment(autoescape=select_autoescape(default=True))
    env.filters["refs"] = refs
    return env.from_string(TEMPLATE).render(
        r=r,
        sources=sources,
        date=datetime.now().strftime("%Y-%m-%d"),
    )
