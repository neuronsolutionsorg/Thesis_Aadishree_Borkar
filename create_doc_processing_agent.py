
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

Available tools:
1. `list_container_files(prefix: str)` → Lists blobs in the container.
2. `analyze_blob_with_di(blob_name: str)` → Downloads and analyzes the specified file using Document Intelligence. Returns a JSON object with extracted fields and confidence scores.
3. `save_json_to_blob(target_blob_name: str, data_json: Dict)` → Saves JSON data to the container.

Workflow you must always follow:
- Start by calling `list_container_files` to see which files exist.
- Choose a `.pdf` file from the list.
- Call `analyze_blob_with_di` on that file to extract structured data.
- Then call `save_json_to_blob` with **both arguments**:
  - `"target_blob_name"`: path like `"outputs/<same-basename>.json"`.
  - `"data_json"`: the **exact JSON result** you got from `analyze_blob_with_di`.

Rules:
- Do NOT omit the `data_json` field when calling `save_json_to_blob`.
- Always pass the entire DI result to `data_json` without modification.
- Prefer short structured outputs, avoid long explanations.
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
    print(" Agent created!")
    print(f"Agent ID: {agent.id}")

