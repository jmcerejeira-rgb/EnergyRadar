from __future__ import annotations

import re
import unicodedata
from typing import Any


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text.lower()).strip()


STRONG_MA_TRIGGERS = [
    "venda", "alienacao", "alienar", "aquisição", "aquisicao", "comprou", "compra",
    "fusão", "fusao", "merger", "m&a", "processo de venda", "procura investidor",
    "entrada de acionista", "saida de acionista", "mudanca acionista", "controlo exclusivo",
    "controlo conjunto", "operação de concentração", "operacao de concentracao",
    "notifica a aquisição", "notifica a aquisicao", "decisão de não oposição", "decisao de nao oposicao",
    "capital raise", "aumento de capital", "refinanciamento", "reestruturacao",
    "reestruturação", "insolvencia", "insolvência", "per", "distress",
    "assessor financeiro", "mandato", "strategic review", "revisão estratégica", "revisao estrategica",
]

MEDIUM_MA_TRIGGERS = [
    "joint venture", "parceria estrategica", "parceria estratégica", "plataforma", "portfolio", "carteira",
    "pipeline", "rtb", "ready to build", "licenciado", "licença", "licenca", "ponto de ligação",
    "ponto de ligacao", "ligacao a rede", "ligação à rede", "concessao", "concessão",
    "leilao", "leilão", "contrato de longo prazo", "ppa", "capex", "financiamento",
]

REGULATORY_TERMS = [
    "erse", "dgeg", "ren", "regulamento", "consulta publica", "consulta pública", "tarifas",
    "licenciamento", "acesso a rede", "acesso à rede", "rede elétrica", "rede eletrica",
    "armazenamento", "bess", "autoconsumo", "comunidades de energia", "mobilidade eletrica",
    "mobilidade elétrica", "biometano", "leilao", "leilão", "serviços de sistema", "servicos de sistema",
    "restricoes tecnicas", "restrições técnicas", "curtailment", "remit",
]

MARKET_RELEVANCE_TERMS = [
    "solar", "fotovoltaico", "renovavel", "renovável", "energia", "armazenamento", "bateria",
    "bess", "eolico", "eólico", "biomassa", "bioenergia", "biometano", "hidrogenio", "hidrogénio",
    "ev charging", "mobilidade eletrica", "eficiencia energetica", "eficiência energética", "esco",
    "o&m", "ipp", "utility", "autoconsumo", "ppa", "rede", "capacidade",
]

IBERIA_TERMS = [
    "portugal", "portugues", "portuguesa", "português", "portugueses", "lisboa", "porto",
    "espanha", "espanhol", "espanhola", "iberia", "ibérico", "iberico",
]


def _contains_any(text: str, terms: list[str]) -> list[str]:
    norm_text = _norm(text)
    hits = []
    for term in terms:
        nt = _norm(term)
        if nt and nt in norm_text:
            hits.append(term)
    return hits


def _item_text(item: dict) -> str:
    return " ".join([
        str(item.get("title", "")),
        str(item.get("summary", "")),
        str(item.get("source", "")),
        str(item.get("url", "")),
    ])


def classify_item(item: dict) -> dict[str, Any]:
    """Deterministic pre-triage before the LLM.

    This is deliberately conservative. It does not decide the final M&A conclusion;
    it labels the evidence available in the source item so the LLM sees the difference
    between market relevance and actionable transaction signal.
    """
    text = _item_text(item)
    strong = _contains_any(text, STRONG_MA_TRIGGERS)
    medium = _contains_any(text, MEDIUM_MA_TRIGGERS)
    regulatory = _contains_any(text, REGULATORY_TERMS)
    market = _contains_any(text, MARKET_RELEVANCE_TERMS)
    iberia = _contains_any(text, IBERIA_TERMS)
    watchlist_hits = item.get("watchlist_hits") or {}

    if strong:
        relevance_type = "candidate_ma_lead"
        lead_candidate = True
        rationale = "Trigger transacional forte detetado antes da análise IA."
    elif medium and (watchlist_hits or iberia):
        relevance_type = "possible_ma_lead"
        lead_candidate = True
        rationale = "Sinal médio com ligação ibérica ou watchlist; requer validação."
    elif regulatory:
        relevance_type = "regulatory_monitoring"
        lead_candidate = False
        rationale = "Notícia/regulação relevante para mercado, mas sem trigger M&A direto."
    elif market or watchlist_hits:
        relevance_type = "market_monitoring"
        lead_candidate = False
        rationale = "Notícia relevante para acompanhar, mas sem evidência transacional suficiente."
    else:
        relevance_type = "low_relevance"
        lead_candidate = False
        rationale = "Baixa evidência de relevância M&A ou regulatória."

    # Higher number = show earlier to the LLM/report.
    priority = 0
    if lead_candidate:
        priority += 30
    if strong:
        priority += 20
    if medium:
        priority += 10
    if watchlist_hits:
        priority += 8
    if iberia:
        priority += 5
    if regulatory:
        priority += 4
    if market:
        priority += 2

    return {
        "relevance_type": relevance_type,
        "lead_candidate": lead_candidate,
        "triage_priority": priority,
        "triage_rationale": rationale,
        "strong_ma_triggers": sorted(set(strong)),
        "medium_ma_triggers": sorted(set(medium)),
        "regulatory_terms": sorted(set(regulatory))[:12],
        "market_terms": sorted(set(market))[:12],
        "iberia_terms": sorted(set(iberia))[:8],
    }


def annotate_triage(items: list[dict]) -> list[dict]:
    annotated = []
    for item in items:
        new_item = dict(item)
        new_item["triage"] = classify_item(new_item)
        annotated.append(new_item)
    return annotated


def sort_by_triage_priority(items: list[dict]) -> list[dict]:
    return sorted(
        items,
        key=lambda x: (
            int((x.get("triage") or {}).get("triage_priority", 0)),
            int(x.get("watchlist_priority", 0)),
            len(x.get("summary", "") or ""),
        ),
        reverse=True,
    )


def triage_counts(items: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = (item.get("triage") or {}).get("relevance_type", "unclassified")
        counts[key] = counts.get(key, 0) + 1
    return counts


def build_triage_prompt() -> str:
    return """
Camada de triagem pré-IA:
Cada notícia enviada pode trazer o campo "triage", calculado antes da tua análise.
Usa-o como evidência auxiliar, não como verdade absoluta.

Decisão obrigatória em dois passos:
1. Primeiro decide se a notícia é apenas relevante para monitorização de mercado/regulação.
2. Só depois promove para "Oportunidades M&A" se houver target/ativo identificável, trigger transacional e próximo passo comercial plausível.

Regras duras:
- "lead_candidate=false" ou "relevance_type=market_monitoring" normalmente NÃO deve entrar em oportunidades M&A.
- Pode entrar em "market_watch" se for relevante para acompanhar.
- "regulatory_monitoring" deve ir para desenvolvimentos regulatórios, não para oportunidades M&A, salvo se houver empresa/ativo e trigger transacional concreto.
- Watchlist hit sozinho não é lead M&A.
- PPA, licenciamento, RTB, ligação à rede ou leilão só são lead M&A quando houver ativo/plataforma identificável e racional de aquisição/capital raise.
- Se o próximo passo for apenas "acompanhar notícia", não é oportunidade M&A; é market_watch.
""".strip()
