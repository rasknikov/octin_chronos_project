# Capitulo XIX - Reatividade de Baixa Massa

Objetivo: medir a velocidade e a taxa de reversao (90%) em ondas de baixa massa, confirmando que ondas leves revertam mais rapido e com maior acerto.

Script fonte (reproducao): `../scripts/cap19_low_mass_reactivity.py`
Saidas principais:
- Janela completa: `../outputs/out_cap19_full/cap19_summary.json`, `../outputs/out_cap19_full/cap19_groups.csv`
- Janela oficial: `../outputs/out_cap19_1999_2024/cap19_summary.json`, `../outputs/out_cap19_1999_2024/cap19_groups.csv`

## Dataset usado
- Arquivo: `../data/eurusd_h1_ohlc.csv`
- Janela completa (FXPro): 1971-01-04 a 2026-01-08
- Janela oficial (EURUSD): 1999-01-04 a 2024-12-31

## Metodo (objetivo)
1) Extrair ziguezague com swing minimo de 15 pips.
2) Definir onda como expansao entre dois pivots consecutivos.
3) Massa = amplitude (pips) x tempo de expansao (horas).
4) Medir tempo para devolver 90% (snap-back) dentro de 2000 horas.
5) Classificar ondas por quartis de massa (pena, pedra, bigorna).

## Resultados - Janela completa (1971-2026)

| Grupo | Win Rate (90%) | T_expansao mediana (h) | T_reversao mediana (h) | Ratio |
| --- | --- | --- | --- | --- |
| Pena (Q1) | 99.69% | 1.0 | 2.0 | 2.00x |
| Pedra (Q2-Q3) | 98.19% | 4.0 | 4.0 | 1.00x |
| Bigorna (Q4) | 91.90% | 12.0 | 29.0 | 2.42x |

## Resultados - Janela oficial (1999-2024)

| Grupo | Win Rate (90%) | T_expansao mediana (h) | T_reversao mediana (h) | Ratio |
| --- | --- | --- | --- | --- |
| Pena (Q1) | 99.66% | 2.0 | 2.0 | 1.00x |
| Pedra (Q2-Q3) | 98.16% | 5.0 | 4.0 | 0.80x |
| Bigorna (Q4) | 91.85% | 13.0 | 29.0 | 2.23x |

## Veredito do Capitulo XIX
- Ondas leves (pena) possuem reversao quase perfeita e rapida.
- Ondas pesadas (bigorna) revertem mais lentamente e falham mais (taxa ~92%).
- A tese de reatividade de baixa massa e CONFIRMADA nas duas janelas.

