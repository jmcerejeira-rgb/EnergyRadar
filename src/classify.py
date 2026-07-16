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
                    "descricao": {"type": "string"},
                    "trigger": {"type": "string"},
                    "angulo_ma": {"type": "string"},
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
                    "empresa", "pais", "setor", "descricao", "trigger",
                    "angulo_ma", "proximo_passo", "score", "source_ids",
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
    return json.loads(response.output_text)
