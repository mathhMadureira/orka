# Demo: CrewAI + Orka

Guarde uma equipe de 3 agentes CrewAI com checagem de politica e audit trail.

## Quickstart

```bash
pip install "orkaia>=0.4.0" crewai
python demo.py
```

A Orka roda em modo local (sem API key). Para enviar as execucoes ao dashboard:

```bash
export ORKA_API_KEY=orka_...   # a key vem do ambiente, nunca fica no codigo
python demo.py
```

## O que acontece

1. Pesquisador -- pesquisa um topico (task_type="research")
2. Redator -- escreve o artigo (risk="LIMITED", pode exigir aprovacao)
3. Revisor -- revisa o conteudo (task_type="review")

Cada tarefa passa por `@orka.guard`: a Orka checa a politica antes de executar
e registra a execucao (duracao, status, risco) no dashboard.

Loop guard e spend cap sao configurados no `orka.init()` (ou em `orka.economy()`),
nao no decorator. Com API key, as politicas do backend valem por agente. O SDK
falha em modo seguro: se a Orka estiver inacessivel, seu codigo nunca e
bloqueado por erro de conectividade.

## Arquivos

- `demo.py` -- equipe completa, pronta para rodar
