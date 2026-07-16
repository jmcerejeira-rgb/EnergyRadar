from __future__ import annotations

from datetime import datetime
from typing import Any

from jinja2 import Environment, select_autoescape


def _fmt(value: Any, fallback: str = "-") -> str:
    """Return a safe display string for empty/missing values."""
    if value is None:
        return fallback
    if isinstance(value, str):
        value = value.strip()
        return value if value else fallback
    return str(value)


def _fmt_list(value: Any, fallback: str = "-") -> str:
    """Render list-like fields such as buyers/investors."""
    if not value:
        return fallback
    if isinstance(value, list):
        cleaned = [_fmt(v, "") for v in value]
        cleaned = [v for v in cleaned if v]
        return ", ".join(cleaned) if cleaned else fallback
    return _fmt(value, fallback)


def _score_label(value: Any) -> str:
    try:
        score = int(value)
    except Exception:
        return "-"

    labels = {
        5: "5 / Acionável",
        4: "4 / Forte",
        3: "3 / Monitorizar",
        2: "2 / Baixa prioridade",
        1: "1 / Irrelevante",
    }
    return labels.get(score, str(score))


TEMPLATE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body { font-family: Arial, Helvetica, sans-serif; color: #1f2933; line-height: 1.35; }
    h2 { margin-bottom: 4px; }
    h3 { margin-top: 26px; margin-bottom: 8px; }
    p.meta { color: #697386; margin-top: 0; }
    .summary { background: #f4f6f8; border-left: 4px solid #697386; padding: 12px; margin: 14px 0 18px 0; }
    .kpis { margin: 12px 0 20px 0; }
    .kpi { display: inline-block; padding: 6px 10px; background: #eef2f7; margin-right: 8px; border-radius: 4px; }
    table { border-collapse: collapse; width: 100%; margin-bottom: 18px; }
    th { background: #eef2f7; text-align: left; font-weight: bold; }
    th, td { border: 1px solid #d8dee9; padding: 7px; vertical-align: top; }
    td.small, th.small { width: 7%; }
    td.medium, th.medium { width: 13%; }
    .muted { color: #697386; }
    .empty { color: #697386; font-style: italic; }
    ul { margin-top: 6px; }
  </style>
</head>
<body>

<h2>Energy M&A Deal Radar | Portugal | {{ date }}</h2>
<p class="meta">Relatório automático de originação. Usar como triagem; confirmar sempre nas fontes originais.</p>

<div class="summary">
  <b>Resumo executivo:</b><br>
  {{ r.executive_summary | fmt }}
</div>

<div class="kpis">
  <span class="kpi"><b>{{ r.opportunities | length }}</b> oportunidades M&A</span>
  <span class="kpi"><b>{{ r.regulatory_developments | length }}</b> desenvolvimentos regulatórios</span>
  <span class="kpi"><b>{{ r.market_watch | length }}</b> notícias para monitorizar</span>
  <span class="kpi"><b>{{ r.watchlist_hits | default([]) | length }}</b> watchlist hits</span>
  <span class="kpi"><b>{{ r.critical_alerts | length }}</b> alertas críticos</span>
</div>

{% if r.top_weekly_opportunities %}
<h3>Top oportunidades da semana</h3>
<ul>
{% for t in r.top_weekly_opportunities %}
  <li>{{ t | fmt }}</li>
{% endfor %}
</ul>
{% endif %}

{% if r.critical_alerts %}
<h3>Alertas críticos</h3>
<ul>
{% for a in r.critical_alerts %}
  <li>{{ a | fmt }}</li>
{% endfor %}
</ul>
{% endif %}

{% if r.watchlist_hits %}
<h3>Watchlist hits</h3>
<table>
<tr>
  <th>Título</th>
  <th class="medium">Fonte</th>
  <th class="medium">Data</th>
  <th class="medium">Empresas</th>
  <th class="medium">Compradores / investidores</th>
  <th class="small">Link</th>
</tr>
{% for h in r.watchlist_hits %}
<tr>
  <td>{{ h.title | fmt }}</td>
  <td>{{ h.source | fmt }}</td>
  <td>{{ h.published | fmt }}</td>
  <td>{{ h.companies | fmt }}</td>
  <td>{{ h.buyers_investors | fmt }}</td>
  <td>
    {% if h.url %}<a href="{{ h.url }}">Abrir</a>{% else %}<span class="muted">Sem link</span>{% endif %}
  </td>
</tr>
{% endfor %}
</table>
{% endif %}

<h3>Oportunidades M&A</h3>
{% if r.opportunities %}
<table>
<tr>
  <th>Empresa</th>
  <th class="small">País</th>
  <th class="medium">Setor</th>
  <th>Descrição</th>
  <th>Sinal observado</th>
  <th>Ângulo M&A</th>
  <th>Compradores / investidores</th>
  <th class="medium">Fonte / data</th>
  <th class="small">Score</th>
  <th>Próximo passo</th>
  <th class="small">Link</th>
</tr>
{% for o in r.opportunities %}
<tr>
  <td>{{ o.empresa | fmt }}</td>
  <td>{{ o.pais | fmt }}</td>
  <td>{{ o.setor | fmt }}</td>
  <td>{{ o.descricao_2_linhas | fmt }}</td>
  <td>{{ o.sinal_observado | fmt }}</td>
  <td>{{ o.angulo_ma | fmt }}</td>
  <td>{{ o.potenciais_compradores_investidores | fmt_list }}</td>
  <td>{{ o.fonte_data | fmt }}</td>
  <td>{{ o.score | score_label }}</td>
  <td>{{ o.proximo_passo | fmt }}</td>
  <td>
    {% if o.url %}<a href="{{ o.url }}">Fonte</a>{% else %}<span class="muted">Sem link</span>{% endif %}
  </td>
</tr>
{% endfor %}
</table>
{% else %}
<p class="empty">Sem oportunidades M&A acionáveis neste lote.</p>
{% endif %}


<h3>Notícias relevantes para monitorizar</h3>
{% if r.market_watch %}
<table>
<tr>
  <th>Título</th>
  <th class="medium">Categoria</th>
  <th>Motivo de relevância</th>
  <th>Porque não é lead M&A</th>
  <th class="medium">Fonte / data</th>
  <th class="small">Score</th>
  <th class="small">Link</th>
</tr>
{% for m in r.market_watch %}
<tr>
  <td>{{ m.titulo | fmt }}</td>
  <td>{{ m.categoria | fmt }}</td>
  <td>{{ m.motivo_relevancia | fmt }}</td>
  <td>{{ m.porque_nao_e_lead_ma | fmt }}</td>
  <td>{{ m.fonte_data | fmt }}</td>
  <td>{{ m.score | score_label }}</td>
  <td>
    {% if m.url %}<a href="{{ m.url }}">Fonte</a>{% else %}<span class="muted">Sem link</span>{% endif %}
  </td>
</tr>
{% endfor %}
</table>
{% else %}
<p class="empty">Sem notícias de mercado/regulação para monitorização adicional.</p>
{% endif %}

<h3>Desenvolvimentos regulatórios</h3>
{% if r.regulatory_developments %}
<table>
<tr>
  <th>Tema</th>
  <th>Desenvolvimento</th>
  <th>Impacto esperado</th>
  <th>Implicação M&A</th>
  <th class="medium">Fonte / data</th>
  <th class="small">Score</th>
  <th class="small">Link</th>
</tr>
{% for d in r.regulatory_developments %}
<tr>
  <td>{{ d.tema | fmt }}</td>
  <td>{{ d.desenvolvimento | fmt }}</td>
  <td>{{ d.impacto_esperado | fmt }}</td>
  <td>{{ d.implicacao_ma | fmt }}</td>
  <td>{{ d.fonte_data | fmt }}</td>
  <td>{{ d.score | score_label }}</td>
  <td>
    {% if d.url %}<a href="{{ d.url }}">Fonte</a>{% else %}<span class="muted">Sem link</span>{% endif %}
  </td>
</tr>
{% endfor %}
</table>
{% else %}
<p class="empty">Sem desenvolvimentos regulatórios relevantes neste lote.</p>
{% endif %}

</body>
</html>
"""


def render_html(report: dict) -> str:
    # Make optional sections safe even when older classify.py output is used.
    report = dict(report or {})
    report.setdefault("executive_summary", "")
    report.setdefault("opportunities", [])
    report.setdefault("regulatory_developments", [])
    report.setdefault("market_watch", [])
    report.setdefault("critical_alerts", [])
    report.setdefault("top_weekly_opportunities", [])
    report.setdefault("watchlist_hits", [])

    env = Environment(autoescape=select_autoescape(default=True))
    env.filters["fmt"] = _fmt
    env.filters["fmt_list"] = _fmt_list
    env.filters["score_label"] = _score_label

    template = env.from_string(TEMPLATE)
    return template.render(
        r=report,
        date=datetime.now().strftime("%Y-%m-%d"),
    )
