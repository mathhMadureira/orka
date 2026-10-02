# Demo: Loop Guard

Veja a Orka cortar um agente preso em loop antes que ele queime seu orcamento.
Roda em ~10 segundos, **offline, sem API key e sem conta**.

## Quickstart

```bash
pip install "orkaia>=0.4.0"
python demo.py
```

## O que acontece

1. Um agente com bug retenta a mesma chamada de API que sempre falha
2. Cada tentativa passa pela Orka via `@orka.guard`
3. Na 3a repeticao (`loop_threshold=3`) a Orka corta e levanta `OrkaPolicyBlocked`
4. O loop para ANTES da proxima chamada cara
5. `orka.summary()` mostra acoes, intervencoes e quanto foi evitado

Saida esperada:

```
   [Tentativa 3] Chamando API... (isso queimaria $$$)

ORKA INTERCEPTOU: Blocked by policy: Loop detected: 'api_call' repeated 3 times
   O loop foi cortado antes da proxima chamada cara.
```

## Como funciona

```python
orka.init(mode="local", enforce=True, per_run_usd=0.50, loop_threshold=3)

@orka.guard(agent_id="burner-demo", task_type="api_call")
def call_flaky_api(query): ...
```

- `mode="local"` -- backend local em SQLite, sem rede e sem API key
- `enforce=True` -- a Orka corta de verdade (sem isso, apenas observa)
- `loop_threshold` -- quantas repeticoes ate cortar
- `per_run_usd` -- teto de gasto por execucao

Loop guard e spend cap sao configurados no `init()` (ou em `orka.economy()`),
nao no decorator.

## Por que isso importa

Em producao, um agente em loop pode gastar $50, $100 ou mais em uma noite.
A Orka corta em segundos.

## Rodando com sua conta

Para ver as execucoes no dashboard, troque o init:

```python
import os
orka.init(api_key=os.environ["ORKA_API_KEY"])  # key sempre do ambiente
```

Dashboard: https://orka.ia.br/dashboard

## Arquivos

- `demo.py` -- codigo completo, pronto para rodar
