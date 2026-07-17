from __future__ import annotations

import json
import os

from openai import OpenAI


def _item_schema(properties, required):
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": required,
    }


SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "today_in_30_seconds": {
            "type": "array",
            "maxItems": 4,
            "items": {"type": "string"},
        },
        "executive_summary": {"type": "string"},
        "banker_actions": {
            "type": "array",
            "maxItems": 3,
            "items": {"type": "string"},
        },
        "opportunities": {
            "type": "array",
            "maxItems": 3,
            "items": _item_schema(
                {
                    "empresa": {"type": "string"},
                    "pais": {"type": "string"},
                    "setor": {"type": "string"},
                    "tipo_oportunidade": {
                        "type": "string",
                        "enum": [
                            "processo_venda_provavel",
                            "mandato_financiamento",
                            "cliente_acompanhar",
                            "contexto_mercado",
                        ],
                    },
                    "probabilidade_transacao": {
                        "type": "string",
                        "enum": ["alta", "media", "baixa"],
                    },
                    "deal_score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "descricao": {"type": "string"},
                    "trigger": {"type": "string"},
                    "porque_agora": {"type": "string"},
                    "angulo_ma": {"type": "string"},
                    "quem_pode_mexer": {
                        "type": "array",
                        "maxItems": 5,
                        "items": {"type": "string"},
                    },
                    "proximo_passo": {"type": "string"},
                    "score": {"type": "integer", "minimum": 2, "maximum": 5},
                    "source_ids": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 3,
                        "items": {"type": "integer", "minimum": 1},
                    },
                },
                [
                    "empresa", "pais", "setor", "tipo_oportunidade",
                    "probabilidade_transacao", "deal_score", "descricao", "trigger",
                    "porque_agora", "angulo_ma", "quem_pode_mexer",
                    "proximo_passo", "score", "source_ids",
                ],
            ),
        },
        "market_watch": {
            "type": "array",
            "maxItems": 3,
            "items": _item_schema(
                {
                    "titulo": {"type": "string"},
                    "porque_importa": {"type": "string"},
                    "leitura_ma": {"type": "string"},
                    "acao": {"type": "string"},
                    "score": {"type": "integer", "minimum": 2, "maximum": 5},
                    "source_ids": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 3,
                        "items": {"type": "integer", "minimum": 1},
                    },
                },
                ["titulo", "porque_importa", "leitura_ma", "acao", "score", "source_ids"],
            ),
        },
        "regulatory_developments": {
            "type": "array",
            "maxItems": 5,
            "items": _item_schema(
                {
                    "tema": {"type": "string"},
                    "desenvolvimento": {"type": "string"},
                    "impacto": {"type": "string"},
                    "implicacao_ma": {"type": "string"},
                    "score": {"type": "integer", "minimum": 2, "maximum": 5},
                    "source_ids": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 3,
                        "items": {"type": "integer", "minimum": 1},
                    },
                },
                ["tema", "desenvolvimento", "impacto", "implicacao_ma", "score", "source_ids"],
            ),
        },
    },
    "required": [
        "today_in_30_seconds",
        "executive_summary",
        "banker_actions",
        "opportunities",
        "market_watch",
        "regulatory_developments",
    ],
}



_VAGUE_ACTION_TERMS = (
    "monitorizar", "acompanhar", "avaliar", "contactar utilities",
    "perceber impacto", "eventual", "potenciais movimentações",
)

_NON_IBERIAN_PHRASES = (
    "sem ligação direta a iberia",
    "sem ligação direta à iberia",
    "sem evidência atual de impacto ibérico",
    "sem impacto ibérico direto",
)


def _normalise_report(report: dict) -> dict:
    """Apply deterministic guardrails after the model response."""
    report = dict(report or {})

    opportunities = list(report.get("opportunities") or [])
    opportunities.sort(key=lambda x: int(x.get("deal_score") or 0), reverse=True)
    report["opportunities"] = opportunities[:3]

    # Actions are only allowed when tied to a concrete opportunity.
    if opportunities:
        actions = []
        for item in opportunities[:3]:
            action = str(item.get("proximo_passo") or "").strip()
            lowered = action.lower()
            if action and not any(term in lowered for term in _VAGUE_ACTION_TERMS):
                actions.append(action)
        report["banker_actions"] = actions[:3]
    else:
        report["banker_actions"] = []

    # Keep market watch Iberian and conservative. It is context, not a deal lead.
    cleaned_market = []
    for item in report.get("market_watch") or []:
        combined = " ".join(
            str(item.get(k) or "")
            for k in ("titulo", "porque_importa", "leitura_ma", "acao")
        ).lower()
        if any(phrase in combined for phrase in _NON_IBERIAN_PHRASES):
            continue
        item = dict(item)
        item["score"] = min(int(item.get("score") or 2), 3)
        item["acao"] = ""
        item["source_ids"] = list(item.get("source_ids") or [])[:1]
        cleaned_market.append(item)
    report["market_watch"] = cleaned_market[:3]

    # Generic regulation is never an actionable M&A lead.
    cleaned_reg = []
    for item in report.get("regulatory_developments") or []:
        item = dict(item)
        item["score"] = 2
        item["implicacao_ma"] = "Sem trigger transacional identificado."
        item["source_ids"] = list(item.get("source_ids") or [])[:1]
        cleaned_reg.append(item)
    report["regulatory_developments"] = cleaned_reg[:5]

    for item in report["opportunities"]:
        item["source_ids"] = list(item.get("source_ids") or [])[:1]

    return report


def analyse(news_items, prompt_text: str, model: str = "gpt-4.1-mini"):
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    payload = json.dumps(news_items, ensure_ascii=False)

    response = client.responses.create(
        model=model,
        input=f"{prompt_text}\n\nItens disponíveis em JSON:\n{payload}",
        text={
            "format": {
                "type": "json_schema",
                "name": "daily_energy_ma_radar",
                "schema": SCHEMA,
                "strict": True,
            }
        },
    )
    return _normalise_report(json.loads(response.output_text))
