import os
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from dotenv import load_dotenv
load_dotenv()

client = DocumentIntelligenceClient(
    os.environ["DOCUMENT_INTELLIGENCE_ENDPOINT"],
    AzureKeyCredential(os.environ["DOCUMENT_INTELLIGENCE_KEY"])
)
print("DI client ready:", client is not None)