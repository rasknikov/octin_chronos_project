# O Bebado na Esteira - Dissecacao Cinematica do EURUSD

## Nota de escopo
Este paper sintetiza as partes mais importantes de uma pesquisa maior que abrangeu diversas outras informacoes e capitulos. Aqui focamos apenas nos capitulos mais relevantes para provar a tese central. Por isso, a numeracao dos capitulos nao segue uma ordem completa ou contavel.

## Resumo
Este paper formaliza e testa empiricamente a tese de que o mercado de EURUSD H1 apresenta uma estrutura majoritariamente deterministica (senoidal/macro) combinada com um componente residual imprevisivel em tempo cronologico linear. Os capitulos XI, XII, XIII-A, XVI, XVII, XIX, XXII e XXIV sao apresentados com definicoes operacionais, scripts de reproducao e resultados numericos replicaveis. As evidencias apontam simetria estrutural forte (pernas), predominio de regimes 50/50 e 60/40 na matriz de inanicao, existencia de macro-senoides relevantes (Tri-Pendulo), mudancas de fase no Expoente de Hurst em janelas longas, hierarquia de massa cronologica entre macro e micro, alta reatividade em ondas leves, e conservacao 50/50 em pips e tempo. O eixo HP (orbita viajante) surge como base mais forte que SMA-520 quando o objetivo e ajustar o deslocamento secular (inflacao e deriva monetaria).

## Nota sobre HP e o eixo viajante
A Teoria de Tudo no dominio da massa (XXVII) usa intercepto fixo (preco ancora) para somar os pendulos. Isso cria erro estrutural porque preco fixo ignora inflacao, juros e deriva monetaria. Mesmo uma media fixa de massa nao acompanha o deslocamento secular do eixo gravitacional. O filtro Hodrick-Prescott (HP) modela esse eixo viajante como tendencia suave, corrigindo a orbita senoidal na media de massa em pips. Essa e exatamente a correcao proposta pela Teoria Relativistica Fiduciaria (XXVIII), que substitui o intercepto fixo por um eixo C_hp(M) viajante.

## Escopo e dados
- Instrumento: EURUSD H1, OHLC + TickVolume.
- Arquivo: `../data/eurusd_h1_ohlc.csv`.
- Janela completa (FXPro): 1971-01-04 a 2026-01-08.
- Janela oficial (EURUSD): 1999-01-04 a 2024-12-31.
- Observacao: o arquivo contem dados pre-1999. Estes dados devem ser interpretados como serie sintetica/backfilled. A explicacao tecnica mais plausivel e a conversao ECU (pre-1999) -> EUR (pos-1999) usando taxas de conversao fixas na introducao do euro. Por isso, todos os capitulos apresentam duas validacoes: janela completa e janela oficial.

## Reprodutibilidade
Scripts fonte (por capitulo):
- Cap XI: `../scripts/cap11_brownian_symmetry.py`
- Cap XII: `../scripts/cap12_time_asymmetry.py`
- Cap XIII-A: `../scripts/cap13a_tri_pendulum_suite.py`
- Cap XVI: `../scripts/cap16_hurst_dfa.py`
- Cap XVII: `../scripts/cap17_chron_inertia.py`
- Cap XIX: `../scripts/cap19_low_mass_reactivity.py`
- Cap XXII: `../scripts/cap22_dynamic_orbit.py`
- Cap XXIV: `../scripts/cap24_thermo_debt.py`

## Definicoes globais
- Pip: `Close * 10000`.
- Retorno horario: `delta = Close_t - Close_{t-1}` em pips.
- Hora de alta: `delta > 0`. Hora de baixa: `delta < 0`.
- Perna (zigzag): segmento entre pivots; fecha quando ocorre reversao >= `threshold_pips`.
- Equador 520H: `eq_520 = (rolling_max_520 + rolling_min_520) / 2`.
- Orbita base: SMA-520H do preco.
- Orbita viajante: tendencia HP com `lambda = 1e10`.

## Capitulo XI - Paradoxo da Simetria Browniana
Objetivo: testar simetria estrutural (contagem de pernas), simetria espacial (pips) e temporal (horas) em longo prazo.

Script: `../scripts/cap11_brownian_symmetry.py`
Saidas: `../outputs/out_cap11/cap11_summary.json`, `../outputs/out_cap11/cap11_leg_summary.csv`, `../outputs/out_cap11_sweep/cap11_leg_summary.csv`

