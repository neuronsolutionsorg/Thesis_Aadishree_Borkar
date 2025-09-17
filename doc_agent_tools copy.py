
# doc_agent_tools.py
import logging
import os, json
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
import base64
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest

load_dotenv()

# Set up logging for azure core
logger = logging.getLogger("azure.core.pipeline.policies.http_logging_policy")
logger.setLevel(logging.DEBUG)

# ---- Clients (safe to init on import) ----
DI_ENDPOINT = os.environ["DOCUMENT_INTELLIGENCE_ENDPOINT"]
DI_KEY = os.environ["DOCUMENT_INTELLIGENCE_KEY"]
di_client = DocumentIntelligenceClient(DI_ENDPOINT, AzureKeyCredential(DI_KEY))

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

def _analyze_bytes_with_di(file_bytes: bytes, content_type: Optional[str] = None) -> Dict[str, Any]:
    
    poller = di_client.begin_analyze_document(
        model_id="prebuilt-document",
        body=file_bytes
    )
    result = poller.result()  

    def by_label(*labels) -> Dict[str, Any]:
        labels_l = [l.lower() for l in labels]
        for kv in (result.key_value_pairs or []):
            key_text = (kv.key.content or "").lower() if kv.key else ""
            if any(lbl in key_text for lbl in labels_l):
                val = kv.value.content if kv.value else None
                return {"value": val, "confidence": float(kv.confidence or 0.0)}
        return {"value": None, "confidence": 0.0}

    out = {
        "vendor_name":  by_label("vendor", "supplier"),
        "delivery_date": by_label("delivery date", "expected delivery"),
        "cost":          by_label("total cost", "budget", "price", "amount"),
        "technologies":  by_label("technologies", "tech stack", "tools"),
    }
    return {"fields": out, "preview": (result.content or "")[:1200]}




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
