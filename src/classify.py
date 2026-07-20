from __future__ import annotations
import json, os
from openai import OpenAI

SCHEMA = {
  "type": "object",
  "additionalProperties": False,
  "properties": {
    "executive_summary": {"type": "string"},

    "opportunities": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
          "empresa": {"type": "string"},
          "pais": {"type": "string"},
          "setor": {"type": "string"},
          "descricao_2_linhas": {"type": "string"},
          "sinal_observado": {"type": "string"},
          "fonte_data": {"type": "string"},
          "url": {"type": "string"},
          "angulo_ma": {"type": "string"},
          "potenciais_compradores_investidores": {
            "type": "array",
            "items": {"type": "string"}
          },
          "score": {"type": "integer", "minimum": 1, "maximum": 5},
          "proximo_passo": {"type": "string"}
        },
        "required": [
          "empresa",
          "pais",
          "setor",
          "descricao_2_linhas",
          "sinal_observado",
          "fonte_data",
          "url",
          "angulo_ma",
          "potenciais_compradores_investidores",
          "score",
          "proximo_passo"
        ]
      }
    },

    "regulatory_developments": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
          "tema": {"type": "string"},
          "desenvolvimento": {"type": "string"},
          "impacto_esperado": {"type": "string"},
          "implicacao_ma": {"type": "string"},
          "fonte_data": {"type": "string"},
          "url": {"type": "string"},
          "score": {"type": "integer", "minimum": 1, "maximum": 5}
        },
        "required": [
          "tema",
          "desenvolvimento",
          "impacto_esperado",
          "implicacao_ma",
          "fonte_data",
          "url",
          "score"
        ]
      }
    },

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

def analyse(news_items, prompt_text: str, model: str = "gpt-4.1-mini"):
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    payload = json.dumps(news_items, ensure_ascii=False)[:120000]

    resp = client.responses.create(
        model=model,
        input=f"{prompt_text}\n\nNotícias em JSON:\n{payload}",
        text={
            "format": {
                "type": "json_schema",
                "name": "daily_energy_ma_radar",
                "schema": SCHEMA,
                "strict": True
            }
        },
    )

    return json.loads(resp.output_text)
