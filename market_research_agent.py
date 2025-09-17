import json
import datetime
from typing import Any, Callable, Set, Dict, List, Optional
import os, time
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import FunctionTool
from azure.ai.projects import AIProjectClient
import inspect
from Langchain_tool_trial import web_search   #toolcall
from dotenv import load_dotenv

load_dotenv()

# Define user functions
user_functions = {web_search} 

# Set up the client
# Retrieve the project endpoint from environment variables
project_endpoint = os.environ["PROJECT_ENDPOINT"]
# Initialize the AIProjectClient
project_client = AIProjectClient(
    endpoint=project_endpoint,
    credential=DefaultAzureCredential(),
    api_version="2025-05-15-preview",
)



# Initialize the FunctionTool with user-defined functions
functions = FunctionTool(functions=user_functions)

with project_client:
    # Create an agent with custom functions
    agent = project_client.agents.create_agent(
        model="gpt-4o-mini",
        name="market research agent",
        instructions="You are a helpful agent who uses the provided tool and returns the answer to the query in a structured format.You also make sure that the information you retrieve from the internet is from legitimate and trusted sources.",
        tools=functions.definitions,
    )
    print(f"Created agent, ID: {agent.id}")

#3 create thread

    thread = project_client.agents.threads.create()
    print(f"Created thread, ID: {thread.id}")

# Send a message to the thread
    user_question = input("Ask a market research question: ")

    message = project_client.agents.messages.create(
        thread_id=thread.id,
        role="user",
        content=user_question,
    )
    print(f"Created message, ID: {message['id']}")

#create run & check output

    run = project_client.agents.runs.create(thread_id=thread.id, agent_id=agent.id)
    print(f"Created run, ID: {run.id}")

# Poll the run status until it is completed or requires action
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

                
            project_client.agents.runs.submit_tool_outputs(thread_id=thread.id, run_id=run.id, tool_outputs=tool_outputs)
            

    print(f"Run completed with status: {run.status}")

# Fetch and log all messages from the thread
    messages = project_client.agents.messages.list(thread_id=thread.id)
    for message in messages:
        print(f"Role: {message['role']}, Content: {message['content']}")
