from __future__ import annotations

import json
import os
import re
import unicodedata
from difflib import SequenceMatcher

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
                    "setor": {"type": "string", "enum": ["Energy", "Transport Infrastructure", "Digital Infrastructure", "Utilities Networks", "Water & Waste"]},
                    "subcategoria": {"type": "string"},
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
                    "empresa", "pais", "setor", "subcategoria", "tipo_oportunidade",
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
                    "setor": {"type": "string", "enum": ["Energy", "Transport Infrastructure", "Digital Infrastructure", "Utilities Networks", "Water & Waste"]},
                    "subcategoria": {"type": "string"},
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
                ["setor", "subcategoria", "titulo", "porque_importa", "leitura_ma", "acao", "score", "source_ids"],
            ),
        },
        "regulatory_developments": {
            "type": "array",
            "maxItems": 5,
            "items": _item_schema(
                {
                    "setor": {"type": "string", "enum": ["Energy", "Transport Infrastructure", "Digital Infrastructure", "Utilities Networks", "Water & Waste"]},
                    "subcategoria": {"type": "string"},
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
                ["setor", "subcategoria", "tema", "desenvolvimento", "impacto", "implicacao_ma", "score", "source_ids"],
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



def _plain(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\b(source[_ ]?ids?|json|parser|hash|identificador)\b", "", text, flags=re.I)
    text = re.sub(r"[^a-zA-Z0-9 ]+", " ", text).lower()
    return re.sub(r"\s+", " ", text).strip()


def _editorial_text(item: dict, section: str) -> str:
    fields = {
        "opportunities": ("empresa", "setor", "subcategoria", "descricao", "trigger"),
        "market_watch": ("setor", "subcategoria", "titulo", "porque_importa", "leitura_ma"),
        "regulatory_developments": ("setor", "subcategoria", "tema", "desenvolvimento", "impacto"),
    }[section]
    return _plain(" ".join(str(item.get(k) or "") for k in fields))


def _same_story(a: str, b: str) -> bool:
    if not a or not b:
        return False
    sa, sb = set(a.split()), set(b.split())
    overlap = len(sa & sb) / max(1, min(len(sa), len(sb)))
    return overlap >= 0.72 or SequenceMatcher(None, a, b).ratio() >= 0.78


def _strip_internal_language(value):
    if isinstance(value, str):
        value = re.sub(r"\bsource[_ ]?ids?\s*[:#]?\s*[0-9, ]*", "", value, flags=re.I)
        value = re.sub(r"\s+", " ", value).strip(" -–—,:;")
        return value
    if isinstance(value, list):
        return [_strip_internal_language(v) for v in value]
    if isinstance(value, dict):
        return {k: _strip_internal_language(v) for k, v in value.items()}
    return value


def _deduplicate_sections(report: dict) -> dict:
    seen: list[str] = []
    for section in ("opportunities", "market_watch", "regulatory_developments"):
        kept = []
        for item in report.get(section) or []:
            key = _editorial_text(item, section)
            if any(_same_story(key, previous) for previous in seen):
                continue
            seen.append(key)
            kept.append(item)
        report[section] = kept
    return report


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
    report = _strip_internal_language(dict(report or {}))
    report = _deduplicate_sections(report)

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
    report["regulatory_developments"] = cleaned_reg[:3]

    for item in report["opportunities"]:
        item["source_ids"] = list(item.get("source_ids") or [])[:1]

    if not report["opportunities"] and not report["market_watch"] and not report["regulatory_developments"]:
        report["today_in_30_seconds"] = [
            "Sem novos desenvolvimentos relevantes para originação nas últimas 24 horas."
        ]
        report["executive_summary"] = "Não foram identificados novos factos com relevância transacional ou económica material."

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
                "name": "daily_energy_infrastructure_ma_radar",
                "schema": SCHEMA,
                "strict": True,
            }
        },
    )
    return _normalise_report(json.loads(response.output_text))
