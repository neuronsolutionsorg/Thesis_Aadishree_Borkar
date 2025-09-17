import os, time, json, base64
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from RFI_schema import gap_checks
from dotenv import load_dotenv
from RFI_tools import list_rfi_blobs, download_blob, extract_text_tables, upload_result

load_dotenv()
PROJECT_ENDPOINT = os.environ["PROJECT_ENDPOINT"]
AGENT_ID = os.environ["RFI_AGENT_ID"]

def handle_tool_call(tc):
    """Route agent tool calls to local implementations, saving big outputs to blob storage."""
    name = tc.function.name
    args = json.loads(tc.function.arguments or "{}")

    # 1) List blobs
    if name == "list_rfi_blobs":
        prefix = args.get("prefix", "")
        out = {"files": list_rfi_blobs(prefix)}
        return json.dumps(out)

    # 2) Download blob -> store raw file in results container -> return pointer
    if name == "download_blob":
        data = download_blob(args["name"])
        fname = args["name"].replace("/", "_")  # avoid slashes in blob name
        upload_result(fname, data)
        return json.dumps({"blob_path": f"{os.environ.get('RFI_RESULTS_CONTAINER')}/{fname}"})

    # 3) Extract text/tables -> store DI JSON result in results container -> return pointer
    if name == "extract_text_tables":
        # Instead of inline base64, agent should now pass blob_path
        blob_path = args.get("blob_path")
        if not blob_path:
            return json.dumps({"error": "Missing blob_path argument"})

        # Re-download the file from submissions container
        fname = blob_path.split("/")[-1]
        file_bytes = download_blob(fname)

        out = extract_text_tables(file_bytes, mime_type=args.get("mime_type"))
        result_name = fname + ".extracted.json"
        result_json = json.dumps(out).encode("utf-8")
        upload_result(result_name, result_json)

        return json.dumps({"result_blob": f"{os.environ.get('RFI_RESULTS_CONTAINER')}/{result_name}"})

    # 4) Upload arbitrary results (CSV, Markdown, JSON)
    if name == "upload_result":
        name, data_b64 = args["name"], args["data_b64"]
        container = args.get("container") or os.environ.get("RFI_RESULTS_CONTAINER")
        upload_result(name, base64.b64decode(data_b64), container=container)
        return json.dumps({"ok": True, "path": f"{container}/{name}"})

    return json.dumps({"error": f"unknown tool {name}"})


def main():
    client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential(),
        api_version="2025-05-15-preview"
    )

    with client:
        thread = client.agents.threads.create()

        user_prompt = """
Process RFI submissions in the container. For each file:
1) download -> extract -> normalize JSON per schema
2) perform gap checks and add 'gaps' object
3) create a side-by-side CSV across all suppliers for: supplier_name, delivery_time_days, iso_27001, sla_summary, pricing_notes
4) draft (a) buyer clarification email stubs per supplier (bullet points only), and (b) a 10-line internal summary
5) upload per-supplier JSON, one CSV compare, and one Markdown summary to the results container.
"""
        client.agents.messages.create(thread_id=thread.id, role="user", content=user_prompt)
        run = client.agents.runs.create(thread_id=thread.id, agent_id=AGENT_ID)

        # Run loop
        while run.status in ["queued", "in_progress", "requires_action"]:
            time.sleep(1)
            run = client.agents.runs.get(thread_id=thread.id, run_id=run.id)

            if run.status == "requires_action":
                outs = []
                for tc in run.required_action.submit_tool_outputs.tool_calls:
                    outs.append({
                        "tool_call_id": tc.id,
                        "output": handle_tool_call(tc)
                    })
                client.agents.runs.submit_tool_outputs(
                    thread_id=thread.id, run_id=run.id, tool_outputs=outs
                )

        # Show assistant outputs
        messages = client.agents.messages.list(thread_id=thread.id)
        for m in messages:
            if m["role"] == "assistant":
                print(m["content"])


if __name__ == "__main__":
    main()
