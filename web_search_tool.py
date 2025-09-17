
from __future__ import annotations
from ddgs import DDGS
from urllib.parse import urlparse
from typing import Optional, List, Dict, Any
import json
import time


# Optional domain governance (tune as you like)
DEFAULT_ALLOW = [
    # Neutral / reputable
    "reuters.com", "bloomberg.com", "bbc.com",
    "ec.europa.eu", "oecd.org", "iso.org",
    "mckinsey.com", "bain.com", "pwc.com",
    "gartner.com", "forrester.com"
]
DEFAULT_DENY = [
    # Low-signal or social
    "reddit.com", "quora.com", "pinterest.com", "linkedin.com"
]


def web_search(
    query: str,
    max_results: int = 20,
    timelimit: str = "y",       # 'd','w','m','y' supported by ddgs
    region: str = "eu-en",
    safesearch: str = "moderate",
    allow_domains: Optional[List[str]] = None,
    deny_domains: Optional[List[str]] = None
) -> str:
    """
    Perform a DuckDuckGo search via ddgs and return a JSON string.

    Parameters
    ----------
    query : str
        The search query.
    max_results : int, default=20
        Max number of deduplicated results to return.
    timelimit : str, default="y"
        Restrict results to a time window: 'd' (day), 'w' (week), 'm' (month), 'y' (year).
    region : str, default="eu-en"
        Locale hint (see ddgs docs).
    safesearch : str, default="moderate"
        'off' | 'moderate' | 'strict'.
    allow_domains : list[str] | None
        If provided, only include results whose domain matches this allowlist (plus DEFAULT_ALLOW).
    deny_domains : list[str] | None
        Domains to exclude (combined with DEFAULT_DENY).

    Returns
    -------
    str
        JSON string with shape:
        {
          "results": [
            {"title": "...", "url": "...", "snippet": "...", "domain": "...", "published": "...(optional)"}
          ],
          "meta": {"query": "...", "generated_at": 173... (epoch), "count": N}
        }
    """
    # Merge governance lists (keep them sets for quick checks)
    allow = set((allow_domains or []) + DEFAULT_ALLOW)
    deny = set(DEFAULT_DENY + (deny_domains or []))

    # Try to start the search iterator
    try:
        search_iter = DDGS().text(
            query=query,
            max_results=max_results,  # ddgs may yield fewer; we still dedupe below
            timelimit=timelimit,
            region=region,
            safesearch=safesearch,
        )
    except Exception as e:
        return json.dumps({
            "results": [],
            "meta": {"query": query, "generated_at": int(time.time())},
            "error": f"ddgs init error: {e}"
        }, ensure_ascii=False)

    results: List[Dict[str, Any]] = []
    seen_urls: set[str] = set()

    try:
        for r in search_iter or []:
            # Extract minimal fields
            url = (r.get("href") or "").strip()
            if not url or url in seen_urls:
                continue

            domain = urlparse(url).netloc.lower()

            # Deny first
            if any(domain.endswith(d) or d in domain for d in deny):
                continue

            # If allowlist present, require at least a partial match
            if allow and not any(domain.endswith(a) or a in domain for a in allow):
                continue

            results.append({
                "title": r.get("title") or "",
                "url": url,
                "snippet": r.get("body") or "",
                "domain": domain,
                # ddgs sometimes exposes a date-ish key; keep it optional
                "published": r.get("published") or r.get("date") or None,
            })
            seen_urls.add(url)

            if len(results) >= max_results:
                break
    except Exception as e:
        return json.dumps({
            "results": [],
            "meta": {"query": query, "generated_at": int(time.time())},
            "error": f"ddgs iteration error: {e}"
        }, ensure_ascii=False)

    payload = {
        "results": results,
        "meta": {
            "query": query,
            "generated_at": int(time.time()),
            "count": len(results),
            "timelimit": timelimit,
            "region": region,
            "safesearch": safesearch
        }
    }
    return json.dumps(payload, ensure_ascii=False)
