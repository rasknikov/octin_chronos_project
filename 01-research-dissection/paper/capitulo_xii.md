# Capitulo XII - Matriz de Inanicao Temporaria

Objetivo: medir, em janelas de 1 ano, quanto tempo o mercado permanece em regimes 50/50, 60/40, 70/30 e 80/20 quando observado em relacao ao Equador 520H.

Script fonte (reproducao): `../scripts/cap12_time_asymmetry.py`
Saidas principais:
- Janela completa: `../outputs/out_cap12_full/cap12_summary.json`, `../outputs/out_cap12_full/cap12_bins.csv`, `../outputs/out_cap12_full/cap12_distribution.csv`
- Janela oficial: `../outputs/out_cap12_1999_2024/cap12_summary.json`, `../outputs/out_cap12_1999_2024/cap12_bins.csv`, `../outputs/out_cap12_1999_2024/cap12_distribution.csv`

## Dataset usado
- Arquivo: `../data/eurusd_h1_ohlc.csv`
- Janela completa (FXPro): 1971-01-04 a 2026-01-08
- Janela oficial (EURUSD): 1999-01-04 a 2024-12-31

## Definicoes operacionais
- Equador 520H: `eq_520 = (rolling_max_520 + rolling_min_520) / 2`.
- Estado binario: `state = 1` quando `Close > eq_520`, `0` caso contrario.
- Janela de 1 ano: `rolling_window = 6240` horas.
- Proporcao direcional da janela: `pct = mean(state)`.
- Magnitude direcional: `mag = max(pct, 1 - pct)`.
- Bins:
  - 50/50: `mag < 0.55`
  - 60/40: `0.55 <= mag < 0.65`
  - 70/30: `0.65 <= mag < 0.75`
  - 80/20: `0.75 <= mag < 0.85`
  - 90/10: `mag >= 0.85`

## Metodo
1) Calcular o Equador 520H no historico completo.
2) Converter a serie em estado binario (acima/abaixo do Equador).
3) Calcular, para cada hora, a proporcao de tempo acima do Equador nas ultimas 6.240 horas.
4) Classificar cada janela no bin correspondente e medir a distribuicao percentual.

## Resultados - Janela completa (1971-2026)
Total de amostras (janelas): 168,173

Distribuicao por bin:

| bin | percent (%) |
| --- | --- |
| 50/50 | 27.7482 |
| 60/40 | 49.3623 |
| 70/30 | 21.2799 |
| 80/20 | 1.6097 |
| 90/10 | 0.0000 |

Agregados:
- Zona do Ruido (50/50 a 60/40): 77.1105%
- Zona de Tendencia Pesada (70/30): 21.2799%
- Zona Extrema (80/20 ou 90/10): 1.6097%

Conclusao objetiva: a distribuicao reproduz com precisao a tese do capitulo (77.1%, 21.3%, 1.6%).

Arquivos de apoio:
- `../outputs/out_cap12_full/cap12_bins.png`

## Resultados - Janela oficial (1999-01-04 a 2024-12-31)
Total de amostras (janelas): 154,696

Distribuicao por bin:

| bin | percent (%) |
| --- | --- |
| 50/50 | 28.4726 |
| 60/40 | 49.3924 |
| 70/30 | 20.3851 |
| 80/20 | 1.7499 |
| 90/10 | 0.0000 |

Agregados:
- Zona do Ruido (50/50 a 60/40): 77.8650%
- Zona de Tendencia Pesada (70/30): 20.3851%
- Zona Extrema (80/20 ou 90/10): 1.7499%

Conclusao objetiva: na janela oficial, a distribuicao permanece na mesma ordem de grandeza. A tese de inaniacao temporal e confirmada, com pequenas variacoes numericas.

Arquivos de apoio:
- `../outputs/out_cap12_1999_2024/cap12_bins.png`

## Veredito do Capitulo XII
- A Matriz de Inanicao (predominio 50/50-60/40) e CONFIRMADA.
- A raridade de regimes extremos (>= 80/20) e CONFIRMADA.
- A janela oficial confirma a tese com variacoes menores que 1 ponto percentual.