Resultados - simetria horaria (janela completa):
- Horas de alta: 85,993
- Horas de baixa: 85,130
- Horas flat: 3,809
- Pips de alta (soma de deltas positivos): 928,144.1
- Pips de baixa (soma de deltas negativos, abs): 921,836.6
- Edge temporal: 1.01014
- Edge espacial: 1.00684

Resultados - simetria estrutural por threshold (janela completa):

| threshold_pips | legs_up | legs_down | edge_legs | edge_pips | edge_hours |
| --- | --- | --- | --- | --- | --- |
| 20 | 10147 | 10146 | 1.00010 | 1.00919 | 1.01384 |
| 50 | 3492 | 3491 | 1.00029 | 1.01301 | 1.00279 |
| 100 | 1395 | 1394 | 1.00072 | 1.01868 | 1.01849 |
| 200 | 471 | 471 | 1.00000 | 1.02779 | 1.07787 |

Sweep de thresholds (5 a 500 pips) - maximos desvios absolutos:
- edge_legs: 0.000717 (0.0717%)
- edge_pips: 0.046693 (4.6693%)
- edge_hours: 0.077868 (7.7868%)

Validacao - janela oficial (1999-01-04 a 2024-12-31):
- Edge temporal: 1.01087
- Edge espacial: 0.99814
- edge_legs = 1.00000 para 20, 50, 100 e 200 pips.

Veredito:
- Simetria temporal e espacial: CONFIRMADA.
- Simetria estrutural (contagem de pernas): CONFIRMADA.
- Numero absoluto de pernas depende de threshold e janela; nao e invariavel.

## Capitulo XII - Matriz de Inanicao Temporaria
Objetivo: medir, em janelas de 1 ano, o tempo em regimes 50/50, 60/40, 70/30, 80/20 e 90/10, em relacao ao Equador 520H.

Script: `../scripts/cap12_time_asymmetry.py`
Saidas: `../outputs/out_cap12_full/cap12_distribution.csv`, `../outputs/out_cap12_1999_2024/cap12_distribution.csv`

Definicoes:
- Janela de 1 ano: 6240 horas.
- Proporcao direcional: `pct = mean(state)`.
- Magnitude direcional: `mag = max(pct, 1 - pct)`.
- Bins:
- 50/50: `mag < 0.55`
- 60/40: `0.55 <= mag < 0.65`
- 70/30: `0.65 <= mag < 0.75`
- 80/20: `0.75 <= mag < 0.85`
- 90/10: `mag >= 0.85`

Resultados - janela completa (1971-2026), total 168,173 janelas:

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

Resultados - janela oficial (1999-2024), total 154,696 janelas:

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

Veredito:
- Predominio 50/50 a 60/40: CONFIRMADO.
- Raridade de regimes extremos >= 80/20: CONFIRMADA.

## Capitulo XIII-A - Tri-Pendulo (Suite Completa)
Objetivo: testar o poder explicativo do Tri-Pendulo, com e sem HP, senoides deformadas pela massa, e modelos XXVII e XXVIII em dominio de massa.

Script: `../scripts/cap13a_tri_pendulum_suite.py`
Saidas: `../outputs/out_cap13a_full_auto_hp/cap13a_summary.json`, `../outputs/out_cap13a_1999_2024_auto_hp/cap13a_summary.json`

Definicoes:
- Eixo cronologico em anos: `t_years = (timestamp - t0) / (24*365.25)`.
- Tri-Pendulo: `P(t) = D + sum_{k=1..3} A_k sin(2pi t/P_k + phi_k)`.
- HP trend (lambda = 1e10): `P(t) = HP(t) + residuo`.
- Senoide deformada pela massa:
- Orbita base: SMA-520H do preco.
- Oscilador: `osc = preco - orbita`.
- Tempo de massa: `phi_m = cumsum((High-Low)/median(High-Low))`.
- Dominio da massa (XXVII e XXVIII):
- Direcao: `sign(Close-Open)`.
- Massa por vela: `(High-Low)*direcao`.
- Eixo M(t): `cumsum(massa)`.
- XXVII: superposicao de 5 senoides com intercepto fixo `C=1.13677`.
- XXVIII: superposicao de 5 senoides com intercepto viajante `C_hp`.

Resultados - janela completa (1971-2026):

