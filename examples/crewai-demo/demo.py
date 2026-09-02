"""Orka + CrewAI — Demo

Guarde uma equipe de 3 agentes CrewAI com a Orka: cada acao passa por uma
checagem de politica antes de executar e e registrada no ledger imutavel.
Acoes de maior risco podem exigir aprovacao humana (politica no backend).

Requisitos:
    pip install "orkaia>=0.4.0" crewai

Execucao:
    python demo.py

A Orka roda em modo local (sem API key). Para enviar tudo ao dashboard:
    export ORKA_API_KEY=orka_...   # key sempre do ambiente, nunca no codigo
    Dashboard: https://orka.ia.br/dashboard
"""
import os

import orka

# Com ORKA_API_KEY no ambiente, envia ao dashboard. Sem ela, roda local.
_key = os.environ.get("ORKA_API_KEY")
if _key:
    orka.init(api_key=_key)
else:
    orka.init(mode="local", enforce=True, per_run_usd=1.00, loop_threshold=3)

AGENT_ID = os.environ.get("ORKA_AGENT_ID", "crewai-demo")


# Cada tarefa da crew e envolvida pelo guard da Orka.
# risk="LIMITED"/"HIGH" permite que o backend exija aprovacao antes de executar.
@orka.guard(agent_id=AGENT_ID, task_type="research", risk="MINIMAL")
def pesquisador_task(topic: str):
    from crewai import Agent, Task, Crew

    agent = Agent(
        role="Pesquisador",
        goal=f"Pesquisar sobre {topic}",
        backstory="Voce e um pesquisador experiente.",
        allow_delegation=False,
    )
    task = Task(description=f"Pesquise {topic}", agent=agent)
    crew = Crew(agents=[agent], tasks=[task])
    return crew.kickoff()


@orka.guard(agent_id=AGENT_ID, task_type="write", risk="LIMITED")
def redator_task(research: str):
    from crewai import Agent, Task, Crew

    agent = Agent(
        role="Redator",
        goal="Escrever um artigo baseado na pesquisa",
        backstory="Voce e um redator tecnico.",
        allow_delegation=False,
    )
    task = Task(description=f"Escreva artigo sobre: {research}", agent=agent)
    crew = Crew(agents=[agent], tasks=[task])
    return crew.kickoff()


@orka.guard(agent_id=AGENT_ID, task_type="review", risk="MINIMAL")
def revisor_task(article: str):
    from crewai import Agent, Task, Crew

    agent = Agent(
        role="Revisor",
        goal="Revisar o artigo",
        backstory="Voce e um editor rigoroso.",
        allow_delegation=False,
    )
    task = Task(description=f"Revise: {article}", agent=agent)
    crew = Crew(agents=[agent], tasks=[task])
    return crew.kickoff()


if __name__ == "__main__":
    print("CrewAI + Orka Demo")
    print("=" * 50)

    topic = "Inteligencia Artificial em 2026"

    print(f"\n1. Pesquisando: {topic}")
    research = pesquisador_task(topic)
    print("   Pesquisa concluida (registrada na Orka)")

    print("\n2. Redigindo artigo...")
    article = redator_task(str(research))
    print("   Artigo concluido (risco LIMITED — pode exigir aprovacao)")

    print("\n3. Revisando...")
    review = revisor_task(str(article))
    print("   Revisao concluida")

    print("\n" + "=" * 50)
    print("Veja todas as execucoes no dashboard:")
    print("   https://orka.ia.br/dashboard")
