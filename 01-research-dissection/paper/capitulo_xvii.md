# Capitulo XVII - Inercia Cronologica

Objetivo: quantificar a massa cronologica (Amplitude x Periodo) por escala e verificar a hierarquia de inercia entre ondas macro e micro.

Script fonte (reproducao): `../scripts/cap17_chron_inertia.py`
Saidas principais:
- Janela completa: `../outputs/out_cap17_full/cap17_summary.json`, `../outputs/out_cap17_full/cap17_mass_table.csv`
- Janela oficial: `../outputs/out_cap17_1999_2024/cap17_summary.json`, `../outputs/out_cap17_1999_2024/cap17_mass_table.csv`

## Dataset usado
- Arquivo: `../data/eurusd_h1_ohlc.csv`
- Janela completa (FXPro): 1971-01-04 a 2026-01-08
- Janela oficial (EURUSD): 1999-01-04 a 2024-12-31

## Metodo (objetivo)
1) Ajuste de senoide unica por periodo (OLS) em preco (pips).
2) Amplitude A e fase extraidas do ajuste.
3) Massa cronologica = Amplitude x Periodo (em horas).
4) Periodos usados:
   - Macro: 33.8y, 14.5y, 3.6y
   - Micro: 8760h (anual), 520h (mensal), 120h (semanal), 24h (diario)

## Resultados - Janela completa (1971-2026)

| Escala | Periodo (h) | Amplitude (pips) | R2 | Massa (A*Periodo) |
| --- | --- | --- | --- | --- |
| macro_33.8y | 296290.8 | 1637.43 | 0.3714 | 485,154,818 |
| macro_14.5y | 127107.0 | 1003.46 | 0.2021 | 127,546,455 |
| macro_3.6y | 31557.6 | 251.74 | 0.0120 | 7,944,193 |
| micro_8760h | 8760.0 | 154.96 | 0.0046 | 1,357,430 |
| micro_520h | 520.0 | 11.83 | 0.0000 | 6,153 |
| micro_120h | 120.0 | 0.39 | 0.0000 | 46.5 |
| micro_24h | 24.0 | 1.20 | 0.0000 | 28.9 |

## Resultados - Janela oficial (1999-2024)

| Escala | Periodo (h) | Amplitude (pips) | R2 | Massa (A*Periodo) |
| --- | --- | --- | --- | --- |
| macro_33.8y | 296290.8 | 2060.38 | 0.5673 | 610,470,920 |
| macro_14.5y | 127107.0 | 1079.06 | 0.2491 | 137,155,634 |
| macro_3.6y | 31557.6 | 321.49 | 0.0210 | 10,145,508 |
| micro_8760h | 8760.0 | 149.10 | 0.0046 | 1,306,083 |
| micro_520h | 520.0 | 6.47 | 0.0000 | 3,365 |
| micro_120h | 120.0 | 1.17 | 0.0000 | 140.7 |
| micro_24h | 24.0 | 0.53 | 0.0000 | 12.7 |

## Veredito do Capitulo XVII
- A hierarquia de massa cronologica e brutal: macro >> micro (ordens de grandeza).
- A massa da onda mestra e centenas de milhoes; a massa da onda diaria e dezenas de unidades.
- A tese de inercia cronologica e CONFIRMADA nas duas janelas.

