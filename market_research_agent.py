import json
import time
import os
from typing import Dict, Any
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from market_research_agent_tools import web_search   # tool
from dotenv import load_dotenv

load_dotenv()

# Load environment variables
PROJECT_ENDPOINT = os.environ["PROJECT_ENDPOINT"]
AGENT_ID = os.environ["MARKET_AGENT_ID"]   # <-- saved from create_market_research_agent.py

# Initialize the AIProjectClient
project_client = AIProjectClient(
    endpoint=PROJECT_ENDPOINT,
    credential=DefaultAzureCredential(),
    api_version="2025-05-15-preview",
)

with project_client:
    # Create a new conversation thread
    thread = project_client.agents.threads.create()
    print(f"Created thread, ID: {thread.id}")

    # Ask user for a market research question
    user_question = input("Ask a market research question: ")

    # Send the user message to the thread
    message = project_client.agents.messages.create(
        thread_id=thread.id,
        role="user",
        content=user_question,
    )
    print(f"Created message, ID: {message['id']}")

    # Start a run using the existing agent
    run = project_client.agents.runs.create(
        thread_id=thread.id,
        agent_id=AGENT_ID
    )
    print(f"Created run, ID: {run.id}")

    # Poll the run status until it is completed
    while run.status in ["queued", "in_progress", "requires_action"]:
        time.sleep(1)
        run = project_client.agents.runs.get(thread_id=thread.id, run_id=run.id)

        if run.status == "requires_action":
            tool_calls = run.required_action.submit_tool_outputs.tool_calls
            tool_outputs = []
            for tool_call in tool_calls:
                print(f"Tool is called {tool_call.function.name}")
                if tool_call.function.name == "web_search":
                    args = json.loads(tool_call.function.arguments)
                    query = args.get("query", "")
                    output = web_search(query)
                    tool_outputs.append({
                        "tool_call_id": tool_call.id,
                        "output": output
                    })

            project_client.agents.runs.submit_tool_outputs(
                thread_id=thread.id,
                run_id=run.id,
                tool_outputs=tool_outputs
            )

    print(f"Run completed with status: {run.status}")

    # Fetch and log all messages from the thread
    messages = project_client.agents.messages.list(thread_id=thread.id)
    for message in messages:
        if message["role"] == "assistant":
            try:
            # Extract raw JSON string
                raw_json = message["content"][0]["text"]["value"]
            # Load + pretty print
                parsed = json.loads(raw_json)
                print(json.dumps(parsed, indent=2))
            except Exception as e:
                print("Assistant output (non-JSON):", message["content"])