| Modelo | R2 |
| --- | --- |
| Tri-Pendulo (cronologico, periodos otimizados) | 0.7036 |
| HP somente (lambda 1e10) | 0.9860 |
| HP + Tri-Pendulo (periodos do cronologico) | 0.9861 |
| HP + Tri-Pendulo (periodos otimizados no residual HP) | 0.9870 |
| Orbita SMA-520 (so orbita) | 0.9704 |
| Orbita + senoide rigida | 0.9704 |
| Orbita + senoide deformada pela massa | 0.9704 |
| XXVII (dominio da massa, C fixo) | 0.5687 |
| XXVIII (dominio da massa, C_hp) | 0.9504 |

Periodos otimizados (cronologico):
- P1: 23.7057 anos
- P2: 14.8018 anos
- P3: 4.5601 anos
- R2 da busca amostrada: 0.70336

Resultados - janela oficial (1999-2024):

| Modelo | R2 |
| --- | --- |
| Tri-Pendulo (cronologico, periodos otimizados) | 0.8309 |
| HP somente (lambda 1e10) | 0.9931 |
| HP + Tri-Pendulo (periodos do cronologico) | 0.9931 |
| HP + Tri-Pendulo (periodos otimizados no residual HP) | 0.9931 |
| Orbita SMA-520 (so orbita) | 0.9856 |
| Orbita + senoide rigida | 0.9856 |
| Orbita + senoide deformada pela massa | 0.9856 |
| XXVII (dominio da massa, C fixo) | 0.5953 |
| XXVIII (dominio da massa, C_hp) | 0.9747 |

Periodos otimizados (cronologico):
- P1: 23.7057 anos
- P2: 13.1577 anos
- P3: 5.1299 anos
- R2 da busca amostrada: 0.83093

Veredito:
- Tri-Pendulo cronologico e estruturalmente relevante, mas o R2 depende da janela.
- HP domina o ajuste global; Tri-Pendulo agrega ganho marginal sobre HP.
- XXVIII supera XXVII com larga margem no dominio da massa.

## Capitulo XVI - Elasticidade do Tempo (Hurst via DFA)
Objetivo: medir o Expoente de Hurst (H) no residuo da zona morta via DFA e verificar mudanca de fase entre curto prazo e macro.

Script: `../scripts/cap16_hurst_dfa.py`
Saidas: `../outputs/out_cap16_dfa_full/cap16_dfa_hurst.csv`, `../outputs/out_cap16_dfa_1999_2024/cap16_dfa_hurst.csv`

Metodo:
- Macro removida por Tri-Pendulo (periodos otimizados por varredura).
- Residuo = preco - macro_fit, em pips.
- DFA ordem 1 com escalas log-espacadas, evitando escalas < 4.
- Escopos em horas: 2-24, 24-120, 120-520, 520-6240.

Resultados - janela completa (1971-2026):
- Macro removida: 23.7057 / 14.8018 / 4.5601 anos (R2 macro = 0.7036)

| Escopo | H (DFA) | Classificacao |
| --- | --- | --- |
| 2H-24H | 0.5657 | trending |
| 24H-120H | 0.5236 | trending |
| 120H-520H | 0.5103 | trending |
| 520H-6240H | 0.4823 | mean_reverting |

Resultados - janela oficial (1999-2024):
- Macro removida: 23.7057 / 13.1577 / 5.1299 anos (R2 macro = 0.8309)

| Escopo | H (DFA) | Classificacao |
| --- | --- | --- |
| 2H-24H | 0.5698 | trending |
| 24H-120H | 0.4974 | random_walk |
| 120H-520H | 0.4969 | random_walk |
| 520H-6240H | 0.5040 | random_walk |

Veredito:
- Mudanca de fase (curto > 0.5 vs macro < 0.5) CONFIRMADA na janela completa.
- Na janela oficial, o macro se aproxima de 0.5; reversao forte nao se confirma.

## Capitulo XVII - Inercia Cronologica
Objetivo: quantificar massa cronologica (Amplitude x Periodo) por escala e verificar hierarquia de inercia.

Script: `../scripts/cap17_chron_inertia.py`
Saidas: `../outputs/out_cap17_full/cap17_mass_table.csv`, `../outputs/out_cap17_1999_2024/cap17_mass_table.csv`

