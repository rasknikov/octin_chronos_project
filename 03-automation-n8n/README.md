# 03-automation-n8n

## Visao geral
Este lab organiza um sistema MoE (Mixture of Experts) no n8n para coordenar PhDs artificiais por especialidade com uma celula de integracao e humano no loop (HITL). O objetivo e reduzir entropia: cada agente atua apenas no que domina e o orquestrador decide a rota.

## Estrutura do lab
- Celula de Fundamentos (Matematica e Fisica): define restricoes e leis do sistema.
- Celula de Implementacao (ML e Engenharia): transforma restricoes em codigo e arquitetura.
- Auditor (Advogado do Diabo): revisa falhas logicas e riscos.
- Humano (Chief Scientist): aprova, refina ou aborta.

## Fluxo n8n (resumo)
1. Ingestao: Telegram Webhook.
2. Init Run Metadata: cria `run_id` e `ts_utc`.
3. Orquestrador: decide rota (physicist, ml_engineer ou auditor).
4. Contexto local: Execute Command com `ls -R`.
5. Sub-workflows: PhD Fisico e/ou PhD ML (Gemini node).
6. Auditor: valida logica e riscos.
7. HITL: aprovacao via Telegram (Aprovar, Refinar, Abortar).
8. Execucao local: Write File ou Execute Command.

## Guardrails
- Resposta JSON estrita por Schema (ver `schemas/`).
- Retry loop (max 3) se JSON quebrado.
- Sanitizacao de comandos (ver `guardrails/command_sanitization.md`).
- Auditoria obrigatoria antes do HITL.
- Bloqueio de caminhos fora de /octin_chronos/.
- Error Trigger: se qualquer node falhar (ex.: Gemini), envia alerta no Telegram.
  - O node de erro usa `TELEGRAM_CHAT_ID` via env var.

## SQL e padronizacao
Este lab inclui nodes Postgres para logs e relatorios:
- `Postgres Log PhD`: registra propostas dos PhDs.
- `Postgres Log Audit`: registra validacao do Auditor.
- `Postgres Log Execution`: registra execucao de comandos/gravacao.
- `Postgres Report (24h)`: gera resumo por expert.

Regra de padronizacao (obrigatoria):
- Use `snake_case` em tabelas e colunas.
- Campos minimos: `run_id`, `ts_utc`, `expert_id`, `task`, `status`, `payload_json`.
- `ts_utc` sempre em ISO-8601 UTC.
- Todo log deve ter `run_id` consistente em toda a cadeia do fluxo.

## Decision Log (por que escolhi isso?)
- Usei `snake_case` porque facilita leitura e grep em ambientes Linux onde o Chronos roda na trincheira.
- JSONB no Postgres porque o Gemini as vezes muda a estrutura dos logs e eu prefiro salvar tudo do que perder dado.
- Error Trigger no Telegram porque quando o Gemini cai, eu preciso saber na hora, nao no dia seguinte.
- `ts_utc` obrigatorio porque ja perdi horas reconciliando timezones em backtests.

## Artefatos desta pasta
- `workflows/phd_lab_blueprint.md`: blueprint completo do fluxo.
- `workflows/workflow_stub.json`: template de workflow para adaptar no n8n.
- `prompts/`: system prompts de cada agente.
- `schemas/router_decision.schema.json`: schema do Router.
- `schemas/phd_output_schema.json`: schema dos PhDs.
- `schemas/audit_response.schema.json`: schema do Auditor.
- `sql/schema.sql`: schema minimo das tabelas de log.
- `guardrails/`: regras de seguranca.

## Inicio rapido
1. Importe o template `workflows/workflow_stub.json` no n8n.
2. Configure o Telegram Trigger e o canal de aprovacao.
3. Configure o node do modelo (Google Gemini via LangChain).
4. Aplique os Schemas nos nodes de validacao.
5. Crie o schema no Postgres com `sql/schema.sql`.
6. Configure as credenciais do Postgres e ajuste as queries para seu schema.

Nota:
- Se for gravar texto com Write File, converta para binario antes (ex.: node Code ou Move Binary Data).

## Observacao
O template e propositalmente simples para evitar dependencias especificas de versao do n8n. Ajuste os nodes e as credenciais conforme o seu ambiente.
