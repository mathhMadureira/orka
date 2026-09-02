# Demo: Loop Guard

Veja a Orka cortar um agente preso em loop antes que ele queime seu orcamento.

## Quickstart

```bash
pip install orkaia

# a key vem do ambiente — nunca fica no codigo
export ORKA_API_KEY=orka_...        # crie em https://orka.ia.br
export ORKA_AGENT_ID=<id-do-agente> # ative a politica de loop guard nele

python demo.py
```

## O que acontece

1. Um agente com bug retenta a mesma chamada de API que sempre falha
2. Cada tentativa passa pela Orka via `@orka.guard`
3. O loop guard (politica no backend) detecta a repeticao e devolve um bloqueio
4. O SDK levanta `OrkaPolicyBlocked` e a execucao e cortada ANTES da proxima chamada cara
5. O bloqueio fica registrado no dashboard: https://orka.ia.br/dashboard

## Por que isso importa

Em producao, um agente em loop pode gastar $50, $100 ou mais em uma noite.
A Orka corta em segundos.

## Notas

- O loop guard e uma **politica avaliada no backend**, nao um parametro do
  decorator. Ative-a para o agente no dashboard.
- O SDK **falha em modo seguro**: se a Orka estiver inacessivel, seu codigo
  nunca e bloqueado por erro de conectividade — o loop simplesmente roda.
- Sem `ORKA_API_KEY`/`ORKA_AGENT_ID` configurados, o demo roda em modo
  passthrough e avisa que nao houve corte.

## Arquivos

- `demo.py` -- codigo completo, pronto para rodar
