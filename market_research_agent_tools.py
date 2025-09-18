from ddgs import DDGS
import json


def web_search(query: str) -> str:


    results = DDGS().text(query, max_results=5)
    summaries = []

    for r in results:
        title = r.get("title", "")
        body = r.get("body", "")
        href = r.get("href", "")
        summaries.append(f"{title}\n{body}\n{href}")

    return json.dumps({"results": summaries})