Metodo:
- Ajuste de senoide unica por periodo (OLS) em pips.
- Massa cronologica = Amplitude x Periodo (horas).
- Periodos: macro 33.8y, 14.5y, 3.6y; micro 8760h, 520h, 120h, 24h.

Resultados - janela completa (1971-2026):

| Escala | Periodo (h) | Amplitude (pips) | R2 | Massa (A*Periodo) |
| --- | --- | --- | --- | --- |
| macro_33.8y | 296290.8 | 1637.43 | 0.3714 | 485,154,818 |
| macro_14.5y | 127107.0 | 1003.46 | 0.2021 | 127,546,455 |
| macro_3.6y | 31557.6 | 251.74 | 0.0120 | 7,944,193 |
| micro_8760h | 8760.0 | 154.96 | 0.0046 | 1,357,430 |
| micro_520h | 520.0 | 11.83 | 0.0000 | 6,153 |
| micro_120h | 120.0 | 0.39 | 0.0000 | 46.5 |
| micro_24h | 24.0 | 1.20 | 0.0000 | 28.9 |

Resultados - janela oficial (1999-2024):

| Escala | Periodo (h) | Amplitude (pips) | R2 | Massa (A*Periodo) |
| --- | --- | --- | --- | --- |
| macro_33.8y | 296290.8 | 2060.38 | 0.5673 | 610,470,920 |
| macro_14.5y | 127107.0 | 1079.06 | 0.2491 | 137,155,634 |
| macro_3.6y | 31557.6 | 321.49 | 0.0210 | 10,145,508 |
| micro_8760h | 8760.0 | 149.10 | 0.0046 | 1,306,083 |
| micro_520h | 520.0 | 6.47 | 0.0000 | 3,365 |
| micro_120h | 120.0 | 1.17 | 0.0000 | 140.7 |
| micro_24h | 24.0 | 0.53 | 0.0000 | 12.7 |

Veredito:
- Hierarquia de massa cronologica e extrema: macro >> micro.
- A tese de inercia cronologica e CONFIRMADA em ambas as janelas.

## Capitulo XIX - Reatividade de Baixa Massa
Objetivo: medir velocidade e taxa de reversao (90%) em ondas de baixa massa.

Script: `../scripts/cap19_low_mass_reactivity.py`
Saidas: `../outputs/out_cap19_full/cap19_groups.csv`, `../outputs/out_cap19_1999_2024/cap19_groups.csv`

Metodo:
- Ziguezague com swing minimo 15 pips.
- Onda = expansao entre pivots consecutivos.
- Massa = amplitude (pips) x tempo de expansao (horas).
- Reversao: devolver 90% dentro de 2000 horas.
- Quartis: pena (Q1), pedra (Q2-Q3), bigorna (Q4).

Resultados - janela completa (1971-2026):

| Grupo | Win Rate (90%) | T_expansao mediana (h) | T_reversao mediana (h) | Ratio |
| --- | --- | --- | --- | --- |
| Pena (Q1) | 99.69% | 1.0 | 2.0 | 2.00x |
| Pedra (Q2-Q3) | 98.19% | 4.0 | 4.0 | 1.00x |
| Bigorna (Q4) | 91.90% | 12.0 | 29.0 | 2.42x |

Resultados - janela oficial (1999-2024):

| Grupo | Win Rate (90%) | T_expansao mediana (h) | T_reversao mediana (h) | Ratio |
| --- | --- | --- | --- | --- |
| Pena (Q1) | 99.66% | 2.0 | 2.0 | 1.00x |
| Pedra (Q2-Q3) | 98.16% | 5.0 | 4.0 | 0.80x |
| Bigorna (Q4) | 91.85% | 13.0 | 29.0 | 2.23x |

Veredito:
- Ondas leves revertem mais rapido e com maior acerto.
- Ondas pesadas revertem mais lentamente e falham mais.
- A tese de reatividade de baixa massa e CONFIRMADA.

## Capitulo XXII - Orbita Dinamica
Objetivo: medir o ganho de modelar orbita dinamica (SMA-520) e senoide deformada pela massa, comparando com HP.

Script: `../scripts/cap22_dynamic_orbit.py`
Saidas: `../outputs/out_cap22_full/cap22_summary.json`, `../outputs/out_cap22_1999_2024/cap22_summary.json`

Metodo:
- Orbita base: SMA-520H do preco.
- Oscilador: preco - orbita.
- Senoide mensal (520H) ajustada em tempo rigido e tempo de massa.
- Comparacao com eixo HP (Hodrick-Prescott, lambda = 1e10).

