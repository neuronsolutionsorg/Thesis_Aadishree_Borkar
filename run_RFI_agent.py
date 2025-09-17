# rfi_run.py
import os, time, json, base64
from typing import List
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from RFI_schema import gap_checks
from dotenv import load_dotenv
load_dotenv()
PROJECT_ENDPOINT = os.environ["PROJECT_ENDPOINT"]
AGENT_ID = os.environ["RFI_AGENT_ID"]

def b64(x: bytes) -> str: return base64.b64encode(x).decode("utf-8")

# Wire actual Python functions to tool calls
from RFI_tools import list_rfi_blobs, download_blob, extract_text_tables, upload_result

def handle_tool_call(tc):
    name = tc.function.name
    args = json.loads(tc.function.arguments or "{}")
    if name == "list_rfi_blobs":
        prefix = args.get("prefix","")
        out = {"files": list_rfi_blobs(prefix)}
        return json.dumps(out)

    if name == "download_blob":
        data = download_blob(args["name"])
        return json.dumps({"name": args["name"], "file_bytes_b64": b64(data)})

    if name == "extract_text_tables":
        file_bytes = base64.b64decode(args["file_bytes_b64"])
        mime = args.get("mime_type")
        out = extract_text_tables(file_bytes, mime_type=mime)
        return json.dumps(out)

    if name == "upload_result":
        name, data_b64 = args["name"], args["data_b64"]
        container = args.get("container")
        upload_result(name, base64.b64decode(data_b64), container=container or os.environ.get("RFI_RESULTS_CONTAINER"))
        return json.dumps({"ok": True, "path": f"{container or os.environ.get('RFI_RESULTS_CONTAINER')}/{name}"})

    return json.dumps({"error":"unknown tool"})

def main():
    client = AIProjectClient(endpoint=PROJECT_ENDPOINT, credential=DefaultAzureCredential(), api_version="2025-05-15-preview")
    with client:
        thread = client.agents.threads.create()

        # System kickoff message: ask the agent to process all files under the prefix
        prefix = "2025-09/"  # <-- change or leave empty to process entire container
        user_prompt = f"""
Process RFI submissions under prefix '{prefix}'. For each file:
1) download -> extract -> normalize JSON per schema
2) perform gap checks and add 'gaps' object
3) create a side-by-side CSV across all suppliers for: supplier_name, delivery_time_days, iso_27001, sla_summary, pricing_notes
4) draft (a) buyer clarification email stubs per supplier (only bullet points), and (b) a 10-line internal summary
5) upload per-supplier JSON, one CSV compare, and one Markdown summary to the results container.
"""

        client.agents.messages.create(thread_id=thread.id, role="user", content=user_prompt)
        run = client.agents.runs.create(thread_id=thread.id, agent_id=AGENT_ID)

        while run.status in ["queued", "in_progress", "requires_action"]:
            time.sleep(1)
            run = client.agents.runs.get(thread_id=thread.id, run_id=run.id)

            if run.status == "requires_action":
                outs = []
                for tc in run.required_action.submit_tool_outputs.tool_calls:
                    outs.append({"tool_call_id": tc.id, "output": handle_tool_call(tc)})
                client.agents.runs.submit_tool_outputs(thread_id=thread.id, run_id=run.id, tool_outputs=outs)

        # Log assistant output (should mention uploaded artifact paths)
        messages = client.agents.messages.list(thread_id=thread.id)
        for m in messages:
            if m["role"] == "assistant":
                print(m["content"])

if __name__ == "__main__":
    main()
