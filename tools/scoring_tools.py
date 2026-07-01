"""
Scoring Tools

Used by: ScorerAgent
Responsibilities:
- Calculate compliance percentage from gap analysis results
- Weight gaps by severity
- Break down scores by category
- Persist historical scores for trend tracking
"""
import json
from datetime import datetime
from pathlib import Path


# Severity weights: how much each severity level reduces the score
SEVERITY_WEIGHTS = {
    "critical": 1.0,
    "high": 0.6,
    "medium": 0.3,
    "low": 0.1,
}


def calculate_score(gaps: list[dict], total_requirements: int) -> dict:
    """
    Calculate a weighted compliance score from a list of gaps.

    The score starts at 100 and is reduced by each gap proportionally
    to its severity weight. Score is floored at 0.

    Args:
        gaps: List of gap dicts from AnalyzerAgent (must have "severity" key)
        total_requirements: Total number of requirements checked

    Returns:
        {
            "overall_score": 0.72,        # 0.0 – 1.0
            "percentage": 72,             # rounded integer
            "grade": "C",                 # A/B/C/D/F
            "penalty_points": 28.0,
            "breakdown": {
                "critical": {"count": 1, "penalty": 10.0},
                "high":     {"count": 2, "penalty": 12.0},
                "medium":   {"count": 2, "penalty": 6.0},
                "low":      {"count": 0, "penalty": 0.0},
            }
        }
    """
    if total_requirements <= 0:
        import logging
        logging.getLogger("scoring_tools").warning(
            f"total_requirements was {total_requirements}, using fallback heuristic"
        )
        total_requirements = max(len(gaps) * 2, 10)  # Sensible fallback

    breakdown = {sev: {"count": 0, "penalty": 0.0} for sev in SEVERITY_WEIGHTS}

    total_penalty = 0.0
    for gap in gaps:
        sev = gap.get("severity", "medium").lower()
        if sev not in SEVERITY_WEIGHTS:
            sev = "medium"
        weight = SEVERITY_WEIGHTS[sev]
        # Each gap's penalty is proportional to its weight and share of requirements
        penalty = (weight / total_requirements) * 100
        breakdown[sev]["count"] += 1
        breakdown[sev]["penalty"] = round(breakdown[sev]["penalty"] + penalty, 2)
        total_penalty += penalty

    total_penalty = min(total_penalty, 100.0)
    percentage = max(0, round(100 - total_penalty))
    overall_score = percentage / 100

    return {
        "overall_score": overall_score,
        "percentage": percentage,
        "grade": _percentage_to_grade(percentage),
        "penalty_points": round(total_penalty, 2),
        "breakdown": breakdown,
    }


def build_score_record(
    score_result: dict,
    sector: str,
    policy_name: str = "unnamed",
) -> dict:
    """
    Build a timestamped score record for persistence.
    """
    return {
        "timestamp": datetime.now().isoformat(),
        "sector": sector,
        "policy_name": policy_name,
        **score_result,
    }


def save_score_record(record: dict, history_path: str | Path) -> None:
    """
    Append a score record to the JSONL history file.

    Args:
        record: Score record from build_score_record()
        history_path: Path to the .jsonl history file
    """
    history_path = Path(history_path)
    history_path.parent.mkdir(parents=True, exist_ok=True)

    with open(history_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def load_score_history(history_path: str | Path, sector: str) -> list[dict]:
    """
    Load all score records for a given sector from the history file.

    Returns:
        List of score records (oldest first), empty list if file not found
    """
    history_path = Path(history_path)
    if not history_path.exists():
        return []

    records = []
    with open(history_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                if record.get("sector") == sector:
                    records.append(record)
            except json.JSONDecodeError:
                continue

    return sorted(records, key=lambda r: r.get("timestamp", ""))


def build_trend(history: list[dict]) -> list[dict]:
    """
    Reduce score history to a trend list suitable for charting.

    Returns:
        [{"date": "2025-01-15", "percentage": 72, "grade": "C"}, ...]
    """
    trend = []
    for record in history:
        trend.append(
            {
                "date": record["timestamp"][:10],
                "percentage": record.get("percentage", 0),
                "grade": record.get("grade", "F"),
            }
        )
    return trend


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _percentage_to_grade(pct: int) -> str:
    if pct >= 90:
        return "A"
    elif pct >= 75:
        return "B"
    elif pct >= 60:
        return "C"
    elif pct >= 45:
        return "D"
    else:
        return "F"
