"""
Scorer Agent

Calculates compliance scores for policies.

Input: {"policy": "...", "gaps": [...], "total_requirements": 100}
Output: {"overall_score": 0.67, "breakdown": {...}, "trend": [...]}
"""
from typing import Dict, Any
from agents.base_agent import BaseAgent


class ScorerAgent(BaseAgent):
    """Scorer Agent - Calculates compliance scores."""

    def __init__(self, sector=None):
        super().__init__("ScorerAgent", sector)

    def validate_input(self, input_data: Any) -> bool:
        if not isinstance(input_data, dict):
            return False
        return "policy" in input_data or "gaps" in input_data

    def execute(self, input_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        from tools.scoring_tools import (
            calculate_score, build_score_record,
            save_score_record, load_score_history, build_trend,
        )
        from config.settings import settings

        gaps = input_data.get("gaps", [])
        total_requirements = input_data.get("total_requirements", settings.DEFAULT_TOTAL_REQUIREMENTS)
        policy_name = input_data.get("policy_name", "unnamed")

        self.logger.info(f"Scoring: {len(gaps)} gaps / {total_requirements} requirements")

        # 1. Calculate weighted score
        score_result = calculate_score(gaps, total_requirements)

        # 2. Persist to history
        record = build_score_record(score_result, self.sector, policy_name)
        history_path = settings.LOGS_DIR / f"scores_{self.sector}.jsonl"
        save_score_record(record, history_path)

        # 3. Load trend data
        history = load_score_history(history_path, self.sector)
        trend = build_trend(history)

        self.logger.info(
            f"Score: {score_result['percentage']}% ({score_result['grade']}) — "
            f"trend has {len(trend)} data points"
        )

        return {
            **score_result,
            "trend": trend,
            "policy_name": policy_name,
        }

    def format_output(self, result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "success",
            "overall_score": result.get("overall_score", 0.0),
            "percentage": result.get("percentage", 0),
            "grade": result.get("grade", "F"),
            "breakdown": result.get("breakdown", {}),
            "trend": result.get("trend", []),
            "policy_name": result.get("policy_name", ""),
            "sector": self.sector,
        }
