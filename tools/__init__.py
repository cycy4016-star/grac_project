"""
GRaC Tools Module

All specialized tools for agents to use.
"""

# PDF ingestion
from tools.pdf_tools import (
    extract_text_from_pdf,
    save_extracted_text,
    list_pdfs_in_directory,
)

# Hierarchical parsing & chunking
from tools.parsing_tools import (
    parse_hierarchy,
    build_chunks,
    extract_metadata,
    save_chunks,
)

# Vector embeddings & ChromaDB
from tools.embedding_tools import (
    get_chroma_client,
    get_or_create_collection,
    get_collection_name,
    load_embedding_model,
    embed_chunks,
    query_collection,
    collection_exists,
    get_collection_count,
)

# LLM calls (multi-provider)
from tools.llm_providers import call_llm, NVIDIAProvider, OpenAIProvider, AnthropicProvider
from tools.llm_tools import (
    call_claude,
    call_openai,
    build_gap_analysis_prompt,
    build_compliance_qa_prompt,
    build_document_prompt,
    parse_json_response,
)

# Scoring
from tools.scoring_tools import (
    calculate_score,
    build_score_record,
    save_score_record,
    load_score_history,
    build_trend,
)

# Audio transcription
from tools.audio_tools import (
    validate_audio_file,
    transcribe_audio,
    transcribe_audio_data,
    clean_transcript,
    estimate_confidence,
)

# Web research
from tools.web_research_tools import (
    search_web,
    search_grc_laws,
    search_specific_law,
    format_search_results,
    fetch_page_text,
)

# Document generation
from tools.document_tools import (
    generate_pdf,
    generate_docx,
)
