# Vorcaro

Sistema **multiagente de day trade** para ações e criptomoedas, com aritmética monetária exata,
mineração estatística de **padrões binários**, uma equação própria de decisão (**Ω**), gestão de
risco com poder de veto e conectores para corretoras reais.

> ⚠️ **Leia antes de usar dinheiro real.** Nenhum sistema garante lucro. Day trade tem custos
> (corretagem, emolumentos, spread, slippage, impostos) que eliminam a maioria das vantagens
> estatísticas pequenas — o próprio backtest deste projeto mostra isso. O Vorcaro foi construído
> para **não se enganar**: sem look-ahead, com controle de falsas descobertas e com travas de
> risco. Comece em simulação, depois sandbox/demo, e só então com capital pequeno.

## Arquitetura

```
                ┌──────────── dados ─────────────┐
                │ Binance · Yahoo (B3 .SA) · CSV │     raspagem RSS → sentimento
                └───────────────┬────────────────┘                │
                                ▼                                 ▼
 ┌───────────── agentes (cada um vê SÓ o passado) ──────────────────────────┐
 │ momentum · reversão · autocorrelação · padrões binários · Ω · sentimento │
 └───────────────────────────────┬──────────────────────────────────────────┘
                                 ▼
          Conselho (Hedge: pesos aprendidos online por ativo)
                                 ▼
          Scanner (ranqueia oportunidades: convicção × liquidez × volatilidade)
                                 ▼
          Agente de risco (VETO · tamanho por risco fixo ∩ Kelly fracionário · travas)
                                 ▼
          Execução → Paper · CCXT (cripto) · Alpaca (EUA) · MetaTrader 5 (B3)
                                 ▼
          Diário JSONL (auditoria de cada oportunidade, veto, ordem e erro)
```

| Módulo | Conteúdo |
|---|---|
| `core/` | modelos, `Decimal` com precisão de 34 dígitos, arredondamento a lote/tick |
| `quant/indicators.py` | EMA, Wilder, RSI, ATR, Bollinger, VWAP, z-score — todos causais |
| `quant/stats.py` | normal (Acklam + Halley), binomial exato, Beta, Hurst R/S (Anis-Lloyd-Peters), PSR, Kelly, Kalman |
| `quant/binary.py` | codificação binária, minerador de padrões com FDR, entropia (Miller-Madow), LZ76 |
| `quant/equation.py` | a Equação Vorcaro Ω |
| `agents/` | agentes de sinal, conselho Hedge, scanner |
| `risk/` | dimensionamento e kill switches |
| `brokers/` | Paper, CCXT, Alpaca, MT5 |
| `backtest/` | motor orientado a eventos, métricas, walk-forward |
| `engine/live.py` | ciclo ao vivo com diário de auditoria |
| `scraping/` | RSS de notícias + léxico de sentimento PT/EN |

## A matemática

### 1. Padrões em dados binários
Cada barra vira um símbolo de bits: o quantil do log-retorno em **código Gray** (faixas vizinhas
diferem em 1 bit) + um bit de volume (acima da mediana das barras *anteriores*).
Para cada palavra `w` de comprimento 2…6 contamos `n` ocorrências e `k` altas seguintes e testamos
`H₀: p = p_base` com **teste binomial exato**. Como milhares de palavras são testadas, os p-valores
passam por **Benjamini-Hochberg** (FDR ≤ 5%). A probabilidade usada é a média da posterior
**Beta** encolhida para a taxa base. Na previsão vence o padrão significativo mais longo
(Markov de ordem variável). A previsibilidade do fluxo é medida pela entropia condicional
`H(Xₜ | Xₜ₋₃..ₜ₋₁)` com correção de Miller-Madow e pela complexidade de Lempel-Ziv.

### 2. A Equação Vorcaro (Ω)

$$\alpha = \frac{1}{1+e^{-\kappa (H-\frac12)}}$$

$$\Psi = \tanh\left(\alpha\,\frac{M}{\lambda_M} \;-\; (1-\alpha)\,\frac{Z}{\lambda_Z} \;+\; \beta B\right)$$

$$\Omega = \Psi \cdot (1 - w_\varepsilon\,\varepsilon)\cdot\left(1-e^{-N/N_0}\right)$$

* `H` — expoente de Hurst: o **regime** decide o peso entre momentum e reversão
* `M = (EMA₉ − EMA₂₁)/ATR` — momentum em unidades de volatilidade
* `Z = (C − VWAP)/σ` — desvio do preço justo
* `B = 2p̂ − 1` — vantagem do padrão binário significativo
* `ε` — entropia condicional normalizada (1 = aleatório): reduz a convicção quando não há estrutura

