# Capitulo XXIV - Divida Termodinamica

Objetivo: verificar a conservacao de energia direcional (50/50) por escala, medindo espaco (pips), tempo (horas) e duas proxies de energia (Joules por tempo e por volume).

Script fonte (reproducao): `../scripts/cap24_thermo_debt.py`
Saidas principais:
- Janela completa: `../outputs/out_cap24_full/cap24_summary.json`, `../outputs/out_cap24_full/cap24_table.csv`
- Janela oficial: `../outputs/out_cap24_1999_2024/cap24_summary.json`, `../outputs/out_cap24_1999_2024/cap24_table.csv`

## Dataset usado
- Arquivo: `../data/eurusd_h1_ohlc.csv`
- Janela completa (FXPro): 1971-01-04 a 2026-01-08
- Janela oficial (EURUSD): 1999-01-04 a 2024-12-31

## Definicoes operacionais
- Ziguezague por thresholds (pips): 15 (micro), 100 (medio), 500 (macro).
- Espaco: amplitude da perna (pips).
- Tempo: duracao da perna (horas).
- Joules (tempo): `amp * horas` (proxy cinetico de esforco).
- Joules (volume): `amp * sum(TickVolume)` dentro da perna (proxy massa-volume).

## Resultados - Janela completa (1971-2026)

| Escala | Pips Up % | Horas Up % | Joules (tempo) Up % | Joules (tick) Up % |
| --- | --- | --- | --- | --- |
| 15 pips | 50.107 | 50.368 | 50.308 | 49.742 |
| 100 pips | 50.304 | 49.875 | 49.342 | 45.588 |
| 500 pips | 51.275 | 50.515 | 48.715 | 34.219 |

## Resultados - Janela oficial (1999-2024)

| Escala | Pips Up % | Horas Up % | Joules (tempo) Up % | Joules (tick) Up % |
| --- | --- | --- | --- | --- |
| 15 pips | 49.972 | 50.316 | 50.037 | 49.513 |
| 100 pips | 49.897 | 49.682 | 48.599 | 44.757 |
| 500 pips | 49.438 | 49.464 | 47.430 | 32.320 |

## Interpretacao objetiva
- Pips e horas permanecem praticamente simetricos (50/50) em todas as escalas.
- A proxy Joules (tempo = amp*horas) tambem permanece proxima de 50/50.
- A proxy Joules (tick volume) apresenta assimetria crescente nas escalas maiores, indicando que o volume nao e distribuido simetricamente entre altas e baixas.

## Veredito do Capitulo XXIV
- A conservacao 50/50 e CONFIRMADA para espaco, tempo e Joules por tempo.
- A conservacao NAO se confirma sob a definicao de Joules ponderada por TickVolume (assimetria material). Isso limita a validade do argumento se a massa for definida estritamente por volume.

