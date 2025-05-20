# Capitulo XIII-A - Tri-Pendulo (Suite Completa)

Objetivo: testar o poder explicativo do Tri-Pendulo em varias configuracoes, incluindo HP, senoides deformadas pela massa, e os modelos XXVII e XXVIII em dominio de massa.

Script fonte (reproducao): `../scripts/cap13a_tri_pendulum_suite.py`
Saidas principais:
- Janela completa: `../outputs/out_cap13a_full_auto_hp/cap13a_summary.json`
- Janela oficial: `../outputs/out_cap13a_1999_2024_auto_hp/cap13a_summary.json`

## Por que usamos HP (contexto fisico)
A Teoria de Tudo no dominio da massa (XXVII) usa um intercepto fixo (preco ancora) para somar os pendulos. Isso cria um erro estrutural: preco fixo ignora inflacao, juros e a deriva monetaria do proprio sistema fiduciario. Mesmo uma media fixa ou constante de massa nao acompanha o deslocamento secular do eixo gravitacional. O filtro Hodrick-Prescott (HP) modela esse eixo viajante como tendencia suave, corrigindo a orbita senoidal na media de massa em pips. Em termos fisicos, o HP fornece o centro dinamico em torno do qual a senoide deve oscilar. Essa e exatamente a correcao proposta pela Teoria Relativistica Fiduciaria (XXVIII), que substitui o intercepto fixo por um eixo C_hp(M) viajante. Portanto: XXVII e a hipotese rigida; XXVIII e a correcao relativistica que alinha a orbita ao mundo inflacionario real.

## Dataset usado
- Arquivo: `../data/eurusd_h1_ohlc.csv`
- Janela completa (FXPro): 1971-01-04 a 2026-01-08
- Janela oficial (EURUSD): 1999-01-04 a 2024-12-31

## Definicoes operacionais
- Eixo cronologico em anos: `t_years = (timestamp - t0) / (24*365.25)`.
- Tri-Pendulo (cronologico): `P(t) = D + sum_{k=1..3} A_k sin(2pi t/P_k + phi_k)`.
- HP trend (lambda = 1e10): `P(t) = HP(t) + residuo`.
- Senoide deformada pela massa (FM):
  - Orbita base: SMA-520H do preco.
  - Oscilador: `osc = preco - orbita`.
  - Tempo de massa: `phi_m = cumsum((High-Low)/median(High-Low))`.
  - Ajuste de senoide mensal (520H) em `t` (rigida) e em `phi_m` (deformada).
- Dominio da massa (XXVII / XXVIII):
  - Direcao: `sign(Close-Open)`.
  - Massa por vela: `(High-Low)*direcao`.
  - Eixo M(t): `cumsum(massa)`.
  - XXVII: superposicao de 5 senoides em M(t) com intercepto fixo `C=1.13677`.
  - XXVIII: superposicao de 5 senoides em M(t) com intercepto viajante `C_hp` (HP filter).
  - Ajuste via `curve_fit` em amostra (step=4) para viabilidade computacional.

## Resultados - Janela completa (1971-2026)

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

Observacoes objetivas:
- O Tri-Pendulo cronologico (periodos otimizados) explica 70.36% do preco no periodo completo.
- O HP captura quase toda a variacao; a adicao do Tri-Pendulo ao HP agrega ganho marginal.
- A otimizacao direta no residual HP produz ganho adicional pequeno (0.9861 -> 0.9870).
- A senoide deformada pela massa tem ganho marginal sobre a orbita simples no periodo completo.
- No dominio da massa, XXVII (C fixo) fica proximo de 0.57, enquanto XXVIII (C_hp) sobe para ~0.95.

Periodos otimizados (varredura automatica):
- P1: 23.7057 anos
- P2: 14.8018 anos
- P3: 4.5601 anos
- R2 da busca amostrada: 0.70336

Periodos otimizados no residual HP:
- P1: 8.2157 anos
- P2: 7.3031 anos
- P3: 6.4919 anos
- R2 da busca amostrada (residual HP): 0.06629

## Resultados - Janela oficial (1999-01-04 a 2024-12-31)

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

Observacoes objetivas:
- O Tri-Pendulo cronologico (periodos otimizados) sobe para 83.09% na janela oficial.
- O HP domina novamente; o ganho incremental do Tri-Pendulo e residual.
- A otimizacao direta no residual HP nao altera o R2 em escala significativa nesta janela.
- XXVIII confirma ganho forte ao permitir intercepto viajante no dominio da massa.

Periodos otimizados (varredura automatica):
- P1: 23.7057 anos
- P2: 13.1577 anos
- P3: 5.1299 anos
- R2 da busca amostrada: 0.83093

Periodos otimizados no residual HP:
- P1: 21.0726 anos
- P2: 9.2422 anos
- P3: 5.1299 anos
- R2 da busca amostrada (residual HP): 0.000009

## Veredito do Capitulo XIII-A
- O Tri-Pendulo cronologico e confirmado como estrutura relevante, mas o R2 depende da janela temporal.
- A filtragem HP aumenta drasticamente o ajuste global (dominante sobre as senoides).
- No dominio da massa, XXVIII supera XXVII com larga margem, alinhado ao manifesto.


