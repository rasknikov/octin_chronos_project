# Octin Chronos Project
> Pesquisa aplicada em dinamica de sistemas, decomposicao senoidal e automacao de laboratorio multi-agente.

Este repositorio consolida tres frentes que se complementam: a disseccao matematica do EURUSD, as arquiteturas baselines de IA, e a automacao operacional via n8n. O foco e pesquisa e reproducibilidade, nao estrategia de trade.

Essa pesquisa começou em meados de 2024. O que você está lendo aqui é a sintetização de tudo o que deu certo e não deu nesses quase 2 anos de pesquisa, unido a uma dev cansada kkk

## O que tem aqui
- `01-research-dissection`: paper e scripts da Fase 1 (disseccao cinetica do EURUSD).
- `02-ai-architecture`: sintese das arquiteturas Weierstrass PINN V2 e Fractal FM SIREN V3.
- `03-automation-n8n`: lab n8n com PhDs artificiais, HITL e trilhos de seguranca.

## Principais resultados (Fase 1)
- R2 = 0.9504 na Equacao de Unificacao (XXVIII) para a janela completa.
- Tri-Pendulo com 3 senoides no tempo cronologico e 5 harmonicas no dominio da massa.
- Zona morta no H1: residuo converge para H ~= 0.5 em escalas macro na janela oficial.
- Matriz de inanicao: predominio de regimes 50/50 a 60/40; poucos regimes 80/20.
- A formulacao no dominio da massa usa um eixo viajante C_hp(M) e cinco harmonicas senoidais:

```math
P(M) = C_{hp}(M) + \sum_{k=1}^{5} a_k \sin(\omega_k M + \phi_k)
```

## Arquiteturas de IA (Fase 2)
- Weierstrass PINN V2: decomposicao greedy em 8 camadas com EMA fase zero e modulacao por ATR.
- Fractal FM SIREN V3: SIREN para fase, loss hibrida (MSE - beta * PearsonCorr).
- Diagnostico: micro-ruido (L5-L8) domina e derruba previsao intraday; fase macro correta nao garante direcao curta.

## Automacao n8n (Lab de PhDs)
- MoE com Router, Physicist, ML Engineer e Auditor.
- HITL obrigatorio antes de executar qualquer acao.
- Logs em Postgres com `run_id` e `ts_utc`.
- Error Trigger com alerta no Telegram.

## Onde comecar
1. Leia o paper principal: `01-research-dissection/paper/o_bebado_na_esteira.md`.
2. Veja os baselines de IA: `02-ai-architecture/README.md`.
3. Veja o lab n8n: `03-automation-n8n/README.md`.

## Nota de escopo
O projeto busca explicar estrutura e limites do determinismo em series financeiras. Nao e um sistema de trade pronto.
