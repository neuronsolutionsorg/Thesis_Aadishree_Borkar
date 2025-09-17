# run_market_agent_min.py
import os, time, json
from typing import Any, Dict, Optional
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import ListSortOrder


# your tool (it returns a JSON string)
from web_search_tool import web_search

load_dotenv()
PROJECT_ENDPOINT = os.environ["PROJECT_ENDPOINT"]
MARKET_AGENT_ID = os.environ["MARKET_AGENT_ID"]



def main():
    client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential(),
        api_version="2025-05-15-preview",
    )

    with client:
        agent = client.agents.get_agent(agent_id=MARKET_AGENT_ID)
        print(f"Using agent: {agent.id}")

        # one thread per session
        thread = client.agents.threads.create()
        print(f"Thread: {thread.id}")

        while True:
            user_q = input("\nAsk your market question (or 'exit'): ").strip()
            if user_q.lower() in {"exit", "quit"}:
                print("Bye!")
                break

            # post user question
            client.agents.messages.create(thread_id=thread.id, role="user", content=user_q)

            # start a run
            run = client.agents.runs.create(thread_id=thread.id, agent_id=agent.id)

            # poll and serve tools
            while run.status in {"queued", "in_progress", "requires_action"}:
                time.sleep(1)
                run = client.agents.runs.get(thread_id=thread.id, run_id=run.id)

                if run.status == "requires_action":
                    tool_calls = run.required_action.submit_tool_outputs.tool_calls
                    tool_outputs = []

                    for tc in tool_calls:
                        fname = tc.function.name
                        args = json.loads(tc.function.arguments or "{}")

                        if fname == "web_search":
                            try:
                                output = web_search(
                                    query=args.get("query", user_q),
                                    max_results=int(args.get("max_results", 20)),
                                    timelimit=args.get("timelimit", "y"),
                                    allow_domains=args.get("allow_domains"),
                                    deny_domains=args.get("deny_domains"),
                                )
                            except Exception as e:
                                output = json.dumps({"results": [], "error": str(e)})
                        else:
                            output = json.dumps({"error": f"unknown tool: {fname}"})

                        tool_outputs.append({"tool_call_id": tc.id, "output": output})

                    client.agents.runs.submit_tool_outputs(
                        thread_id=thread.id, run_id=run.id, tool_outputs=tool_outputs
                    )

            print(f"Run status: {run.status}")

            # fetch reply and print JSON only (as enforced by instructions)
            messages = client.agents.messages.list(
                 thread_id=thread.id,
                 order=ListSortOrder.DESCENDING  # newest message first
            )

            assistant_text = None
            for m in messages:
                if m.text_messages and m.role == "assistant":
                    assistant_text = m.text_messages[-1].text.value
                    break  # we found the most recent assistant reply

            # just print what the agent returned (should be valid JSON)
            print("\n=== AGENT JSON OUTPUT ===")
            print(assistant_text)
            print("=========================\n")

if __name__ == "__main__":
    main()
