"""Orka + CrewAI — Monitor your CrewAI agents in production

Add @orka.guard to any CrewAI tool or task function to get full visibility
into what your crew is doing: every action logged, policy-checked, and visible
in your Orka dashboard.

Requirements:
    pip install orkaia crewai

Run:
    ORKA_API_KEY=orka_... ORKA_AGENT_ID=... python crewai_example.py
"""
import os
import orka

orka.init(api_key=os.environ["ORKA_API_KEY"])
AGENT_ID = os.environ.get("ORKA_AGENT_ID", "replace-with-your-agent-id")


# ── Wrap any CrewAI tool with @orka.guard ─────────────────────────────────────
@orka.guard(agent_id=AGENT_ID, task_type="web_search", risk="MINIMAL")
def search_web(query: str) -> str:
    """Your existing tool — Orka logs input, output, duration, and status."""
    # Replace with your actual search logic (Firecrawl, SerpAPI, etc.)
    return f"[mock] Search results for: {query}"


@orka.guard(agent_id=AGENT_ID, task_type="data_analysis", risk="LIMITED")
def analyze_data(data: dict) -> str:
    """Higher risk tasks can require approval before execution."""
    return f"[mock] Analysis of {len(data)} data points"


print("Running guarded CrewAI tools...")
result1 = search_web("best AI agent observability tools 2026")
print(f"Search: {result1}")

result2 = analyze_data({"revenue": 100000, "costs": 80000, "period": "Q1 2026"})
print(f"Analysis: {result2}")

print("\n→ Both executions are visible at https://orka.ia.br/dashboard/executions")
print("→ Risk scores, durations, and outputs are all tracked automatically")


# ── Use with actual CrewAI (requires crewai installed) ────────────────────────
try:
    from crewai import Agent, Task, Crew
    from crewai.tools import tool

    @tool("web_search")
    def orka_search_tool(query: str) -> str:
        """Search the web and log the action to Orka."""
        return search_web(query)  # already wrapped with @orka.guard above

    researcher = Agent(
        role="Research Analyst",
        goal="Find information about AI agent observability",
        backstory="You are an expert researcher who always logs your work.",
        tools=[orka_search_tool],
        verbose=False,
    )

    task = Task(
        description="Research the top 3 AI agent monitoring tools in 2026",
        expected_output="A brief list of tools with their key features",
        agent=researcher,
    )

    crew = Crew(agents=[researcher], tasks=[task], verbose=False)
    result = crew.kickoff()
    print(f"\nCrew result: {result}")

except ImportError:
    print("\nInstall crewai to run the full example: pip install crewai")
