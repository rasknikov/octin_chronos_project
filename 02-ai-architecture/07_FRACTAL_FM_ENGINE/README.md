# FRACTAL_FM_ENGINE (V3) - README

## Visao geral
Este modulo implementa a arquitetura **FM SIREN (V3)** para decomposicao fractal do EURUSD H1. O modelo substitui MLPs tradicionais por camadas senoidais (SIREN), e usa *Greedy Layer-Wise Detrending* com EMA de fase zero para separar macro -> micro sem vazamento de gradiente.

## O que foi construido
- Motor SIREN com ativacao seno e modulacao de frequencia (FM) interna.
- Pipeline de decomposicao greedy em 8 camadas com alvos low-pass (EMA zero-phase).
- Oraculo de sinais e backtest hermetico walk-forward com retraining controlado.
- Pesos exportados para inferencia offline.

## Arquitetura (FM SIREN)
A rede aprende diretamente uma representacao senoidal continua:

```math
H^{(L)} = \sin\left( \omega_0 \cdot (H^{(L-1)} W^{(L)}) + \phi^{(L)} \right)
```

O eixo temporal e a fase intrinseca:
- `Phi(t) = \int_0^t ATR(\tau) d\tau` (fase integrada de volatilidade)

A perda e hibrida para amplitude + direcao:

```math
\mathcal{L} = \alpha \cdot \mathrm{MSE}(\hat{y}, y) - \beta \cdot \mathrm{PearsonCorr}(\Delta\hat{y}, \Delta y)
```

## Loop greedy (detrending exato)
Para cada camada:
- `target = EMA_zero_phase(residual, span)`
- treinar SIREN para ajustar `target`
- `residual = residual - target` (detrending exato)

Observacao: o residual e matematicamente perfeito; a previsao treinada so afeta a reconstrucao.

## Scripts por etapa (links diretos)
- Motor e topologia SIREN: `siren_engine.py`
- Pipeline de decomposicao: `run_fm_siren.py`
- Configuracao de camadas: `config.py`
- Treino inicial (in-sample curto): `train_siren_initial.py`
- Oraculo de sinais: `siren_bot_execution.py`
- Backtest hermetico OOS: `siren_hermetic_backtest.py`

## Dataset e janelas usadas
- Fonte: `01_DATALAKE/eurusd_h1_ohlc.csv`
- Todos os scripts filtram **>= 1999-01-01**.
- Treino inicial (`train_siren_initial.py`): **4320 barras**
  - 1999-01-04 10:00:00 ? 1999-09-15 03:00:00
- Decomposicao FM (`run_fm_siren.py`): **30.000 barras**
  - 1999-01-04 10:00:00 ? 2003-10-27 08:00:00
- Backtest hermetico (`siren_hermetic_backtest.py`): carrega todo o historico >= 1999; nos resultados reportados foi usada a janela de **30.000 barras** (5 anos).

## Resultados OOS (corrigidos apos vazamento)
O relatorio original continha vazamento. Os resultados reais corrigidos sao:

```text
======================================================================
  FM SIREN BACKTEST v3 REPORT
======================================================================

  Total Trades:     140
  Long / Short:     67 / 73
  Win Rate:         46.43%
  Profit Factor:    0.9094
  Total PnL:        -864.0 pips
  Avg Win:          +133.5 pips
  Avg Loss:         -127.2 pips
  Max Drawdown:     -3012.0 pips

  --- ML Performance Metrics ---
  Dir. Accuracy:    46.43%
  Long Precision:   50.75%
  Short Precision:  42.47%
  Predictive MAE:   461.46 pips
  Predictive RMSE:  733.31 pips
  Info Coeff (IC):  -0.0062
```

Conclusao: o motor e util para modelagem e diagnostico, mas nao demonstrou alpha operacional no walk-forward OOS nesta janela.

## Outputs (organizado como no paper_formalizacao)
- `outputs/plots/` — graficos (ex.: equity)
- `outputs/weights/` — pesos exportados
- `outputs/reports/` — relatorios e notas tecnicas

## Como reproduzir (minimo)
- Decomposicao e pesos: `python run_fm_siren.py`
- Treino inicial: `python train_siren_initial.py`
- Backtest OOS: `python siren_hermetic_backtest.py`

## Observacao
Os relatorios tecnicos completos estao em `outputs/reports/`.
