# Projeto Chronos: Dissecacao Cinematica do EURUSD
> Modelagem deterministica e analise de fase em series temporais financeiras (1971-2026).

Este repositorio documenta a Fase 1 de uma pesquisa profunda sobre inercia e gravidade orbital do EURUSD. O objetivo nao e construir uma estrategia de trade, e sim um estudo de caso de Processamento de Sinais e Dinamica de Sistemas. A pesquisa completa possui mais capitulos; aqui focamos apenas nos que sustentam a tese central, por isso a numeracao nao segue uma ordem completa.

## Conceito central: A Fisica da Inercia Financeira
O preco e tratado como um corpo fisico sujeito a duas forcas:
- Deriva secular (a esteira): capturada pelo filtro Hodrick-Prescott com lambda = 1e10.
- Oscilacao orbital (o bebado): modelada como superposicao de senoides e massas intrinsecas.

A analogia do "Bebado na Esteira" resume a separacao entre tendencia lenta (HP) e movimento browniano (ruido), base de toda a disseccao.

## Equacao de Unificacao (XXVIII)
A formulacao no dominio da massa usa um eixo viajante C_hp(M) e cinco harmonicas senoidais:

```math
P(M) = C_{hp}(M) + \sum_{k=1}^{5} a_k \sin(\omega_k M + \phi_k)
```

Onde M e o eixo de massa intrinseca (cumsum de (High-Low) com direcao), e C_hp(M) corrige o deslocamento secular do eixo gravitacional.

## Principais resultados tecnicos
- Fidelidade do modelo: R2 = 0.9504 (95.04% de variancia explicada) na Equacao de Unificacao (XXVIII), janela completa.
- Tri-Pendulo: 3 senoides no tempo cronologico (periodos otimizados 23.7057, 14.8018, 4.5601 anos) e 5 harmonicas no dominio da massa.
- Zona Morta (H1): o residuo apos remover a macroestrutura converge para H ~= 0.5 em escalas macro na janela oficial, indicando limite do determinismo linear.
- Matriz de Inanicao: 77% do tempo em regimes 50/50 a 60/40 (zona do ruido), ~21% em 70/30, ~1.6% em 80/20.

## Evidencias por capitulo
- XI: Simetria estrutural quase perfeita em contagem de pernas; simetria espacial e temporal proximas de 1.0.
- XII: Dominio estatistico de regimes 50/50 e 60/40 em janelas de 1 ano.
- XIII-A: Tri-Pendulo relevante, mas HP domina o ajuste global; XXVIII supera XXVII com larga margem.
- XVI: Elasticidade do tempo via DFA mostra fase trending no micro e enfraquecimento macro na janela oficial.
- XVII: Hierarquia de massa cronologica extrema (macro >> micro).
- XIX: Ondas leves revertem mais rapido e com maior acerto que ondas pesadas.
- XXII: Orbita HP supera SMA-520; senoide deformada nao aumenta R2 global.
- XXIV: Conservacao 50/50 valida para pips e tempo; falha quando energia e ponderada por volume.

## Dataset
- Fonte: `data/eurusd_h1_ohlc.csv`
- Linhas: 174,932 horas
- Janela completa: 1971-01-04 a 2026-01-08 (FXPro, inclui pre-1999)
- Janela oficial: 1999-01-04 a 2024-12-31

## Documento principal
O paper completo desta fase esta em `paper/o_bebado_na_esteira.md`.

## Conteudo desta pasta
- `paper/o_bebado_na_esteira.md` (paper principal)
- `paper/capitulo_*.md` (capitulos por tema)
- `scripts/` (execucao e reproducao)
- `outputs/` (tabelas e JSON de resultados)
- `outputs/plots/` (graficos gerados pelos scripts)
- `data/eurusd_h1_ohlc.csv` (dataset)
- `requirements.txt` (dependencias)
- `notes/rascunho.md` (processo de trabalho, opcional)

## Reproducao rapida
- Instale dependencias: `pip install -r requirements.txt`
- Execute um capitulo: `python scripts/cap11_brownian_symmetry.py`
- Os resultados vao para `outputs/` e os plots para `outputs/plots/`

## Scripts e saidas
- Cap XI: `scripts/cap11_brownian_symmetry.py`
- Cap XII: `scripts/cap12_time_asymmetry.py`
- Cap XIII-A: `scripts/cap13a_tri_pendulum_suite.py`
- Cap XVI: `scripts/cap16_hurst_dfa.py`
- Cap XVII: `scripts/cap17_chron_inertia.py`
- Cap XIX: `scripts/cap19_low_mass_reactivity.py`
- Cap XXII: `scripts/cap22_dynamic_orbit.py`
- Cap XXIV: `scripts/cap24_thermo_debt.py`

Graficos e tabelas estao nos diretorios `outputs/out_cap11_sweep`, `outputs/out_cap12_full`, `outputs/out_cap13a_full_auto_hp` e similares. Os plots consolidados ficam em `outputs/plots/`.
