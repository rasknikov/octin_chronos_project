# Arquitetura: Fractal Frequency Modulation (FM) SIREN (V3.0)

Este documento define o blueprint matemático de uma arquitetura neural customizada que abando a MLP tradicional (Linear $\rightarrow$ ReLU) para abraçar internamente a Função de Weierstrass através de **Sinusoidal Representation Networks (SIRENs)** moduladas pelo cálculo de FM (Frequency Modulation).

---

## 1. O Fim da "Linha Reta" (A FFN Não-Linear)

MLPs tradicionais usam o Somatório de Pesos Comum ($Z = \sum X \cdot W + b$) passando por uma ativação em forma de cotovelo (ReLU) ou S (Tanh). O gradiente tenta otimizar os eixos para formar retas que, somadas, aproximam a curva do EURUSD de forma burra (interpolação linear).

### O Novo Perceptron (O Oscilador FM)
O novo neurônio não emite "parâmetros" para uma equação externa (como a PINN V2). **O neurônio *É* a equação.** 

Equação interna da Camada $L$:
$$H^{(L)} = \sin\left( \omega_0 \cdot (H^{(L-1)} W^{(L)}) + \phi^{(L)} \right)$$

Ao passarmos a fase integral $\Phi(t) = \int \text{ATR}(\tau) d\tau$ direto como $X$ para a primeira matriz, os pesos $W^{(1)}$ assumem instantaneamente a identidade de **Frequências Iniciais ($f_k$)**, e os bias $b$ assumem a identidade de **Fases ($\phi_k$)**.

**O Pulo do Gato (Modulação Cross-Fase):**
Ao jogarmos uma onda $H^{(1)}$ dentro do argumento do Sênico do próximo neurônio $H^{(2)}$, criamos um **Sintetizador FM Matemático**. A matemática prova (via Expansão de Bessel) que o seno de um seno gera *infinitos harmônicos orgânicos* que interagem em ressonância. A arquitetura modela diretamente a distorção e os espinhos da Série de Weierstrass sem que tenhamos que definir estaticamente "8 matrizes de espectro".

A saída final é apenas um Produto Escalar (Amplitude $A_k$) somando essas oscilações caóticas-determinísticas:
$$Y(t) = H^{(FINAL)} \cdot W_{out} + b_{out}$$

Isso atende o **Objetivo #1 e #2**, banindo a FFN comum e instaurando um cálculo matricial que respeita a topologia ondulatória.

---

## 2. A Esteira de Engenharia Reversa (Isolamento de Gradiente)

Para que esse emaranhado de matrizes senoidais não sofra o Câncer do Algoritmo Neural (*Gradient Vanishing*), manteremos a regra de sobrevivência suprema detalhada por você na concepção do sistema (O *Greedy Layer-Wise*):

1. **A lixa de EMA** de fase-zero gera o Alvo Careca (O *Lowpass* Macro).
2. A Rede SIREN (com 2 hidden layers senoidais) entra em campo sozinha (Otimizando apenas aquele sub-espaço temporal). O peso das camadas superiores não interfere na derivada.
3. Subtrai-se a predição da rede em relação à série original $\rightarrow$ Resíduo sem Ladeira.
4. Passamos a próxima "Lixa" no Resíduo $\rightarrow$ Alvo da Onda 2.
5. Repete-se o processo escalonado.

**O Otimizador no chão reto:** Como cada bloco SIREN tenta mapear apenas o ruído planificado pela EMA correspondente no alvo $\rightarrow$ $\Delta y_k$, não há disputa de frequência.

---

## 3. A Função Loss Híbrida (Newton vs Pearson)

MSE (Erro Quadrático Médio) é obsecado por minimizar a distância vertical (Preço Y1 contra Y2). Mas como vimos nos resultados MACRO vs MICRO, a nossa edge reside na **Direção do Derivativo temporal**. O R² pode ser perfeito e, ainda assim, errar se o próximo tick é + ou - (Fase defasada).

Para resolver o **Objetivo #3**, propomos a Loss:

$$\mathcal{L} = \alpha \cdot \text{MSE}(\hat{y}, y) - \beta \cdot \text{PearsonCorrelation}(\Delta\hat{y}, \Delta y)$$

Onde:
*   **MSE** ancora a onda na amplitude correta (evita que a rede plote gráficos de +- 500 pips para um lixo de 5 pips).
*   **Pearson (Directional Derivative Loss)** calcula a correlação direcional dos *deltas* ($\hat{y}_{t} - \hat{y}_{t-1}$ vs $y_t - y_{t-1}$). Se a rede modelou a derivada para subir, e o mercado real desceu, a correlação é $-1$, punindo severamente o `Adam` mesmo que o MSE (altura estática) esteja próximo.

---

## Resumo e Próximos Passos
1. Implementar o PyTorch `SineLayer` e `SIREN`.
2. Integrar a $\Phi(t)$ ATR Modulada na entrada $X$.
3. Aplicar a Distância Derivativa na `loss_fn`.
4. Treinar $L_1 \rightarrow L_8$ na arquitetura V3 sob sementes $42$ usando Numpy ZeroPhase EMA.
