# WEIERSTRASS_ENGINE (V2) - README

## Visao geral
Este modulo implementa o **Weierstrass Decomposition Engine v3** com PINN, aplicado ao EURUSD H1 (167.771 barras, 1999-01-04 10:00:00 a 2026-01-08 01:00:00). O objetivo e decompor o preco em 8 camadas senoidais hierarquicas moduladas por ATR, usando Greedy Layer-Wise Training com detrending exato.

## O que foi construido
- Um motor PyTorch em `06_WEIERSTRASS_ENGINE/` que decompõe EURUSD H1 em 8 camadas senoidais com modulação por ATR.
- Treinamento greedy em camadas (macro -> micro) com detrending exato por low-pass.
- Oraculo de sinais por comite (bussola + gatilho) e backtest OOS hermetico.
- Infraestrutura de retreino walk-forward com correcoes de vazamento.

## Zero ferramentas prontas
- Sem LSTM, Transformer, ou arquiteturas prontas.
- Sem FFT (`numpy.fft` ou `scipy.fft`).
- Sem `pandas.ewm`, `ta-lib` ou indicadores prontos.
- Tudo calculado manualmente (EMA fase zero, ATR incremental, features).

## Arquitetura matematica
Cada camada k modela um banco de harmonicas senoidais com fase modulada por ATR:

```math
y_k(t) = \sum_{h=1}^{N_h} A_{k,h} \cdot \sin\left(2\pi f_{k,h} \cdot \int_0^t \mathrm{ATR}_k(\tau)\,d\tau + \phi_{k,h}\right) + b_k
```

## Loop greedy (v3 — detrending exato)
Para cada camada k:
- `lowpass_k = ZeroPhaseEMA(residual, span_k)`
- Treinar `WeierstrassWaveLayer` para **ajustar** `lowpass_k`
- `residual = residual - lowpass_k` (detrending exato)
- Congelar camada

Decisao critica: o detrending usa o **low-pass**, nao a previsao treinada. Isso garante uma cadeia residual matematicamente perfeita; a camada treinada afeta apenas a reconstrucao final.

## Testes de estabilidade de optimizer
Antes do pipeline final, foram feitos testes com diferentes otimizadores e agendas de LR para verificar a estabilidade da tecnica de suavizacao de gradiente (EMA fase zero) e evitar colapso do treinamento em camadas profundas. Esse passo validou a robustez do detrending e orientou a escolha de otimizador e hyperparams por camada (ver `config.py`).

## Scripts por etapa (links diretos)
- Lab (treino e exportacao de pesos): `weierstrass_engine.py`
- Runner da decomposicao (gera plots e pesos): `run_decomposition.py`
- Configuracao de camadas (EMA/ATR/harmonics/epochs): `config.py`
- Validador de fase (Directional Accuracy): `validate_phase_accuracy.py`
- Oraculo de sinais (bussola + gatilho): `bot_execution.py`
- Backtest hermetico OOS: `hermetic_backtest.py`
- Gateway de broker (stub de risco/ordem): `broker_gateway.py`

## Outputs (organizado como no paper_formalizacao)
- `outputs/plots/` — graficos (reconstruction, equity, phase accuracy, etc.)
- `outputs/logs/` — logs de treino e execucao
- `outputs/weights/` — pesos treinados (`pesos_weierstrass.json` e variantes)
- `outputs/reports/` — relatorios em markdown

## Resultados de verificacao (decomposicao)
- **Exact Reconstruction R2:** ~0.99998 (soma dos low-pass)
- **Trained Reconstruction R2:** ~0.97 (ver `outputs/logs/train_pinn_v2.log`)
- **Final Residual Std:** ~0.00073 (aprox 0.7 pips)
- **Final Residual Max:** ~0.0108 (aprox 10.8 pips)

Observacao: o R2 treinado pode cair em camadas profundas porque 8 harmonicas nao capturam milhares de micro-oscilações. Isso e esperado; a cadeia de detrending continua perfeita.

## Validacao de fase (Directional Accuracy)
O R2 penaliza amplitude, nao timing. O script `validate_phase_accuracy.py` mede Directional Accuracy (DA): % de barras onde o sinal da derivada da onda coincide com a direcao real.

Resultados (todas as camadas acima de 50%):
- L1 — Multi-Year: 77.0% (p < 1e-9)
- L2 — Annual: 85.0% (p < 1e-9)
- L3 — Quarterly: 66.3% (p < 1e-9)
- L4 — Monthly: 58.7% (p < 1e-9)
- L5 — Weekly: 52.6% (p < 1e-9)
- L6 — Daily: 51.2% (p < 1e-9)
- L7 — Intraday: 50.9% (p < 1e-9)
- L8 — Micro-Pip: 50.5% (p < 0.001)

Conclusao: todas as camadas capturam estrutura de fase estatisticamente significativa, mesmo quando o R2 e negativo nas microcamadas.

## Regimes de operacao (macro vs micro)
**Regime MICRO (scalping):**
- Bussola: L4 (Mensal) + L5 (Semanal)
- Gatilho: L6 (Diaria) + L7 (Intraday)
- Projecao/Hold: 3 barras (H1)
- Lookback: 720 horas (~30 dias)
- Retreino: a cada 168 horas, 300 epochs
- Amostra OOS: ~20.000 barras (~3 anos)

**Regime MACRO (trend):**
- Bussola: L2 (Anual) + L3 (Trimestral)
- Gatilho: L4 (Mensal) + L5 (Semanal)
- Projecao/Hold: 168 horas (1 semana)
- Lookback: 4320 horas (~6 meses)
- Retreino: a cada 168 horas, 150 epochs
- Amostra OOS: ~30.000 barras (~5 anos)

## Backtest V2 (resumo)
Micro (scalping, 3 anos) apresentou IC negativo e PF < 1.0, reforcando comportamento mean-reverting no horizonte curto. O regime macro (5 anos) melhorou acuracia direcional, mas com edge limitado. Detalhes completos em `outputs/reports/V2_PINN_BACKTEST_ANALYSIS.md`.

## Walk-forward fixes (V2.1)
- **Global vs Local Phase Leak:** bounds de Phi(t) eram recomputados localmente em janelas de 30 dias, acelerando ondas. Fix: bounds globais injetados no retrainer.
- **PyTorch Weight Amnesia:** o retrainer recriava a rede sem carregar pesos globais. Fix: copia explicita do `state_dict` antes do fine-tuning.

## Como reproduzir (minimo)
- Rodar decomposicao e gerar plots: `python run_decomposition.py`
- Validar fase: `python validate_phase_accuracy.py`
- Backtest OOS: `python hermetic_backtest.py`

## Observacao importante
Apesar da matematica correta e da fase capturada, o IC permaneceu estruturalmente negativo no micro. Isso sugere que o EURUSD H1 e predominantemente mean-reverting no horizonte curto e que a extrapolacao inercial de curto prazo tende a errar o lado.
