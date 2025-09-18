# Doc_processing_agent.py (runner)
import os, json, time
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from doc_agent_tools import list_container_files, analyze_blob_with_di, save_json_to_blob

load_dotenv()
PROJECT_ENDPOINT = os.environ["PROJECT_ENDPOINT"]

def main():
    AGENT_ID = os.environ["DOC_AGENT_ID"]  
    project_client = AIProjectClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential(),
        api_version="2025-05-15-preview",
    )
    with project_client:
        thread = project_client.agents.threads.create()
        print(f"Created thread, ID: {thread.id}")

        user_message = (
            "Call `list_container_files` with {\"prefix\": \"\"} and return a few .pdf files. "
            "Pick one .pdf file from the list. "
            "Call `analyze_blob_with_di` with {\"blob_name\": \"<that-pdf-file>\"}. "
            "Finally, call `save_json_to_blob` with {\"target_blob_name\": \"outputs/<same-basename>.json\", "
            "\"data_json\": <the DI result>}. "
            "Ensure `data_json` is exactly the full JSON output from `analyze_blob_with_di`."
            )

        project_client.agents.messages.create(thread_id=thread.id, role="user", content=user_message)
        run = project_client.agents.runs.create(thread_id=thread.id, agent_id=AGENT_ID)

        while run.status in ["queued", "in_progress", "requires_action"]:
            time.sleep(1)
            run = project_client.agents.runs.get(thread_id=thread.id, run_id=run.id)
            if run.status == "requires_action":
                tool_outputs = []
                for tc in run.required_action.submit_tool_outputs.tool_calls:
                    name = tc.function.name
                    args = json.loads(tc.function.arguments or "{}")
                    if name == "list_container_files":
                        out = list_container_files(**args)
                    elif name == "analyze_blob_with_di":
                        out = analyze_blob_with_di(**args)
                    elif name == "save_json_to_blob":
                        out = save_json_to_blob(**args)
                    else:
                        out = {"error": f"Unknown tool {name}"}
                    tool_outputs.append({"tool_call_id": tc.id, "output": json.dumps(out, ensure_ascii=False)})
                project_client.agents.runs.submit_tool_outputs(thread_id=thread.id, run_id=run.id, tool_outputs=tool_outputs)

        print(f"Run completed with status: {run.status}")

        messages = project_client.agents.messages.list(thread_id=thread.id)
        print("\n--- Thread transcript ---")
        for m in messages:
            role = m.get("role") if isinstance(m, dict) else getattr(m, "role", None)
            content = m.get("content") if isinstance(m, dict) else getattr(m, "content", None)
            print(f"[{role}] {content}")
        print("--- end transcript ---\n")

if __name__ == "__main__":
    main()

