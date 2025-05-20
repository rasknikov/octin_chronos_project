# Capitulo XI - Paradoxo da Simetria Browniana

## Adendo - Janela de dados (FXPro) e pre-1999
Esta base (H1) e a janela historica disponibilizada pela corretora FXPro. O arquivo contem dados anteriores a 1999, embora o euro tenha sido introduzido oficialmente em 1 de janeiro de 1999.

Portanto, os registros pre-1999 devem ser entendidos como serie sintetica/backfilled. Uma pratica comum para construir series continuas e converter a ECU (pre-1999) e o EUR (pos-1999) usando taxas de conversao fixas na introducao do euro; adotamos essa interpretacao como a explicacao tecnica mais plausivel para o backfill.

Para evitar ambiguidade, abaixo apresentamos duas validacoes:
1) Janela completa do dataset FXPro (inclui pre-1999).
2) Janela oficial do EURUSD (primeiro registro na base: 1999-01-04) ate 2024-12-31.

Objetivo: testar se a simetria macro (tempo e espaco) e a simetria estrutural (contagem de pernas) se mantem no longo prazo.

Script fonte (reproducao): `../scripts/cap11_brownian_symmetry.py`
Saidas principais: `../outputs/out_cap11/cap11_summary.json` e `../outputs/out_cap11/cap11_leg_summary.csv`

## Dataset usado
- Arquivo: `../data/eurusd_h1_ohlc.csv`
- Linhas: 174,932
- Janela: 1971-01-04 00:00:00 ate 2026-01-08 01:00:00
- Observacao: o paper original cita 1971-2024. Esta execucao inclui dados ate 2026-01-08.

## Definicoes operacionais
- Pip: `Close * 10000`.
- Retorno horario: `delta = Close_t - Close_{t-1}` em pips.
- Hora de alta: `delta > 0`. Hora de baixa: `delta < 0`. Hora flat: `delta = 0`.
- Simetria temporal: `edge_time = horas_up / horas_down`.
- Simetria espacial: `edge_space = pips_up / pips_down`.
- Perna (zigzag): segmento entre pivots, fechado quando ocorre reversao >= `threshold_pips`.
- O ultimo segmento aberto e ignorado para evitar vies.

## Metodo
1) Medir simetria horaria (tempo e espaco) com deltas hora-a-hora.
2) Medir simetria estrutural por zigzag em multiplos thresholds (20, 50, 100, 200 pips).
3) Registrar edge ratios e diferenca absoluta entre direcoes.

## Resultados - Simetria horaria (tempo e espaco)
- Horas de alta: 85,993
- Horas de baixa: 85,130
- Horas flat: 3,809
- Pips de alta (soma de deltas positivos): 928,144.1
- Pips de baixa (soma de deltas negativos, abs): 921,836.6
- Edge temporal: 1.01014
- Edge espacial: 1.00684

Conclusao objetiva: a assimetria de longo prazo e pequena (cerca de 0.7% a 1.0%). A simetria temporal e espacial e confirmada nesta janela.

## Resultados - Simetria estrutural (zigzag)
Tabela com thresholds e simetria de pernas:

| threshold_pips | legs_up | legs_down | edge_legs | edge_pips | edge_hours |
| --- | --- | --- | --- | --- | --- |
| 20 | 10147 | 10146 | 1.00010 | 1.00919 | 1.01384 |
| 50 | 3492 | 3491 | 1.00029 | 1.01301 | 1.00279 |
| 100 | 1395 | 1394 | 1.00072 | 1.01868 | 1.01849 |
| 200 | 471 | 471 | 1.00000 | 1.02779 | 1.07787 |

Conclusao objetiva: a contagem de pernas e praticamente simetrica para todos os thresholds. A simetria estrutural e confirmada.

