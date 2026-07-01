"""
Web Research Tools

Used by: WebResearchAgent
Responsibilities:
- Search the web for GRC laws, regulations, and compliance information
- Multi-tier: duckduckgo_search lib → Brave API → Bing scrape → DDG scrape
- Cite sources with URLs and snippets
"""

import re
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_SESSION = None


def _get_session():
    global _SESSION
    if _SESSION is None:
        import requests
        _SESSION = requests.Session()
        _SESSION.headers.update(_HEADERS)
    return _SESSION


def _get_brave_api_key() -> str:
    """Read Brave API key from settings (env var BRAVE_API_KEY)."""
    try:
        from config.settings import settings as s
        return getattr(s, 'BRAVE_API_KEY', '') or ''
    except Exception:
        return ''
    from os import getenv
    return getenv('BRAVE_API_KEY', '')


# ---------------------------------------------------------------------------
# Tier 1: duckduckgo-search library (free, no API key, uses internal DDG API)
# ---------------------------------------------------------------------------

def _search_ddg_lib(query: str, max_results: int = 5) -> list[dict]:
    """Search via the duckduckgo_search library (most reliable free option)."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=max_results))
        results = []
        for r in raw:
            results.append({
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            })
        if results:
            logger.debug("ddg_lib: %d results for '%s'", len(results), query)
        return results
    except Exception as e:
        logger.debug("ddg_lib failed: %s", e)
        return []


# ---------------------------------------------------------------------------
# Tier 2: Brave Search API (free tier, needs BRAVE_API_KEY env var)
# ---------------------------------------------------------------------------

def _search_brave(query: str, max_results: int = 5) -> list[dict]:
    """Search via Brave Search API (requires BRAVE_API_KEY env var)."""
    api_key = _get_brave_api_key()
    if not api_key:
        return []

    try:
        import requests
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": api_key,
            },
            params={"q": query, "count": max_results},
            timeout=10,
        )
        if resp.status_code != 200:
            logger.debug("Brave API returned %d", resp.status_code)
            return []

        data = resp.json()
        web = data.get("web", {})
        raw_results = web.get("results", [])
        results = []
        for r in raw_results:
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("description", ""),
            })
        if results:
            logger.debug("brave: %d results for '%s'", len(results), query)
        return results
    except Exception as e:
        logger.debug("brave search failed: %s", e)
        return []


# ---------------------------------------------------------------------------
# Tier 3: Bing HTML scraping (existing fallback)
# ---------------------------------------------------------------------------

def _search_bing(query: str, max_results: int = 5) -> list[dict]:
    """Scrape Bing search results (fragile fallback)."""
    import requests
    from bs4 import BeautifulSoup

    session = _get_session()
    try:
        resp = session.get(
            "https://www.bing.com/search",
            params={"q": query},
            timeout=15,
        )
        resp.raise_for_status()
    except Exception:
        return []

    if "challenge" in resp.text.lower()[:500] or "captcha" in resp.text.lower()[:500]:
        return []

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for tag in soup.select("#b_results .b_algo"):
            title_tag = tag.select_one("h2 a")
            snippet_tag = tag.select_one(".b_caption p")
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            url = title_tag.get("href", "")
            snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
            results.append({"title": title, "url": url, "snippet": snippet})
            if len(results) >= max_results:
                break
        return results
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Tier 4: DuckDuckGo HTML scraping (final fallback)
# ---------------------------------------------------------------------------

def _search_duckduckgo(query: str, max_results: int = 5) -> list[dict]:
    """Scrape DuckDuckGo HTML results (fragile fallback)."""
    import requests
    from bs4 import BeautifulSoup

    session = _get_session()
    try:
        resp = session.post(
            "https://html.duckduckgo.com/html/",
            data={"q": query},
            timeout=15,
        )
        resp.raise_for_status()
    except Exception:
        return []

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        for tag in soup.select(".result__body"):
            title_tag = tag.select_one(".result__title a")
            snippet_tag = tag.select_one(".result__snippet")
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            url = title_tag.get("href", "")
            snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
            results.append({"title": title, "url": url, "snippet": snippet})
            if len(results) >= max_results:
                break
        return results
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Retry helpers
# ---------------------------------------------------------------------------

def _simplify_query(query: str) -> list[str]:
    """Generate progressively simpler query variants for retry."""
    variants = [query]

    # Remove quotes
    no_quotes = re.sub(r'["\']', '', query)
    if no_quotes != query:
        variants.append(no_quotes)

    # First 8 words
    short = ' '.join(no_quotes.split()[:8])
    if short != no_quotes and short != query:
        variants.append(short)

    # Key terms only (drop common stop words)
    stop_words = {'the', 'a', 'an', 'is', 'what', 'how', 'does', 'do', 'for',
                  'of', 'in', 'on', 'to', 'and', 'or', 'about', 'with', 'as',
                  'at', 'by', 'that', 'this', 'are', 'was', 'were', 'be',
                  'been', 'being', 'have', 'has', 'had', 'not', 'no', 'but'}
    terms = [t for t in no_quotes.split() if t.lower() not in stop_words]
    if len(terms) < len(no_quotes.split()):
        keyword_q = ' '.join(terms[:6])
        if keyword_q not in variants:
            variants.append(keyword_q)

    return variants


# ---------------------------------------------------------------------------
# Main search function
# ---------------------------------------------------------------------------

SEARCH_TIERS = [
    ("duckduckgo_lib", _search_ddg_lib),
    ("brave_api", _search_brave),
    ("bing_scrape", _search_bing),
    ("duckduckgo_scrape", _search_duckduckgo),
]


def search_web(
    query: str,
    max_results: int = 5,
    prefer_tier: Optional[str] = None,
) -> list[dict]:
    """
    Search the web using a multi-tier approach.

    Tries each search backend in order until results are found.
    On empty results, retries with progressively simpler query variants.

    Args:
        query: Search query string
        max_results: Maximum results to return
        prefer_tier: If set, try this tier first before falling back

    Returns:
        List of result dicts: [{"title": ..., "url": ..., "snippet": ...}]
    """
    tiers = list(SEARCH_TIERS)

    # If a preferred tier is specified, move it to front
    if prefer_tier:
        idx = next((i for i, (name, _) in enumerate(tiers) if name == prefer_tier), None)
        if idx is not None:
            tiers.insert(0, tiers.pop(idx))

    variants = _simplify_query(query)
    seen_urls = set()
    all_results = []

    for variant in variants:
        for tier_name, search_fn in tiers:
            time.sleep(0.3)  # Be polite between requests
            try:
                results = search_fn(variant, max_results)
            except Exception:
                continue

            if not results:
                continue

            # Deduplicate by URL
            for r in results:
                url = r.get('url', '')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(r)
                    if len(all_results) >= max_results:
                        return all_results[:max_results]

        if all_results:
            break

    return all_results[:max_results]


# ---------------------------------------------------------------------------
# Domain-specific search helpers
# ---------------------------------------------------------------------------

def search_grc_laws(
    query: str,
    sector: Optional[str] = None,
    max_results: int = 5,
) -> list[dict]:
    """
    Search for GRC laws biased toward Ghanaian sources.

    Automatically prepends Ghana/GRC context to the query.

    Args:
        query: User's question or topic
        sector: Optional sector filter
        max_results: Max results to return

    Returns:
        List of result dicts
    """
    sector_labels = {
        "cybersecurity": "cybersecurity",
        "fintech": "fintech payments banking",
        "data_protection": "data protection privacy",
        "healthcare": "healthcare medical",
    }

    sector_context = sector_labels.get(sector, "") if sector else ""
    enhanced_query = f"Ghana {sector_context} {query}".strip()

    return search_web(enhanced_query, max_results=max_results)


def search_specific_law(
    law_name: str,
    max_results: int = 5,
) -> list[dict]:
    """
    Search for a specific Ghanaian law by name/number.

    Args:
        law_name: e.g. "Act 1038", "Data Protection Act 2012", "Act 843"
        max_results: Max results to return

    Returns:
        List of result dicts
    """
    query = f"Ghana {law_name} full text PDF"
    return search_web(query, max_results=max_results)


def fetch_page_text(url: str, max_chars: int = 3000) -> str:
    """
    Fetch and extract readable text from a URL.

    Args:
        url: Page URL
        max_chars: Max characters to return

    Returns:
        Extracted text content
    """
    import requests
    from bs4 import BeautifulSoup

    try:
        resp = requests.get(url, timeout=15, headers=_HEADERS)
        resp.raise_for_status()
    except Exception as e:
        return f"Error fetching page: {e}"

    try:
        soup = BeautifulSoup(resp.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text[:max_chars]
    except Exception as e:
        return f"Error parsing page: {e}"


def format_search_results(results: list[dict]) -> str:
    """
    Format search results into a readable context block for LLM prompts.

    Args:
        results: List of result dicts from search_web()

    Returns:
        Formatted string
    """
    if not results:
        return "No web search results found."

    if isinstance(results, dict) and "error" in results:
        return f"Web search unavailable: {results['error']}"

    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "Untitled")
        url = r.get("url", "")
        snippet = r.get("snippet", "")
        lines.append(
            f"[{i}] {title}\n"
            f"    URL: {url}\n"
            f"    {snippet}\n"
        )

    return "\n".join(lines)