Resultados - janela completa (1971-2026):

| Modelo | R2 |
| --- | --- |
| HP (orbita viajante) | 0.9860 |
| SMA-520 (orbita base) | 0.9704 |
| SMA-520 + senoide rigida | 0.9704 |
| SMA-520 + senoide deformada (massa) | 0.9704 |

Resultados - janela oficial (1999-2024):

| Modelo | R2 |
| --- | --- |
| HP (orbita viajante) | 0.9931 |
| SMA-520 (orbita base) | 0.9856 |
| SMA-520 + senoide rigida | 0.9856 |
| SMA-520 + senoide deformada (massa) | 0.9856 |

Interpretacao fisica (massa vs relogio):
A massa atua como estabilizador do relogio cronologico. Ondas pesadas preservam a cadencia temporal e se aproximam de um movimento senoidal perfeito no eixo do tempo. Ondas leves possuem baixa inercia, sofrem deformacao temporal e exibem maior volatilidade aparente. Quanto maior a massa, mais estavel o relogio; quanto menor a massa, mais elastico e erratico o movimento.

Veredito:
- O eixo HP supera SMA-520 em explicacao global.
- A senoide deformada nao aumenta o R2 global nesta medicao.
- A orbita dinamica e valida, mas HP e a base mais forte.

## Capitulo XXIV - Divida Termodinamica
Objetivo: verificar conservacao 50/50 por escala medindo espaco (pips), tempo (horas) e duas proxies de energia.

Script: `../scripts/cap24_thermo_debt.py`
Saidas: `../outputs/out_cap24_full/cap24_table.csv`, `../outputs/out_cap24_1999_2024/cap24_table.csv`

Definicoes:
- Ziguezague por thresholds (pips): 15 (micro), 100 (medio), 500 (macro).
- Espaco: amplitude da perna (pips).
- Tempo: duracao da perna (horas).
- Joules (tempo): `amp * horas`.
- Joules (volume): `amp * sum(TickVolume)`.

Resultados - janela completa (1971-2026):

| Escala | Pips Up % | Horas Up % | Joules (tempo) Up % | Joules (tick) Up % |
| --- | --- | --- | --- | --- |
| 15 pips | 50.107 | 50.368 | 50.308 | 49.742 |
| 100 pips | 50.304 | 49.875 | 49.342 | 45.588 |
| 500 pips | 51.275 | 50.515 | 48.715 | 34.219 |

Resultados - janela oficial (1999-2024):

| Escala | Pips Up % | Horas Up % | Joules (tempo) Up % | Joules (tick) Up % |
| --- | --- | --- | --- | --- |
| 15 pips | 49.972 | 50.316 | 50.037 | 49.513 |
| 100 pips | 49.897 | 49.682 | 48.599 | 44.757 |
| 500 pips | 49.438 | 49.464 | 47.430 | 32.320 |

Interpretacao:
- Pips e horas permanecem praticamente simetricos (50/50) em todas as escalas.
- Joules por tempo tambem permanece proximo de 50/50.
- Joules ponderado por tick volume apresenta assimetria crescente nas escalas maiores.

Veredito:
- Conservacao 50/50 CONFIRMADA para pips, horas e joules por tempo.
- Conservacao NAO confirmada para joules ponderado por TickVolume.

## Conclusao geral
1) A simetria estrutural de pernas e robusta em todo o historico.
2) A Matriz de Inanicao confirma que o mercado passa a maior parte do tempo em regimes proximos a 50/50 e 60/40.
3) O Tri-Pendulo e relevante, mas o eixo HP domina o ajuste global e explica o deslocamento secular.
4) A elasticidade do tempo via DFA mostra mudanca de fase na janela completa e enfraquecimento na janela oficial.
5) A hierarquia de massa cronologica e clara e explica a diferenca entre macro e micro.
6) Ondas leves apresentam reversao rapida; ondas pesadas reagem lentamente.
7) A conservacao 50/50 e valida para espaco e tempo, mas falha quando energia e ponderada por volume.

Estado final: as teses principais se confirmam com alta consistencia, com excecoes localizadas (Hurst macro na janela oficial e joules por volume). O mercado exibe determinismo estrutural de longo prazo combinado com um residuo imprevisivel em tempo cronologico linear.
