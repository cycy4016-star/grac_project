"""
Web Research Agent

Searches the web for GRC laws, regulations, and compliance information
to supplement or replace ChromaDB retrieval.

Input: {"query": "...", "sector": "...", "law_name": "...", "top_k": 5}
Output: {"results": [...], "formatted": "...", "count": N}
"""
from typing import Dict, Any
from agents.base_agent import BaseAgent


class WebResearchAgent(BaseAgent):
    """Web Research Agent - Searches the web for GRC laws and info."""

    def __init__(self, sector=None):
        super().__init__("WebResearchAgent", sector)

    def validate_input(self, input_data: Any) -> bool:
        if not isinstance(input_data, dict):
            return False
        return bool(input_data.get("query") or input_data.get("law_name"))

    def execute(self, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        from tools.web_research_tools import search_grc_laws, search_specific_law, format_search_results, fetch_page_text

        query = input_data.get("query", "")
        law_name = input_data.get("law_name", "")
        sector = input_data.get("sector", self.sector)
        top_k = input_data.get("top_k", 5)
        fetch_detail = input_data.get("fetch_detail", False)

        results = []

        if law_name:
            self.logger.info(f"Searching for specific law: {law_name}")
            results = search_specific_law(law_name, max_results=top_k)
        elif query:
            self.logger.info(f"Searching web for: {query[:100]}...")
            results = search_grc_laws(query, sector=sector, max_results=top_k)
        else:
            return {"results": [], "formatted": "", "count": 0}

        if isinstance(results, dict):
            self.logger.warning(f"Search failed: {results.get('error')}")
            return {"results": [], "formatted": f"Search failed: {results['error']}", "count": 0}

        # Optionally fetch full page text from the top result
        detailed = None
        if fetch_detail and results:
            top_url = results[0].get("url", "")
            if top_url:
                self.logger.info(f"Fetching details from: {top_url}")
                detailed = fetch_page_text(top_url)

        formatted = format_search_results(results)

        return {
            "results": results,
            "formatted": formatted,
            "detailed": detailed,
            "count": len(results),
            "query": query or law_name,
        }

    def format_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "success",
            "results": result.get("results", []),
            "formatted": result.get("formatted", ""),
            "detailed": result.get("detailed"),
            "count": result.get("count", 0),
            "sector": self.sector,
        }
