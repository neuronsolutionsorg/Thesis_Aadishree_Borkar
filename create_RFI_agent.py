import os
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import FunctionTool
from RFI_schema import RFI_SCHEMA_JSON
from RFI_tools import list_rfi_blobs, download_blob, extract_text_tables, upload_result

load_dotenv()
PROJECT_ENDPOINT = os.environ["PROJECT_ENDPOINT"]

INSTRUCTIONS = f"""
You are the BUYER-SIDE RFI Agent.
Task: read suppliers' RFI submissions (PDF/DOCX/XLSX), extract answers, normalize them, check gaps,
compare suppliers, and draft clarification notes and an internal summary.

Rules:
- Use ONLY the provided tools for file access and OCR/extraction.
- Normalize output to STRICT JSON matching this schema:
{RFI_SCHEMA_JSON}
- If you are uncertain about a value, set it to "" or an empty array, do not hallucinate.
- Keep an evidence trail by listing any filenames you based values on in 'sources'.
- When complete, produce: (1) one JSON per supplier, (2) a CSV comparison table,
  (3) a short Markdown summary with gaps per supplier.
Return concise text confirming artifacts saved, plus a list of produced artifact paths.
"""

def main():
    client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential(),
        api_version="2025-05-15-preview",
    )

    # Register actual Python functions as tools
    tools = FunctionTool(functions={
        list_rfi_blobs,
        download_blob,
        extract_text_tables,
        upload_result,
    })

    with client:
        agent = client.agents.create_agent(
            model="gpt-4o-mini",
            name="rfi-buyer-agent",
            instructions=INSTRUCTIONS,
            tools=tools.definitions,
        )

    print(f"AGENT_ID={agent.id}")

if __name__ == "__main__":
    main()

