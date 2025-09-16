import base64
import json
import logging
import os
import time
import traceback
import uuid
from typing import Dict, Literal, Union

import requests

from .handler_result import HandlerResult


class DocumentIntelligenceHandler:
    logger = logging.getLogger("neuron_public")

    def __init__(
        self,
        model_type: Literal["documentModels", "documentClassifiers"],
        model_id: Union[
            Literal[
                "prebuilt-read",
                "prebuilt-layout",
                "prebuilt-invoice",
                "prebuilt-receipt",
            ],
            str,
        ],
        output_content_format: Literal["text", "markdown"] = "markdown",
        api_version: str = "2024-11-30",
    ):
        """
        Handler for Azure Document Intelligence.
        `DOCUMENT_INTELLIGENCE_ENDPOINT` and `DOCUMENT_INTELLIGENCE_API_KEY` must be set in the environment variables.
        Main function is __call__ which takes a document path and returns the result of the analysis.

        Args:
            model_type (str): The type of model to use. Can be "documentModels" or "documentClassifiers".
            model_id (str): The ID of the model to use for analysis.
            output_content_format (str): The format of the output content. Can be "text" or "markdown".
            api_version (str): Azure Document Intelligence API version to use for requests.
        """
        self._endpoint = os.environ["DOCUMENT_INTELLIGENCE_ENDPOINT"]
        self._api_key = os.environ["DOCUMENT_INTELLIGENCE_API_KEY"]
        self.model_type = model_type
        self.model_id = model_id
        self.output_content_format = output_content_format
        self.api_version = api_version

    def _base64_encode_document(self, document_path: str) -> str:
        """Open a file from the system and base64 encode it.
        Args:
            document_path (str): The path to the document
        Return:
            base64_encoded_doc (str): The encoded document
        """
        if not os.path.exists(document_path):
            raise Exception("File do not exists")
        with open(document_path, "rb") as file:
            return base64.b64encode(file.read()).decode("utf-8")

    def _post_document(self, base64_source: str) -> str:
        """A POST request is used to analyze documents with a prebuilt or custom model
        Args:
            base64_source (str): The base64 encoded document to analyze
        Returns:
            result_url (str): The url from where to retrieve the result
        """
        url = (
            f"{self._endpoint}/documentintelligence/{self.model_type}/"
            f"{self.model_id}:analyze?api-version={self.api_version}&outputContentFormat={self.output_content_format}"
        )
        headers = {
            "Content-Type": "application/json",
            "Ocp-Apim-Subscription-Key": self._api_key,
        }
        data = {"base64Source": base64_source}
        self.logger.debug(
            json.dumps(
                {
                    "fuid": self.fuid,
                    "type": "document_intelligence",
                    "message": "Posting document to Azure Document Intelligence",
                }
            )
        )

        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        return response.headers["Operation-Location"]

    def _get_result(self, result_url: str, delay_time: int, max_retry: int) -> Dict:
        """A GET request is used to retrieve the result of a document analysis call.
        Args:
            result_url (str): The url from where to retrieve the result
            delay_time (int): The time to wait between retries
            max_retry (int): The maximum number of retries
        Returns:
            result (Dict): The result of the document analysis
        """
        for attempt in range(1, max_retry + 1):
            self.logger.debug(
                json.dumps(
                    {
                        "fuid": self.fuid,
                        "type": "document_intelligence",
                        "message": f"Getting result from Azure Document Intelligence, attempt {attempt}",
                    }
                )
            )

            response = requests.get(
                result_url, headers={"Ocp-Apim-Subscription-Key": self._api_key}
            )
            response.raise_for_status()
            response = response.json()
            status = response["status"]
            if status == "succeeded":
                return response
            if status == "failed":
                raise Exception("Document Intelligence failed")

            # If not finished and not failed, wait before next attempt unless this was the last try
            if attempt == max_retry:
                break
            time.sleep(delay_time)

        raise Exception("Max retries reached for Document Intelligence")

    def __call__(
        self,
        document_path: str,
        max_retry: int = 20,
        delay_between_retry: int = 1,
        initial_delay: int = 4,
        fuid: str | None = None,
    ) -> HandlerResult:
        """
        Takes a document path and returns the result of the analysis.

        Functionality:
        1. Base64 encode the document.
        2. Post the document to the Azure Document Intelligence API.
        3. Wait `initial_delay` seconds before starting to get the result.
        4. Get the result from the API.
        5. If no result yet, wait `delay_between_retry` seconds and retry `max_retry` times.
        6. If still no result, raise an exception.
        7. If result is found, return the result.

        Args:
            document_path (str): The path to the document to analyze.
            max_retry (int): The maximum number of retries to get the result.
            delay_between_retry (int): The delay between retries in seconds.
            initial_delay (int): The initial delay before starting to get the result in seconds.
            fuid (str): The file unique identifier for logging.
        Returns:
            HandlerResult: The result of the analysis.
        """
        start_time = time.time()
        self.fuid = fuid if fuid else str(uuid.uuid4())

        try:
            base64_encoded_doc = self._base64_encode_document(document_path)
            result_url = self._post_document(base64_encoded_doc)
            time.sleep(initial_delay)
            result = self._get_result(
                result_url=result_url,
                delay_time=delay_between_retry,
                max_retry=max_retry,
            )

            content = result
            success = True
            log = {"run_time": time.time() - start_time}
            error = None

        except Exception as e:
            self.logger.error(
                {
                    "fuid": self.fuid,
                    "type": "document_intelligence",
                    "message": "Error with Document Intelligence",
                    "error_message": str(e),
                    "error_traceback": traceback.format_exc(),
                }
            )
            content = None
            success = False
            error = str(e)
            log = {
                "traceback": traceback.format_exc(),
                "run_time": time.time() - start_time,
            }

        self.fuid = None
        return HandlerResult(
            content=content,
            success=success,
            log=log,
            error=error,
        )