## Sweep de thresholds (5 a 500 pips)
Script: `../scripts/cap11_brownian_symmetry.py`
Saidas: `../outputs/out_cap11_sweep/cap11_leg_summary.csv` e `../outputs/out_cap11_sweep/cap11_edge_ratios.png`

Tabela resumida (edge ratios):

| threshold_pips | edge_legs | edge_pips | edge_hours |
| --- | --- | --- | --- |
| 5 | 1.000035 | 1.007155 | 1.020164 |
| 10 | 1.000053 | 1.007754 | 1.021285 |
| 15 | 1.000074 | 1.008496 | 1.021079 |
| 20 | 1.000099 | 1.009189 | 1.013841 |
| 30 | 1.000152 | 1.010497 | 1.004470 |
| 40 | 1.000215 | 1.011770 | 1.004654 |
| 50 | 1.000286 | 1.013011 | 1.002794 |
| 60 | 1.000357 | 1.014094 | 1.018909 |
| 80 | 1.000521 | 1.016437 | 1.021227 |
| 100 | 1.000717 | 1.018675 | 1.018495 |
| 150 | 1.000000 | 1.022925 | 1.026747 |
| 200 | 1.000000 | 1.027788 | 1.077868 |
| 300 | 1.000000 | 1.036786 | 1.046182 |
| 400 | 1.000000 | 1.045597 | 0.947246 |
| 500 | 1.000000 | 1.046693 | 1.015461 |

Maximos desvios absolutos da simetria (|edge - 1.0|):
- edge_legs: 0.000717 (0.0717%)
- edge_pips: 0.046693 (4.6693%)
- edge_hours: 0.077868 (7.7868%)

Conclusao objetiva do sweep: a simetria estrutural (edge_legs) permanece essencialmente perfeita em todos os thresholds testados. A simetria espacial e temporal permanece proxima de 1.0, com maior variancia em thresholds altos (amostra menor).

## Validacao na janela oficial (1999-01-04 a 2024-12-31)
Saidas: `../outputs/out_cap11_1999_2024/cap11_summary.json` e `../outputs/out_cap11_1999_2024/cap11_leg_summary.csv`

Simetria horaria (tempo e espaco):
- Horas de alta: 79,329
- Horas de baixa: 78,476
- Horas flat: 3,650
- Pips de alta (soma de deltas positivos): 742,543.5
- Pips de baixa (soma de deltas negativos, abs): 743,927.6
- Edge temporal: 1.01087
- Edge espacial: 0.99814

Simetria estrutural (zigzag):

| threshold_pips | legs_up | legs_down | edge_legs | edge_pips | edge_hours |
| --- | --- | --- | --- | --- | --- |
| 20 | 8725 | 8725 | 1.00000 | 0.99733 | 1.01223 |
| 50 | 2714 | 2714 | 1.00000 | 0.99612 | 0.99884 |
| 100 | 1010 | 1010 | 1.00000 | 0.99481 | 1.00908 |
| 200 | 303 | 303 | 1.00000 | 0.99109 | 1.06639 |

Conclusao objetiva: mesmo na janela oficial, a simetria estrutural (contagem de pernas) e praticamente perfeita; a simetria espacial e temporal permanece proxima de 1.0.

## Checagem de consistencia com o paper (1971-2024)
Execucao adicional com `--end 2024-12-31` e `threshold_pips=60`:
- legs_up: 2,743
- legs_down: 2,742
- count_legs: 5,485
- edge_legs: 1.00036

Isso mostra que o numero absoluto de pernas depende do threshold e do corte temporal. A simetria (up vs down) permanece, mas o numero exato (ex.: ~5,447) nao e invariavel.

## Veredito do Capitulo XI
- Parte A (simetria temporal e espacial): CONFIRMADA.
- Parte B (simetria estrutural de pernas): CONFIRMADA.
- Numero absoluto de pernas (ex.: 5,447): NAO REPRODUZIDO com threshold 50 e janela ate 2026. O valor depende do threshold e do intervalo de dados.


