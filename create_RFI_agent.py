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
- Always use this workflow:
  1. Call `list_rfi_blobs` to see available submissions in the 'rfi-submissions' container.
  2. Call `download_blob` with the file name to get its blob path in 'rfi-submissions'.
  3. Call `extract_text_tables` with `blob_path` (not file bytes) to extract text and tables.
  4. Normalize output to STRICT JSON matching this schema:
{RFI_SCHEMA_JSON}
  5. Perform gap checks and note missing or unclear fields.
  6. Create a supplier comparison CSV (supplier_name, delivery_time_days, iso_27001, sla_summary, pricing_notes).
  7. Draft buyer clarification bullet points per supplier and a 10-line internal summary.

- When saving outputs (per-supplier JSON, consolidated CSV, Markdown summary), always use `upload_result`.
  Save them into the 'rfi-results' container, not in 'rfi-submissions'.
- If you are uncertain about a value, set it to "" or an empty array, do not hallucinate.
- Keep an evidence trail by listing any filenames you based values on in 'sources'.
- Return concise text confirming artifacts saved, plus a list of produced artifact paths.
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

