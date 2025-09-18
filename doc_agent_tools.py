# doc_agent_tools.py
import json
import os
import tempfile
import re 
from typing import Any, Dict, List, Optional

from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

from utils.document_intelligence_handler import DocumentIntelligenceHandler
from utils.handler_result import HandlerResult

load_dotenv()

# ---- Clients (safe to init on import) ----

di_handler = DocumentIntelligenceHandler(
    model_type="documentModels",
    model_id="prebuilt-layout",
    #output_content_format="json",
)

BLOB_CONN = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
CONTAINER_NAME = os.environ["CONTAINER_NAME"]
container_client = BlobServiceClient.from_connection_string(BLOB_CONN).get_container_client(CONTAINER_NAME)

#helpers
def _get_blob_bytes(blob_name: str) -> bytes:
    return container_client.get_blob_client(blob_name).download_blob().readall()


def _guess_content_type(blob_name: str) -> str:
    name = blob_name.lower()
    if name.endswith(".docx"):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if name.endswith(".pdf"):
        return "application/pdf"
    return "application/octet-stream"


def _analyze_bytes_with_di(
    file_bytes: bytes, content_type: Optional[str] = None
) -> Dict[str, Any]:
    # Persist to a temp file so the working handler can read it
    # Works with image files too, suffix doesn't really matter
    suffix = ".pdf"
    if (
        content_type
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ):
        suffix = ".docx"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    res: HandlerResult = di_handler(tmp_path)
    if not res.success:
        raise RuntimeError(f"Document Intelligence failed: {res.error}")

    result_content = (res.content or {}).get("analyzeResult", {})
    content_text = result_content.get("content", "")
    fields = extract_proposal_fields(content_text)

    return {
        "fields": fields,
        "preview": (content_text or "")[:1200]
    }

def extract_proposal_fields(text: str) -> dict:
    # Supplier
    supplier = re.search(r"Supplier:\s*(.+)", text)
    
    # Project title (first line after Supplier)
    title = re.search(r"Supplier:.*?\n\n(.+)", text, re.DOTALL)
    
    # Client / recipient
    client = re.search(r"Proposal for\s+(.+)", text)
    
    # Duration
    duration = re.search(r"Estimated duration:\s*([0-9–\-]+.*weeks)", text, re.IGNORECASE)
    
    # Offer Price
    cost = re.search(r"Offer Price:\s*([\d,\.]+.*)", text, re.IGNORECASE)
    
    # Key Deliverables block
    deliverables = re.search(r"Key Deliverables:(.+?)\n\n", text, re.DOTALL | re.IGNORECASE)
    
    # Expected Benefits block
    benefits = re.search(r"EXPECTED BUSINESS BENEFITS(.+?)\n\nCOST ESTIMATE", text, re.DOTALL | re.IGNORECASE)

    return {
        "supplier_name": supplier.group(1).strip() if supplier else None,
        "project_title": title.group(1).strip() if title else None,
        "client": client.group(1).strip() if client else None,
        "duration": duration.group(1).strip() if duration else None,
        "offer_price": cost.group(1).strip() if cost else None,
        "key_deliverables": deliverables.group(1).strip() if deliverables else None,
        "expected_benefits": benefits.group(1).strip() if benefits else None,
    }

# ---- Tools the agent will call ----
def list_container_files(prefix: Optional[str] = None) -> List[str]:
    return [b.name for b in container_client.list_blobs(name_starts_with=prefix or "")]

def analyze_blob_with_di(blob_name: str) -> Dict[str, Any]:
    data = _get_blob_bytes(blob_name)
    ctype = _guess_content_type(blob_name)
    
    return {"blob_name": blob_name, **_analyze_bytes_with_di(data, content_type=ctype)}
    
def save_json_to_blob(target_blob_name: str, data_json: Dict[str, Any]) -> str:
    payload = json.dumps(data_json, ensure_ascii=False, indent=2).encode("utf-8")
    container_client.get_blob_client(target_blob_name).upload_blob(payload, overwrite=True)
    return target_blob_name
