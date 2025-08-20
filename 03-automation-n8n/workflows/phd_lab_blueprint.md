# phd_lab_blueprint.md

## 1. Os Cerebros: prompts/
Cada System Prompt e uma camisa de forca tecnica. Cada agente so faz sua especialidade.

### The Router (O orquestrador)
- Role: Dispatcher Central do Lab Octin.
- Output: JSON estrito indicando o proximo PhD e a tarefa especifica.
- Logica: teoria/equacoes -> Physicist; implementacao/codigo -> ML Engineer; erro/risco -> Auditor.

### The Physicist (O Guardiao das Leis)
- Role: PhD em Fisica Teorica e Sistemas Dinamicos.
- Mantra: "O codigo deve respeitar a entropia e as leis da dinamica classica."
- Task: transformar problemas de mercado em modelos matematicos; entregar logica proposicional e restricoes (sem codigo final).

### The ML Engineer (O Construtor de tensores)
- Role: PhD em Deep Learning, especialista em PyTorch e otimizacao.
- Task: traduzir a logica do Physicist para arquitetura, convergencia e regularizacao.

### The Auditor (pessimista)
- Role: QA + Ciberseguranca, pessimista por definicao.
- Task: revisar logica, buscar falhas e barrar o fluxo se algo estiver 99% e nao 100%.

## 2. Os Trilhos: schemas/
Todos os agentes respondem em JSON estruturado (Response Format).

- Router: `schemas/router_decision.schema.json`
- Physicist/ML Engineer: `schemas/phd_output_schema.json`
- Auditor: `schemas/audit_response.schema.json`

Schema base dos PhDs:
```json
{
  "expert_id": "string",
  "technical_rationale": "string",
  "proposed_solution": "string/code",
  "confidence_score": "float (0-1)",
  "requires_human_intervention": "boolean",
  "next_step_recommendation": "string"
}
```

## 3. O Fluxo de Trabalho: n8n
1. Telegram Trigger: recebe a ordem da Chief Scientist.
2. Init Run Metadata: gera `run_id` e `ts_utc`.
3. Router (Gemini): decide quem atua e define a tarefa.
4. Contexto local: Execute Command com `ls -R` para listar arquivos.
5. PhD (Gemini): executa a tarefa com base no contexto local.
6. Auditor: valida logica, riscos e comandos.
7. HITL (Wait): pausa e envia aprovacao no Telegram.
   - Relatorio do PhD
   - Veredito do Auditor
   - Botoes: [APROVAR E EXECUTAR] | [PEDIR REFINAMENTO] | [CANCELAR]
8. Execute: se aprovado, grava ou executa via Write File ou Execute Command.

## 4. Guardrails
- JSON estrito com retry (max 3) quando o schema falhar.
- Auditor obrigatorio antes do HITL.
- Sanitizacao de comandos (ver `guardrails/command_sanitization.md`).
- Bloqueio de caminhos fora de /octin_chronos/.

## 5. SQL e Logs
O fluxo inclui nodes Postgres para persistir memoria operacional:
- Logs de propostas (PhDs), auditoria e execucao.
- Relatorio agregado (ex.: ultimas 24h).

Padrao minimo (obrigatorio):
- Tabelas e colunas em `snake_case`.
- Campos minimos: `run_id`, `ts_utc`, `expert_id`, `task`, `status`, `payload_json`.
- `ts_utc` em ISO-8601 UTC.

## 6. Error Trigger
Inclua um Error Trigger dedicado para alertar no Telegram quando qualquer node falhar (ex.: Gemini indisponivel). nao eh pra esquecer!!!!

## 7. Notas de trincheira
- Se o JSON vier quebrado, eu prefiro travar o fluxo e pedir retry a confiar na sorte.
- O schema em SQL precisa tolerar log torto; por isso o payload vai inteiro em JSONB.
- O HITL e chato, mas ja salvou dias de trabalho quando um agente errou o contexto.
