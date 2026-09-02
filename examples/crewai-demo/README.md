# Demo: CrewAI + Orka

Guarde uma equipe de 3 agentes CrewAI com checagem de politica e audit trail.

## Quickstart

```bash
pip install orkaia crewai

# a key vem do ambiente — nunca fica no codigo
export ORKA_API_KEY=orka_...        # crie em https://orka.ia.br
export ORKA_AGENT_ID=<id-do-agente>

python demo.py
```

## O que acontece

1. Pesquisador -- pesquisa um topico (task_type="research")
2. Redator -- escreve o artigo (risk="LIMITED", pode exigir aprovacao)
3. Revisor -- revisa o conteudo (task_type="review")

Cada tarefa passa por `@orka.guard`: a Orka checa a politica antes de executar
e registra a execucao (duracao, status, risco) no dashboard.

Loop guard, spend cap e aprovacao humana sao politicas configuradas no backend
por agente — nao parametros do decorator. O SDK falha em modo seguro: se a Orka
estiver inacessivel, seu codigo nunca e bloqueado por erro de conectividade.

## Arquivos

- `demo.py` -- equipe completa, pronta para rodar
