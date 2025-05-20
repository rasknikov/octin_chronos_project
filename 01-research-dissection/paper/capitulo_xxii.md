# Capitulo XXII - Orbita Dinamica

Objetivo: medir o ganho de modelar a orbita dinamica (SMA-520) e a senoide deformada pela massa, e comparar com o eixo HP (orbita viajante).

Script fonte (reproducao): `../scripts/cap22_dynamic_orbit.py`
Saidas principais:
- Janela completa: `../outputs/out_cap22_full/cap22_summary.json`
- Janela oficial: `../outputs/out_cap22_1999_2024/cap22_summary.json`

## Dataset usado
- Arquivo: `../data/eurusd_h1_ohlc.csv`
- Janela completa (FXPro): 1971-01-04 a 2026-01-08
- Janela oficial (EURUSD): 1999-01-04 a 2024-12-31

## Metodo (objetivo)
1) Orbita base: SMA-520H do preco.
2) Oscilador: preco - orbita.
3) Senoide mensal (520H) ajustada em tempo rigido e em tempo de massa (phi_m).
4) Comparacao com eixo HP (filtro Hodrick-Prescott, lambda = 1e10).

## Resultados - Janela completa (1971-2026)

| Modelo | R2 |
| --- | --- |
| HP (orbita viajante) | 0.9860 |
| SMA-520 (orbita base) | 0.9704 |
| SMA-520 + senoide rigida | 0.9704 |
| SMA-520 + senoide deformada (massa) | 0.9704 |

## Resultados - Janela oficial (1999-2024)

| Modelo | R2 |
| --- | --- |
| HP (orbita viajante) | 0.9931 |
| SMA-520 (orbita base) | 0.9856 |
| SMA-520 + senoide rigida | 0.9856 |
| SMA-520 + senoide deformada (massa) | 0.9856 |

## Veredito do Capitulo XXII
- O eixo HP supera a SMA-520 em explicacao global (orbita viajante mais adequada).
- A senoide deformada pela massa nao aumenta R2 de forma material nesta medicao global.
- A tese de orbita dinamica permanece valida, mas a evidencia quantitativa favorece a orbita HP como base mais forte.

## Interpretacao fisica (massa vs relogio)
A massa atua como estabilizador do relogio cronologico. Ondas pesadas preservam a cadencia temporal e se aproximam de um movimento senoidal perfeito no eixo do tempo. Ondas leves possuem baixa inercia, sofrem deformacao temporal e exibem maior volatilidade aparente. Portanto: quanto maior a massa, mais estavel o relogio; quanto menor a massa, mais elastico e erratico o movimento.

