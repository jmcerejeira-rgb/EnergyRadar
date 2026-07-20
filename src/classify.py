from __future__ import annotations

import json
import os
import re
from typing import Any

from openai import OpenAI

SCHEMA = {
  "type": "object",
  "additionalProperties": False,
  "properties": {
    "executive_summary": {"type": "string"},

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "dashboard": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "setores_ativos": {
                    "type": "array",
                    "maxItems": 5,
                    "items": {"type": "string"},
                },
                "geografias": {
                    "type": "array",
                    "maxItems": 4,
                    "items": {"type": "string"},
                },
            },
            "required": ["setores_ativos", "geografias"],
        },
        "prioridades": {
            "type": "array",
            "maxItems": 7,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "prioridade": {
                        "type": "string",
                        "enum": ["Alta", "Média", "Baixa"],
                    },
                    "empresa": {"type": "string"},
                    "tipo": {"type": "string"},
                    "acao": {"type": "string"},
                    "source_ids": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 2,
                        "items": {"type": "integer", "minimum": 1},
                    },
                },
                "required": [
                    "prioridade",
                    "empresa",
                    "tipo",
                    "acao",
                    "source_ids",
                ],
            },
        },
        "opportunities": {
            "type": "array",
            "maxItems": 7,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "empresa": {"type": "string"},
                    "pais": {"type": "string"},
                    "tipo": {"type": "string"},
                    "deal_score": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100,
                    },
                    "confianca": {
                        "type": "string",
                        "enum": ["Alta", "Média", "Baixa"],
                    },
                    "porque_interessa": {"type": "string"},
                    "proximo_passo": {"type": "string"},
                    "source_ids": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 2,
                        "items": {"type": "integer", "minimum": 1},
                    },
                },
                "required": [
                    "empresa",
                    "pais",
                    "tipo",
                    "deal_score",
                    "confianca",
                    "porque_interessa",
                    "proximo_passo",
                    "source_ids",
                ],
            },
        },
        "market_watch": {
            "type": "array",
            "maxItems": 7,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "titulo": {"type": "string"},
                    "pais": {"type": "string"},
                    "resumo": {"type": "string"},
                    "source_ids": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 1,
                        "items": {"type": "integer", "minimum": 1},
                    },
                },
                "required": ["titulo", "pais", "resumo", "source_ids"],
            },
        },
        "regulatory_developments": {
            "type": "array",
            "maxItems": 7,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "tema": {"type": "string"},
                    "pais": {"type": "string"},
                    "resumo": {"type": "string"},
                    "source_ids": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 1,
                        "items": {"type": "integer", "minimum": 1},
                    },
                },
                "required": ["tema", "pais", "resumo", "source_ids"],
            },
        },
    },
    "required": [
        "dashboard",
        "prioridades",
        "opportunities",
        "market_watch",
        "regulatory_developments",
    ],
}


VAGUE_ACTIONS = (
    "explorar oportunidades",
    "avaliar potenciais",
    "monitorizar evolução",
    "monitorizar o mercado",
    "acompanhar o mercado",
    "contactar investidores",
    "contactar utilities",
    "analisar mercado",
    "manter acompanhamento",
)

SPECULATIVE_PHRASES = (
    "pode representar",
    "poderá representar",
    "pode gerar",
    "poderá gerar",
    "potencial mandato",
    "possível oportunidade",
    "possivelmente",
    "potencialmente",
)

NO_TRIGGER_SIGNALS = (
    "ppa",
    "acordo comercial",
    "parceria estratégica",
    "inauguração",
    "entrada em operação",
    "concluída",
    "concluído",
    "consulta pública",
    "licenciamento",
    "apoio público",
    "subvenção",
    "tarifa",
    "plano nacional",
)

