# Infrastructure & Energy M&A Radar — Iberia

Radar diário de originação para infraestrutura e energia em Portugal e Espanha.

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python src/main.py
```

## Estrutura

- `config/sources.yml`: fontes.
- `config/keywords.yml`: filtro inicial.
- `config/watchlist.yml`: entidades prioritárias.
- `config/scoring.yml`: regras e limites.
- `prompts/`: instruções editoriais e de classificação.
- `src/classify.py`: análise estruturada pela API OpenAI.
- `src/report.py`: email HTML.
- `src/persistence.py`: deduplicação por URL e por assinatura editorial durante 7 dias.

## GitHub Actions

Criar os secrets:
`OPENAI_API_KEY`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_FROM`, `EMAIL_TO`.

O workflow corre diariamente às 06:00 UTC e também pode ser executado manualmente.
