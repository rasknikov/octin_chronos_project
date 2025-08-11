# 02-ai-architecture

## Visao geral
Esta pasta sintetiza as duas arquiteturas baselines (Weierstrass PINN V2 e Fractal FM SIREN V3) e o motivo principal da falha operacional: o ruido intraday do EURUSD (zona morta) domina as camadas micro e derruba o sinal direcional, mesmo quando a fase macro esta correta.

## Arquitetura A: Weierstrass PINN V2
- Decomposicao greedy em 8 camadas com EMA fase zero e modulacao de frequencia por ATR.
- Camadas macro e micro treinadas em cascata, com residual matematicamente perfeito.
- Oraculo de sinais com bussola (macro) e gatilho (micro).
- Links: `../06_WEIERSTRASS_ENGINE/README.md` e `../06_WEIERSTRASS_ENGINE/V2_PINN_BACKTEST_ANALYSIS.md`.

## Arquitetura B: Fractal FM SIREN V3
- Substitui MLP por SIREN (seno como perceptron), com modulacao de frequencia interna.
- Mantem o greedy detrending com EMA fase zero.
- Loss hibrida (MSE - beta * PearsonCorr) para amplitude + direcao.
- Links: `../07_FRACTAL_FM_ENGINE/README.md` e `../07_FRACTAL_FM_ENGINE/V3_FM_SIREN_ANALYSIS.md`.

## Por que falhou (diagnostico objetivo)
- O EURUSD H1 apresenta **zona morta**: o residuo micro (L5-L8) tem entropia alta e comportamento mean-reverting.
- R2 e direcao entram em conflito nas camadas profundas: o modelo acerta fase, mas erra amplitude e sinal no horizonte curto.
- Mesmo com detrending exato, o ruído intraday nao permite extrapolacao inercial robusta em micro escala.

## Evidencia experimental
- V2 (micro): IC negativo e PF < 1, mesmo com fase estatisticamente significativa.
- V3 (macro OOS corrigido): PF < 1 e IC levemente negativo.
- A matematica da decomposicao funciona; a previsao intraday nao.

## Direcao futura (salto arquitetural)
- Preprocessamento mais robusto para remover completamente L8, L7, L6 e L5 (micro ruido).
- Ajuste de amplitude aprendivel (ganho dinamico) por camada, separado da fase.
- Duas linhas de evolucao:
- Modelos separados: um para macro (L1-L4), outro para micro (somente quando houver sinal de baixa entropia).
- Modelo unificado: gating dinamico para zerar camadas micro quando a entropia local exceder limiar.

## Objetivo desta fase
Consolidar o baseline matematico e preparar a proxima geracao do pipeline com pre-processamento anti-ruido e controle de amplitude por regime.
