import json
import datetime
from typing import Any, Callable, Set, Dict, List, Optional
import os, time
from azure.identity import DefaultAzureCredential
#from azure.ai.projects import AIProjectClient
#from azure.ai.projects._client import AIProjectClient   #changed
from azure.ai.agents.models import FunctionTool
from azure.ai.projects import AIProjectClient
import inspect
from Langchain_tool_trial import web_search  ##### importing tools into main agent.
#print(inspect.getfile(AIProjectClient))
#print(dir(AIProjectClient))

#project version b11
#custom function
def fetch_weather(location: str) -> str:
    """
    Fetches the weather information for the specified location.

    :param location: The location to fetch weather for.    
    :return: Weather information as a JSON string.
    """
    # Mock weather data for demonstration purposes
    mock_weather_data = {"New York": "Sunny, 25°C", "London": "Cloudy, 18°C", "Tokyo": "Rainy, 22°C"}
    weather = mock_weather_data.get(location, "Weather data not available for this location.")
    return json.dumps({"weather": weather})

def fetch_time(location: str) -> str:
    """
    Fetches the time information for the specified location.

    :param location: The location to fetch time for.    
    :return: Time information as a JSON string.
    """
    # Mock weather data for demonstration purposes
    mock_time_data = {"New York": "Sunny, 12:00", "London": "Cloudy, 17:00", "Tokyo": "Rainy, 13:00"}
    time = mock_time_data.get(location, "Time data not available for this location.")
    return json.dumps({"time": time})


# Define user functions
user_functions = {fetch_weather,fetch_time}

#2 create client & agent

# Set up the client
# Retrieve the project endpoint from environment variables
#project_endpoint = os.environ["PROJECT_ENDPOINT"]
project_endpoint= "https://borkar-thesis-project-resource.services.ai.azure.com/api/projects/borkar-thesis-project"
# Initialize the AIProjectClient
project_client = AIProjectClient(
    endpoint=project_endpoint,
    credential=DefaultAzureCredential(),
    api_version="2025-05-15-preview",
)

# #tried using connection string instead of endpoint. Does not work. not supported by azure sdk
# project_client = AIProjectClient.create(
#     credential=DefaultAzureCredential(),
#     conn_str="swedencentral.api.azureml.ms;40fd5aec-ff36-4584-840f-61ae4a4317f2;neurongeneralopenai;general-use"
# )



# Initialize the FunctionTool with user-defined functions
functions = FunctionTool(functions=user_functions)

with project_client:
    # Create an agent with custom functions
    agent = project_client.agents.create_agent(
        model="gpt-4o-mini",
        name="my-agent",
        instructions="You are a helpful agent",
        tools=functions.definitions,
    )
    print(f"Created agent, ID: {agent.id}")

#3 create thread

    thread = project_client.agents.threads.create()
    print(f"Created thread, ID: {thread.id}")

# Send a message to the thread
    message = project_client.agents.messages.create(
        thread_id=thread.id,
        role="user",
        content="Hello, what is the time in New York?",
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
                if tool_call.function.name == "fetch_weather":
                    output = fetch_weather("New York")
                    tool_outputs.append({"tool_call_id": tool_call.id, "output": output})
                    print(f"Fetch_weather is called {output}")
                if tool_call.function.name == "fetch_time":
                    output = fetch_time("New York")
                    tool_outputs.append({"tool_call_id": tool_call.id, "output": output})
                    print(f"Fetch_time is called {output}")
            project_client.agents.runs.submit_tool_outputs(thread_id=thread.id, run_id=run.id, tool_outputs=tool_outputs)
            

    print(f"Run completed with status: {run.status}")

    # Fetch and log all messages from the thread
    messages = project_client.agents.messages.list(thread_id=thread.id)
    for message in messages:
        print(f"Role: {message['role']}, Content: {message['content']}")

    # # Delete the agent after use
    # project_client.agents.delete_agent(agent.id)
    # print("Deleted agent")


    # import inspect
    # print(inspect.getfile(AIProjectClient))

    