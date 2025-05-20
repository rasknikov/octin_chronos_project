# Capitulo XVI - Elasticidade do Tempo (Hurst via DFA)

Objetivo: medir o Expoente de Hurst (H) no residuo da Zona Morta usando DFA (Detrended Fluctuation Analysis), metodo mais robusto para series nao-estacionarias, e verificar a mudanca de fase entre curto prazo e macro.

Script fonte (reproducao): `../scripts/cap16_hurst_dfa.py`
Saidas principais:
- Janela completa: `../outputs/out_cap16_dfa_full/cap16_dfa_summary.json`, `../outputs/out_cap16_dfa_full/cap16_dfa_hurst.csv`
- Janela oficial: `../outputs/out_cap16_dfa_1999_2024/cap16_dfa_summary.json`, `../outputs/out_cap16_dfa_1999_2024/cap16_dfa_hurst.csv`

## Dataset usado
- Arquivo: `../data/eurusd_h1_ohlc.csv`
- Janela completa (FXPro): 1971-01-04 a 2026-01-08
- Janela oficial (EURUSD): 1999-01-04 a 2024-12-31

## Metodo (objetivo)
1) Ajuste da macro-estrutura via Tri-Pendulo (periodos otimizados por varredura automatica).
2) Residuo = preco - macro_fit, convertido para pips.
3) DFA (ordem 1) no residuo, com escalas log-espacadas por faixa; escalas pequenas (<4) sao evitadas para nao gerar ajuste degenerado.
4) Escopos avaliados (em horas):
   - Micro intraday: 2H a 24H
   - Swing semanal: 24H a 120H
   - Fissura mensal: 120H a 520H
   - Macro orbita: 520H a 6240H

## Resultados - Janela completa (1971-2026)
Macro removida com periodos: 23.7057 / 14.8018 / 4.5601 anos (R2 macro = 0.7036)

| Escopo | H (DFA) | Classificacao |
| --- | --- | --- |
| 2H-24H | 0.5657 | trending |
| 24H-120H | 0.5236 | trending |
| 120H-520H | 0.5103 | trending |
| 520H-6240H | 0.4823 | mean_reverting |

Conclusao objetiva: curto prazo permanece >0.5 (momentum) e o regime macro cai abaixo de 0.5 (reversao), alinhado ao capitulo para a janela completa.

## Resultados - Janela oficial (1999-01-04 a 2024-12-31)
Macro removida com periodos: 23.7057 / 13.1577 / 5.1299 anos (R2 macro = 0.8309)

| Escopo | H (DFA) | Classificacao |
| --- | --- | --- |
| 2H-24H | 0.5698 | trending |
| 24H-120H | 0.4974 | random_walk |
| 120H-520H | 0.4969 | random_walk |
| 520H-6240H | 0.5040 | random_walk |

Conclusao objetiva: na janela oficial, o momentum curto existe apenas no micro (2H-24H). As escalas maiores ficam proximas de 0.5; a reversao macro nao se confirma com a mesma forca vista na janela completa.

## Veredito do Capitulo XVI
- A mudanca de fase (curto > 0.5 vs macro < 0.5) e CONFIRMADA na janela completa.
- Na janela oficial, a mudanca de fase fica mais fraca; o macro orbita aproxima 0.5 e nao valida reversao forte.

