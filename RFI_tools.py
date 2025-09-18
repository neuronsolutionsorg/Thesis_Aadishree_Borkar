# rfi_tools.py
import io
import json
import os
import tempfile
from typing import Dict, List

from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

from utils.document_intelligence_handler import DocumentIntelligenceHandler
from utils.handler_result import HandlerResult

load_dotenv()
ACCOUNT_URL = os.environ["AZURE_STORAGE_ACCOUNT_URL"]
CONTAINER = os.environ.get("RFI_CONTAINER", "rfi-submissions")
RESULTS_CONTAINER = os.environ.get("RFI_RESULTS_CONTAINER", "rfi-results")

# Blob client
conn_str = os.environ["AZURE_STORAGE_CONNECTION_STRING"]
_blob = BlobServiceClient.from_connection_string(conn_str)

# Document Intelligence handler (reads its own env vars)
di_handler = DocumentIntelligenceHandler(
    model_type="documentModels",
    model_id="prebuilt-layout",
    output_content_format="text",
)


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


def extract_text_tables(file_bytes: bytes, mime_type: str = None) -> Dict:
    """
    Use prebuilt layout/Read to extract plain text and tables.
    """
    # Persist bytes to a temp file for the handler
    suffix = ".bin"
    if mime_type == "application/pdf":
        suffix = ".pdf"
    elif (
        mime_type
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ):
        suffix = ".docx"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    res: HandlerResult = di_handler(tmp_path)
    if not res.success:
        raise RuntimeError(f"Document Intelligence failed: {res.error}")

    analyze_result = (res.content or {}).get("analyzeResult", {})
    text = analyze_result.get("content", "") or ""

    tables_out: List[List[List[str]]] = []
    for t in analyze_result.get("tables", []) or []:
        row_count = int(t.get("rowCount") or 0)
        col_count = int(t.get("columnCount") or 0)
        grid = [["" for _ in range(col_count)] for _ in range(row_count)]
        for cell in t.get("cells", []) or []:
            r = int(cell.get("rowIndex") or 0)
            c = int(cell.get("columnIndex") or 0)
            if 0 <= r < row_count and 0 <= c < col_count:
                grid[r][c] = cell.get("content") or ""
        tables_out.append(grid)

    return {"text": text, "tables": tables_out}