STRONG_TRIGGER_SIGNALS = (
    "venda",
    "alienação",
    "processo competitivo",
    "revisão estratégica",
    "procura de investidor",
    "procura de parceiro",
    "refinanciamento",
    "recapitalização",
    "aumento de capital",
    "carve-out",
    "saída de sponsor",
    "distress",
    "assessor",
    "mandato",
)


def _trim_words(text: Any, limit: int) -> str:
    words = str(text or "").split()
    return " ".join(words[:limit]).strip()


def _normalise_sentence(text: Any) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    return value


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(phrase in lowered for phrase in phrases)


def _dedupe_by_source(items: list[dict]) -> list[dict]:
    output: list[dict] = []
    seen: set[tuple[int, ...]] = set()
    for item in items:
        key = tuple(sorted(int(x) for x in item.get("source_ids", []) if str(x).isdigit()))
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        output.append(item)
    return output



IBERIAN_GEOGRAPHIES = (
    "portugal",
    "espanha",
    "spain",
    "ibéria",
    "iberia",
    "península ibérica",
    "portugal/espanha",
    "espanha/portugal",
)

DIRECT_PORTUGAL_LINK_GEOGRAPHIES = (
    "marrocos",
    "morocco",
)

NON_IBERIAN_GEOGRAPHIES = (
    "emirados árabes unidos",
    "united arab emirates",
    "uae",
    "dubai",
    "abu dhabi",
    "estados unidos",
    "united states",
    "china",
    "índia",
    "india",
    "austrália",
    "australia",
)

PORTUGUESE_REPLACEMENTS = {
    "projecto": "projeto",
    "projectos": "projetos",
    "actividade": "atividade",
    "actividades": "atividades",
    "transaccional": "transacional",
    "transaccionais": "transacionais",
    "activo": "ativo",
    "activos": "ativos",
    "eléctrico": "elétrico",
    "eléctrica": "elétrica",
    "electrificação": "eletrificação",
    "interconexão": "interligação",
}


def _pt_pt(text: Any) -> str:
    value = _normalise_sentence(text)
    for old, new in PORTUGUESE_REPLACEMENTS.items():
        value = re.sub(rf"\b{re.escape(old)}\b", new, value, flags=re.IGNORECASE)
    return value


def _is_geographically_relevant(item: dict) -> bool:
    geography = " ".join(
        [
            str(item.get("pais", "")),
            str(item.get("titulo", "")),
            str(item.get("tema", "")),
            str(item.get("resumo", "")),
            str(item.get("empresa", "")),
            str(item.get("porque_interessa", "")),
        ]
    ).casefold()

    if any(token in geography for token in NON_IBERIAN_GEOGRAPHIES):
        return False

    if any(token in geography for token in IBERIAN_GEOGRAPHIES):
        return True

    # Morocco is accepted only when Portugal is explicitly part of the same item.
    if any(token in geography for token in DIRECT_PORTUGAL_LINK_GEOGRAPHIES):
        return "portugal" in geography

    # EU-wide regulation may remain only in the regulatory section.
    return "união europeia" in geography or "european union" in geography or geography.strip() == "ue"

    "market_watch": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
          "titulo": {"type": "string"},
          "categoria": {"type": "string"},
          "motivo_relevancia": {"type": "string"},
          "porque_nao_e_lead_ma": {"type": "string"},
          "fonte_data": {"type": "string"},
          "url": {"type": "string"},
          "score": {"type": "integer", "minimum": 1, "maximum": 5}
        },
        "required": [
          "titulo",
          "categoria",
          "motivo_relevancia",
          "porque_nao_e_lead_ma",
          "fonte_data",
          "url",
          "score"
        ]
      }
    },

    "critical_alerts": {
      "type": "array",
      "items": {"type": "string"}
    },

    "top_weekly_opportunities": {
      "type": "array",
      "items": {"type": "string"}
    }
  },
  "required": [
    "executive_summary",
    "opportunities",
    "regulatory_developments",
    "market_watch",
    "critical_alerts",
    "top_weekly_opportunities"
  ]
}

