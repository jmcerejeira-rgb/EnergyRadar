# Separação entre notícia relevante e lead M&A acionável

Esta versão adiciona uma camada de triagem antes da análise pela OpenAI.

## Objetivo

Evitar que qualquer notícia de energia seja promovida para oportunidade M&A.

O pipeline passa a distinguir:

1. `candidate_ma_lead` — há trigger transacional forte.
2. `possible_ma_lead` — há sinal médio, mas exige validação.
3. `regulatory_monitoring` — notícia regulatória relevante, mas sem lead M&A direto.
4. `market_monitoring` — notícia de mercado/watchlist relevante, mas sem trigger M&A.
5. `low_relevance` — pouca utilidade para originação.

## Regras práticas

Uma oportunidade M&A exige:

- target/ativo identificável;
- trigger transacional;
- racional de comprador/investidor;
- próximo passo comercial concreto.

Se faltar isto, a notícia deve ir para `market_watch` ou `regulatory_developments`, não para `opportunities`.

## Ficheiros novos/alterados

- `src/triage.py` — pré-classificação determinística.
- `src/main.py` — aplica triagem antes de chamar a OpenAI.
- `src/classify.py` — schema passa a incluir `market_watch`.
- `prompts/daily_report.md` — instruções explícitas de decisão em dois passos.
- `src/report.py` — email mostra a secção "Notícias relevantes para monitorizar".

## Log esperado

Ao correr `python src/main.py`, o terminal passa a mostrar algo como:

```text
Fetched relevant items: 30
Already seen items: 12
New items: 18
Watchlist hits in new items: 3
Triage counts: {'candidate_ma_lead': 2, 'regulatory_monitoring': 7, 'market_monitoring': 9}
```

## Nota

A triagem Python é conservadora e serve para orientar o modelo. A decisão final continua no prompt/schema da OpenAI, mas agora com menos espaço para falsos positivos.
