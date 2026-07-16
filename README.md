# Energy M&A Deal Radar — Portugal

Relatório diário por email para oportunidades M&A e desenvolvimentos regulatórios no setor elétrico português.

## Setup

1. Criar repositório GitHub e copiar estes ficheiros.
2. Adicionar secrets em **Settings → Secrets and variables → Actions**:
   - `OPENAI_API_KEY`
   - `SMTP_HOST` — ex: `smtp.gmail.com` ou `smtp.office365.com`
   - `SMTP_PORT` — normalmente `587`
   - `SMTP_USER`
   - `SMTP_PASSWORD`
   - `EMAIL_FROM`
   - `EMAIL_TO` — emails separados por vírgula
3. Ir a **Actions → Daily Energy M&A Radar → Run workflow** para testar manualmente.
4. O cron corre em dias úteis.

## Ajustes recomendados

- Completar `config/sources.yml` com fontes pagas ou RSS internos.
- Expandir `config/watchlist.yml`.
- Rever semanalmente falsos positivos e keywords.
- Usar password de aplicação para Gmail/Outlook, quando aplicável.
