from __future__ import annotations

from functools import lru_cache

from agents.supervisor import SupervisorAgent


@lru_cache(maxsize=1)
def get_supervisor() -> SupervisorAgent:
    return SupervisorAgent()
