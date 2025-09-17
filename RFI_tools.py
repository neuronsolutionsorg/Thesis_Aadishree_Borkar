# rfi_tools.py
import io, os, json
from typing import List, Dict
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
load_dotenv()  
ACCOUNT_URL = os.environ["AZURE_STORAGE_ACCOUNT_URL"]          
CONTAINER = os.environ.get("RFI_CONTAINER","rfi-submissions")
RESULTS_CONTAINER = os.environ.get("RFI_RESULTS_CONTAINER","rfi-results")

DI_ENDPOINT = os.environ["DOCUMENT_INTELLIGENCE_ENDPOINT"]
DI_KEY = os.environ["DOCUMENT_INTELLIGENCE_KEY"]

# Blob client
conn_str = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
_blob = BlobServiceClient.from_connection_string(conn_str)

def list_rfi_blobs(prefix: str = "") -> List[str]:
    container = _blob.get_container_client(CONTAINER)
    return [b.name for b in container.list_blobs(name_starts_with=prefix) if not b.name.endswith("/")]

def download_blob(name: str) -> bytes:
    container = _blob.get_container_client(CONTAINER)
    return container.download_blob(name).readall()

def upload_result(name: str, data: bytes, container: str = RESULTS_CONTAINER):
    container_client = _blob.get_container_client(container)
    try:
        container_client.create_container()
    except Exception:
        pass
    container_client.upload_blob(name, data, overwrite=True)

# Document Intelligence
_di = DocumentIntelligenceClient(DI_ENDPOINT, AzureKeyCredential(DI_KEY))

def extract_text_tables(file_bytes: bytes, mime_type: str = None) -> Dict:
    """
    Use prebuilt layout/Read to extract plain text and tables.
    """
    poller = _di.begin_analyze_document(
        model_id="prebuilt-layout",
        analyze_request=file_bytes,
        content_type=mime_type or "application/octet-stream"
    )
    result = poller.result()
    text = result.content or ""
    tables = []
    for t in result.tables or []:
        rows = []
        for r in range(t.row_count):
            row = []
            for c in range(t.column_count):
                cell = next((cell for cell in t.cells if cell.row_index==r and cell.column_index==c), None)
                row.append(cell.content if cell else "")
            rows.append(row)
        tables.append(rows)
    return {"text": text, "tables": tables}