def _is_eu_policy_item(item: dict) -> bool:
    text = " ".join(
        [
            str(item.get("titulo", "")),
            str(item.get("tema", "")),
            str(item.get("resumo", "")),
            str(item.get("pais", "")),
        ]
    ).casefold()
    policy_terms = (
        "action plan",
        "plano de ação",
        "meta de",
        "diretiva",
        "regulamento",
        "comissão europeia",
        "união europeia",
    )
    return any(term in text for term in policy_terms)


def _clean(report: dict) -> dict:
    r = dict(report or {})
    r.setdefault("dashboard", {"setores_ativos": [], "geografias": []})

    opportunities = [
        item for item in _dedupe_by_source(list(r.get("opportunities") or []))
        if _is_geographically_relevant(item)
    ][:7]
    market_watch_raw = [
        item for item in _dedupe_by_source(list(r.get("market_watch") or []))
        if _is_geographically_relevant(item)
    ]
    regulation = [
        item for item in _dedupe_by_source(list(r.get("regulatory_developments") or []))
        if _is_geographically_relevant(item)
    ][:7]

    # EU-wide policy belongs in regulation, not market monitoring.
    moved_to_regulation = []
    market_watch = []
    for item in market_watch_raw:
        if _is_eu_policy_item(item):
            moved_to_regulation.append(
                {
                    "tema": item.get("titulo") or "Política europeia",
                    "pais": item.get("pais") or "União Europeia",
                    "resumo": "Sem impacto transacional identificado.",
                    "source_ids": item.get("source_ids", [])[:1],
                }
            )
        else:
            market_watch.append(item)
    regulation = _dedupe_by_source(moved_to_regulation + regulation)[:7]

    cleaned_opportunities: list[dict] = []
    demoted_watch: list[dict] = []

    for item in opportunities:
        evidence = " ".join(
            [
                str(item.get("tipo", "")),
                str(item.get("porque_interessa", "")),
                str(item.get("proximo_passo", "")),
            ]
        )
        score = int(item.get("deal_score") or 0)

        has_strong_trigger = _contains_any(evidence, STRONG_TRIGGER_SIGNALS)
        looks_non_transactional = _contains_any(evidence, NO_TRIGGER_SIGNALS)

        if not has_strong_trigger and looks_non_transactional:
            demoted_watch.append(
                {
                    "titulo": _normalise_sentence(item.get("empresa")) or "Tema",
                    "pais": _normalise_sentence(item.get("pais")) or "Iberia",
                    "resumo": "Sem trigger transacional identificado.",
                    "source_ids": item.get("source_ids", [])[:1],
                }
            )
            continue

        item["deal_score"] = max(61, score) if has_strong_trigger else min(score, 60)
        if item["deal_score"] < 61:
            demoted_watch.append(
                {
                    "titulo": _normalise_sentence(item.get("empresa")) or "Tema",
                    "pais": _normalise_sentence(item.get("pais")) or "Iberia",
                    "resumo": _trim_words(
                        item.get("porque_interessa") or "Sem trigger transacional identificado.",
                        30,
                    ),
                    "source_ids": item.get("source_ids", [])[:1],
                }
            )
            continue

        item["empresa"] = _pt_pt(item.get("empresa"))
        item["pais"] = _pt_pt(item.get("pais"))
        item["tipo"] = _pt_pt(item.get("tipo"))
        item["porque_interessa"] = _trim_words(_pt_pt(item.get("porque_interessa")), 55)
        item["proximo_passo"] = _trim_words(_pt_pt(item.get("proximo_passo")), 25)
        cleaned_opportunities.append(item)

    market_watch = _dedupe_by_source(demoted_watch + market_watch)[:7]
    for item in market_watch:
        item["titulo"] = _pt_pt(item.get("titulo"))
        item["pais"] = _pt_pt(item.get("pais"))
        summary = _pt_pt(item.get("resumo"))
        if not summary or _contains_any(summary, SPECULATIVE_PHRASES):
            summary = "Sem trigger transacional identificado."
        elif "trigger transacional" not in summary.casefold():
            summary = summary.rstrip(".") + ". Sem trigger transacional identificado."
        item["resumo"] = _trim_words(summary, 30)

    for item in regulation:
        item["tema"] = _pt_pt(item.get("tema"))
        item["pais"] = _pt_pt(item.get("pais"))
        summary = _pt_pt(item.get("resumo"))
        if not summary or _contains_any(summary, SPECULATIVE_PHRASES):
            summary = "Sem impacto transacional identificado."
        elif "impacto transacional" not in summary.casefold():
            summary = summary.rstrip(".") + ". Sem impacto transacional identificado."
        item["resumo"] = _trim_words(summary, 20)

    opportunity_sources = {
        int(sid)
        for item in cleaned_opportunities
        for sid in item.get("source_ids", [])
    }
    market_watch = [
        item
        for item in market_watch
        if not any(int(sid) in opportunity_sources for sid in item.get("source_ids", []))
    ][:7]
    regulation = [
        item
        for item in regulation
        if not any(int(sid) in opportunity_sources for sid in item.get("source_ids", []))
    ][:7]

    valid_priorities: list[dict] = []
    allowed_priority_sources = opportunity_sources
    for priority in list(r.get("prioridades") or [])[:7]:
        action = _normalise_sentence(priority.get("acao"))
        source_ids = [int(x) for x in priority.get("source_ids", [])]
        if not action or _contains_any(action, VAGUE_ACTIONS):
            continue
        if not any(sid in allowed_priority_sources for sid in source_ids):
            continue
        priority["empresa"] = _pt_pt(priority.get("empresa"))
        priority["tipo"] = _pt_pt(priority.get("tipo"))
        priority["acao"] = _trim_words(_pt_pt(action), 15)
        valid_priorities.append(priority)

    # Never show a commercial-priority table when there are no genuine opportunities.
    if not cleaned_opportunities:
        valid_priorities = []

    r["opportunities"] = cleaned_opportunities[:7]
    r["market_watch"] = market_watch[:7]
    r["regulatory_developments"] = regulation[:7]
    r["prioridades"] = valid_priorities[:7]
    r["dashboard"]["setores_ativos"] = list(
        dict.fromkeys(r["dashboard"].get("setores_ativos") or [])
    )[:5]
    selected_geographies = []
    for item in r["opportunities"] + r["market_watch"] + r["regulatory_developments"]:
        geo = _pt_pt(item.get("pais"))
        if geo and geo not in selected_geographies:
            selected_geographies.append(geo)
    r["dashboard"]["geografias"] = selected_geographies[:4]
    return r


def analyse(items: list[dict], prompt: str) -> dict:
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    model = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    payload = json.dumps(items, ensure_ascii=False)

    resp = client.responses.create(
        model=model,
        instructions=prompt,
        input=(
            "Analisa exclusivamente os itens seguintes e usa apenas os source_ids existentes. "
            "Não inventes factos, intenções, compradores, assessores ou necessidades de capital. "
            "Uma PPA, parceria comercial, inauguração, licenciamento, consulta pública, apoio "
            "público ou obra concluída não é oportunidade sem trigger explícito de venda, capital, "
            "financiamento, refinanciamento, procura de investidor/parceiro ou assessoria. "
            "Uma venda confirmada de ativo/projeto é um trigger transacional. "
            "Não repitas o mesmo source_id em secções diferentes. "
            "Se não houver oportunidades, devolve oportunidades e prioridades vazias.\n\n"
            + payload
        ),
        text={
            "format": {
                "type": "json_schema",
                "name": "daily_radar",
                "strict": True,
                "schema": SCHEMA,
            }
        },
    )
    return _clean(json.loads(response.output_text))
