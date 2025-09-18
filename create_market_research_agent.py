
import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import FunctionTool


load_dotenv()
PROJECT_ENDPOINT = os.environ["PROJECT_ENDPOINT"]


from web_search_tool import web_search

#JSON schema
MARKET_SCHEMA = r"""
Return ONLY valid JSON (no explanations) matching:
{
  "query": "string",
  "time_window": "string",
  "suppliers": [
    {
      "name": "string",
      "hq": "string|null",
      "regions": ["string"],
      "capabilities": ["string"],
      "indicative_prices_or_tiers": "string|null",
      "strengths": ["string"],
      "risks": ["string"],
      "sources": [{"title":"string","url":"string","domain":"string"}]
    }
  ],
  "market_snapshot": {
    "segments": ["string"],
    "drivers": ["string"],
    "constraints_or_regulations": ["string"],
    "trends": ["string"]
  },
  "open_questions": ["string"],
  "sources": [{"title":"string","url":"string","domain":"string"}]
}
"""

INSTRUCTIONS = f"""
You are a buyer-side Market Research Agent.

Rules:
- Use ONLY the `web_search` tool for facts.
- Prefer reputable/official sources; if unsure, add to open_questions.
- Every nontrivial claim must be supported by a URL from the latest tool output.
- Always return details for at least 3 suppliers (if found). 
- Each supplier must have: name, HQ (if available), regions, capabilities, and at least 1 supporting source.
- If fewer than 3 suppliers are found, add open questions about missing ones.
- If data is missing, leave fields null/empty and record an open question.
- Return ONLY the JSON described below. No extra text.
{MARKET_SCHEMA}
"""


def main():
    client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential(),
        api_version="2025-05-15-preview",
    )
    tools = FunctionTool(functions={web_search})

    with client:
        agent = client.agents.create_agent(
            model="gpt-4o-mini",
            name="market research agent",
            instructions=INSTRUCTIONS,
            tools=tools.definitions,
        )

    print("Agent created.")
   
    print(f"MARKET_AGENT_ID={agent.id}")

if __name__ == "__main__":
    main()
