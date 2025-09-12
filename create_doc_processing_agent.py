
import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import FunctionTool
from doc_agent_tools import list_container_files, analyze_blob_with_di, save_json_to_blob

load_dotenv()
PROJECT_ENDPOINT = os.environ["PROJECT_ENDPOINT"]

functions = FunctionTool(functions={list_container_files, analyze_blob_with_di, save_json_to_blob})

DOC_AGENT_PROMPT = """
You are a document processing agent for procurement proposals.
You have to use the tools to (1) list files, (2) analyze a selected file with Azure Document Intelligence,
and (3) save the extracted JSON into the container on Azure blob storage.
Always return JSON with fields: vendor_name, delivery_date, cost, technologies along with confidence scores for each value.
If a value is missing, set it to null and keep confidence=0.0.
Keep explanations short—prefer structured output.
"""

project_client = AIProjectClient(
    endpoint=PROJECT_ENDPOINT,
    credential=DefaultAzureCredential(),
    api_version="2025-05-15-preview",
)

with project_client:
    agent = project_client.agents.create_agent(
        model="gpt-4o-mini",
        name="document processing agent",
        instructions=DOC_AGENT_PROMPT,
        tools=functions.definitions,
    )
    print("✅ Agent created!")
    print(f"Agent ID: {agent.id}")