### 3. Autocorrelação com significância
`ρ̂ₖ√n ~ N(0,1)` sob ausência de memória; só lags com `|z| > 2,5` entram na previsão
`r̂ₜ₊₁ = Σ ρ̂ₖ rₜ₊₁₋ₖ`, com correção de Bonferroni na confiança.

### 4. Conselho Hedge
`wᵢ ← wᵢ · exp(−η ℓᵢ)`, `ℓᵢ = (1 − sᵢ·sign(r))/2`. Garantia de arrependimento `O(√(T ln N))`
contra o melhor agente em retrospecto — o sistema aprende **qual agente funciona em qual ativo**.
Agentes que se abstêm recebem perda neutra ½ para que todos sejam comparados nas mesmas rodadas.

### 5. Risco
`qtd = (patrimônio · 0,5% · |S|) / (1,5·ATR)`, limitada por `¼ · Kelly(p̂, b = TP/SL)` e por 20% do
patrimônio. Travas: −2% no dia (libera no dia seguinte), −10% de drawdown (reset manual),
máximo de posições e de ordens/dia. Toda posição é zerada no fim do pregão.

## Validação (o que os testes provam)

| Cenário sintético | Resultado |
|---|---|
| Passeio aleatório | agentes estatísticos **se abstêm 100%**; FDR controla falsos padrões |
| Reversão AR(−0,3) | Sharpe > 10, PSR ≈ 100%, padrões validados **fora da amostra** (~62% de acerto) |
| Persistência AR(+0,3) | Sharpe > 20 com custo baixo; com 14 bps ida+volta as taxas comem ~80% do lucro |
| Anti look-ahead | um agente espião confirma que na barra *i* só se vê `0..i` |
| Contabilidade | `Decimal` exato; stop tem prioridade sobre alvo na mesma barra; gap executa na abertura |

```bash
pip install -e ".[dev]"
pytest -q          # 43 testes
```

## Uso

```bash
pip install -e ".[crypto]"            # ccxt para cripto

# Backtest e walk-forward
vorcaro backtest --source binance:BTCUSDT --interval 5m --bars 5000
vorcaro backtest --source yahoo:PETR4.SA --interval 5m --walk-forward 4
vorcaro backtest --source csv:meus_dados.csv --config config/default.toml --trades 20

# Padrões binários (treino em 70%, validação nos 30% finais)
vorcaro patterns --source binance:ETHUSDT --ret-bits 2 --max-len 5

# Leitura atual da Equação Ω
vorcaro omega --source binance:SOLUSDT

# Sentimento de notícias (raspagem RSS)
vorcaro news --symbol BTC --aliases bitcoin

# Ao vivo: por padrão NÃO envia ordens (só registra o que faria)
vorcaro run --broker paper --data binance --universe BTCUSDT,ETHUSDT,SOLUSDT
```

## Conectando sua corretora e carteira

Copie `.env.example` para `.env` e preencha. **Use chaves somente com permissão de trade — nunca de
saque.** Três níveis de segurança:

| Comando | O que acontece |
|---|---|
| `vorcaro run ...` | simulação: calcula e registra, **não envia nada** |
| `vorcaro run ... --execute` | envia para **sandbox/testnet, paper ou conta demo** |
| `VORCARO_LIVE=1 vorcaro run ... --execute --live` | **dinheiro real** (trava dupla) |

| Mercado | Corretora | Como |
|---|---|---|
| Cripto | Binance, Bybit, OKX, Kraken, Mercado Bitcoin… | `--broker ccxt` + `VORCARO_CCXT_EXCHANGE` |
| Ações EUA | Alpaca | `--broker alpaca` (bracket orders nativas) |
| B3 | XP, Clear, Rico, Genial, BTG… via **MetaTrader 5** | `--broker mt5` (Windows; recusa conta real sem `--live`) |

```bash
# exemplo: testnet da Binance
export VORCARO_CCXT_EXCHANGE=binance VORCARO_CCXT_API_KEY=... VORCARO_CCXT_SECRET=...
vorcaro run --broker ccxt --universe BTC/USDT,ETH/USDT --execute

# exemplo: mini índice / ações na B3 via MT5 (conta demo)
vorcaro run --broker mt5 --universe WINZ26,PETR4,VALE3 --session-close 20:45 --execute
```

## Roteiro sugerido
1. Rode `pytest` e os backtests nos **seus** ativos e timeframes, com os custos reais da sua corretora.
2. Exija estabilidade no `--walk-forward` (todos os blocos, não só a média).
3. Rode `run` em simulação por semanas; compare o diário com o que teria acontecido.
4. Sandbox/demo com `--execute`. 5. Capital real pequeno com `--live`.

## Licença
MIT
