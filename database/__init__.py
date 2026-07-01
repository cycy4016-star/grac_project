"""GRaC Database Module"""

from database.connection import (
    Base,
    create_tables,
    drop_tables,
    get_db,
    get_db_session,
    get_engine,
    init_db,
)

from database.models import (
    AuditLog,
    ComplianceQuestion,
    ComplianceScore,
    GapFinding,
    LawSource,
    PolicyAnalysis,
    VoiceTranscription,
)

from database.queries import (
    # Analysis
    create_analysis,
    get_analysis,
    list_analyses,
    count_analyses,
    # Gaps
    add_gaps,
    get_gaps_for_analysis,
    count_gaps_by_severity,
    # Scores
    create_score,
    get_score_for_analysis,
    get_score_history,
    # Q&A
    create_question,
    get_question,
    search_questions,
    # Voice
    create_transcription_log,
    # Audit
    log_audit_event,
    get_audit_logs,
)

__all__ = [
    "Base",
    "create_tables",
    "drop_tables",
    "get_db",
    "get_db_session",
    "get_engine",
    "init_db",
    "AuditLog",
    "ComplianceQuestion",
    "ComplianceScore",
    "GapFinding",
    "LawSource",
    "PolicyAnalysis",
    "VoiceTranscription",
    "create_analysis",
    "get_analysis",
    "list_analyses",
    "count_analyses",
    "add_gaps",
    "get_gaps_for_analysis",
    "count_gaps_by_severity",
    "create_score",
    "get_score_for_analysis",
    "get_score_history",
    "create_question",
    "get_question",
    "search_questions",
    "create_transcription_log",
    "log_audit_event",
    "get_audit_logs",
]
