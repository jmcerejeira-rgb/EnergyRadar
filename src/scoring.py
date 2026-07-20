from __future__ import annotations
from typing import Any

def cap_score(score: int, item: dict[str, Any], config: dict[str, Any]) -> int:
    caps = ((config or {}).get("deal_score") or {}).get("caps") or {}
    text = " ".join(str(item.get(k) or "") for k in ("porque_interessa", "resumo", "tipo")).lower()
    applied = [100]
    if "sem trigger" in text:
        applied.append(int(caps.get("no_concrete_trigger", 60)))
    if any(x in text for x in ("ppa", "acordo comercial", "parceria comercial")):
        applied.append(int(caps.get("PPA_or_commercial_agreement_only", 45)))
    if any(x in text for x in ("inauguração", "concluída", "entrada em operação")):
        applied.append(int(caps.get("inauguration_or_completion", 35)))
    return max(0, min(int(score), min(applied)))

def confidence_label(value: str) -> str:
    value = (value or "").strip().lower()
    return {"alta": "Alta", "media": "Média", "média": "Média", "baixa": "Baixa"}.get(value, "Média")
