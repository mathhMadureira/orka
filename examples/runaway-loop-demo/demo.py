"""Orka — Demo: Loop Guard

Veja a Orka cortar um agente preso em loop antes que ele queime seu orcamento.

Como funciona:
    Cada tentativa do agente passa pela Orka (@orka.guard). O loop guard e uma
    politica avaliada no backend: quando a Orka detecta a mesma acao falhando
    repetidamente, ela devolve um bloqueio e o SDK levanta OrkaPolicyBlocked —
    cortando a execucao ANTES da proxima chamada cara.

    O SDK falha em modo seguro: se a Orka estiver inacessivel, seu codigo nunca
    e bloqueado por erro de conectividade.

Requisitos:
    pip install orkaia

Setup (key nunca fica no codigo):
    1. Crie uma conta gratis em https://orka.ia.br
    2. Settings -> API Keys -> Create Key
    3. Crie um agente e ative a politica de loop guard
    4. export ORKA_API_KEY=orka_...
       export ORKA_AGENT_ID=<id-do-seu-agente>

Execucao:
    python demo.py

Dashboard em tempo real: https://orka.ia.br/dashboard
"""
import os
import time

import orka
from orka import OrkaPolicyBlocked

# A key vem do ambiente — nunca hardcoded.
orka.init(api_key=os.environ.get("ORKA_API_KEY", "orka_your_key_here"))
AGENT_ID = os.environ.get("ORKA_AGENT_ID", "replace-with-your-agent-id")

MAX_ATTEMPTS = 25  # trava de seguranca do demo (a Orka corta bem antes disso)


@orka.guard(agent_id=AGENT_ID, task_type="api_call", risk="LIMITED")
def call_flaky_api(query: str) -> str:
    """Uma tentativa de chamada de API que sempre falha.

    Sem um guard, um agente com bug chamaria isso em loop, queimando
    tokens/dinheiro. Cada chamada passa pela Orka antes de executar.
    """
    time.sleep(0.1)
    raise RuntimeError("upstream 503 — API indisponivel")


if __name__ == "__main__":
    print("=" * 60)
    print("ORKA -- Demo: Loop Guard")
    print("=" * 60)
    print()
    print("Simulando um agente com bug que retenta a mesma chamada.")
    print("A Orka deve cortar o loop via politica no backend.")
    print()

    cut_by_orka = False
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"   [Tentativa {attempt}] Chamando API... (isso queimaria $$$)")
        try:
            call_flaky_api("consulta de dados")
        except OrkaPolicyBlocked as e:
            cut_by_orka = True
            print(f"\nORKA INTERCEPTOU: {e}")
            print("   O loop foi cortado antes da proxima chamada cara.")
            break
        except RuntimeError:
            # A chamada falhou (esperado). O agente com bug tentaria de novo.
            print("   Falhou. O agente tentaria novamente...")

    print()
    print("-" * 60)
    if not cut_by_orka:
        print("A Orka nao cortou o loop nesta execucao.")
        print("Motivos possiveis (o SDK sempre falha em modo seguro):")
        print("  - ORKA_API_KEY / ORKA_AGENT_ID nao configurados")
        print("  - politica de loop guard nao ativada para este agente")
        print("  - backend da Orka inacessivel")
        print("Configure a key e a politica e rode de novo para ver o corte.")
    else:
        print("Veja o bloqueio registrado no dashboard:")
    print("   https://orka.ia.br/dashboard")
    print("-" * 60)
