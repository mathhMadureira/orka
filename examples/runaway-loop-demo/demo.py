"""Orka — Demo: Loop Guard

Veja a Orka cortar um agente preso em loop antes que ele queime seu orcamento.
Roda em ~10 segundos, offline, sem API key e sem conta.

Como funciona:
    orka.init(mode="local") sobe um backend local (SQLite). Com enforce=True,
    a Orka avalia cada acao: ao detectar a mesma acao repetida `loop_threshold`
    vezes — ou ao estourar o teto de custo `per_run_usd` — ela devolve um
    bloqueio e o SDK levanta OrkaPolicyBlocked, cortando a execucao ANTES da
    proxima chamada cara.

Requisitos:
    pip install "orkaia>=0.4.0"

Execucao:
    python demo.py

Para enviar as execucoes ao dashboard, troque o init por:
    orka.init(api_key=os.environ["ORKA_API_KEY"])   # key sempre do ambiente
    Dashboard: https://orka.ia.br/dashboard
"""
import time

import orka
from orka import OrkaPolicyBlocked

# Modo local: sem API key, sem rede. enforce=True faz a Orka cortar de verdade.
orka.init(
    mode="local",
    enforce=True,
    per_run_usd=0.50,   # teto de gasto por execucao
    loop_threshold=3,   # corta apos 3 acoes repetidas
)

MAX_ATTEMPTS = 25  # trava de seguranca do demo (a Orka corta bem antes)


@orka.guard(agent_id="burner-demo", task_type="api_call")
def call_flaky_api(query: str) -> str:
    """Uma chamada de API que sempre falha.

    Sem um guard, um agente com bug chamaria isso em loop, queimando
    tokens/dinheiro. Cada tentativa passa pela Orka antes de executar.
    """
    time.sleep(0.1)
    raise RuntimeError("upstream 503 — API indisponivel")


if __name__ == "__main__":
    print("=" * 60)
    print("ORKA -- Demo: Loop Guard")
    print("=" * 60)
    print()
    print("Simulando um agente com bug que retenta a mesma chamada.")
    print(f"A Orka deve cortar apos {3} tentativas repetidas.")
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
    if not cut_by_orka:
        print("A Orka nao cortou o loop nesta execucao.")
        print("Confira se instalou orkaia>=0.4.0 (modo local exige 0.4.0+).")
    else:
        # Quanto a Orka evitou de desperdicio nesta run
        try:
            orka.summary()
        except Exception:
            pass

    print("-" * 60)
    print("Rode com sua conta para ver tudo no dashboard:")
    print("   https://orka.ia.br/dashboard")
    print("-" * 60)
