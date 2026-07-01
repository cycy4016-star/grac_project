"""
Parsing Tools

Used by: ParserAgent
Responsibilities:
- Identify hierarchical structure in extracted legal text
- Split text into chunks at section/subsection boundaries
- Attach metadata (law name, part, section, subsection) to each chunk
"""
import re
import json
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Regex patterns for Ghanaian legal document structure
# ---------------------------------------------------------------------------

PATTERNS = {
    "part":       re.compile(r"^PART\s+([IVXLCDM\d]+)[.\s]*(.*)$", re.IGNORECASE | re.MULTILINE),
    "section":    re.compile(r"^(\d+)\.\s+(.+)$", re.MULTILINE),
    "subsection": re.compile(r"^\s*\((\d+)\)\s+(.+)$", re.MULTILINE),
    "paragraph":  re.compile(r"^\s*\(([a-z])\)\s+(.+)$", re.MULTILINE),
    "schedule":   re.compile(r"^SCHEDULE\s*(.*)?$", re.IGNORECASE | re.MULTILINE),
}


def parse_hierarchy(text: str, law_name: str) -> dict:
    """
    Parse extracted law text into a hierarchical structure.

    Returns:
        {
            "law_name": str,
            "parts": [
                {
                    "number": "I",
                    "title": "Preliminary",
                    "sections": [
                        {
                            "number": "1",
                            "title": "Interpretation",
                            "text": "...",
                            "subsections": [...]
                        }
                    ]
                }
            ],
            "schedules": [...]
        }
    """
    lines = text.split("\n")
    hierarchy = {"law_name": law_name, "parts": [], "schedules": []}

    current_part = None
    current_section = None
    section_buffer = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_section is not None:
                section_buffer.append("")
            continue

        # Check for Part header
        part_match = PATTERNS["part"].match(stripped)
        if part_match:
            # Save pending section
            if current_section is not None:
                current_section["text"] = "\n".join(section_buffer).strip()
                section_buffer = []

            current_part = {
                "number": part_match.group(1).strip(),
                "title": part_match.group(2).strip(),
                "sections": [],
            }
            hierarchy["parts"].append(current_part)
            current_section = None
            continue

        # Check for Schedule
        sched_match = PATTERNS["schedule"].match(stripped)
        if sched_match:
            if current_section is not None:
                current_section["text"] = "\n".join(section_buffer).strip()
                section_buffer = []
            hierarchy["schedules"].append(
                {"title": sched_match.group(1).strip() or "Schedule", "text": ""}
            )
            current_section = None
            continue

        # Check for numbered section: "1. Interpretation"
        sec_match = PATTERNS["section"].match(stripped)
        if sec_match:
            # Save previous section
            if current_section is not None:
                current_section["text"] = "\n".join(section_buffer).strip()
                section_buffer = []

            current_section = {
                "number": sec_match.group(1),
                "title": sec_match.group(2).strip(),
                "text": "",
                "subsections": [],
            }
            if current_part is not None:
                current_part["sections"].append(current_section)
            else:
                # Sections before any Part heading — create a default part
                default_part = next(
                    (p for p in hierarchy["parts"] if p["number"] == "0"), None
                )
                if default_part is None:
                    default_part = {"number": "0", "title": "General", "sections": []}
                    hierarchy["parts"].insert(0, default_part)
                default_part["sections"].append(current_section)
                current_part = default_part
            continue

        # Accumulate lines into current section
        if current_section is not None:
            section_buffer.append(line)

    # Flush final section
    if current_section is not None:
        current_section["text"] = "\n".join(section_buffer).strip()

    return hierarchy


def build_chunks(hierarchy: dict, chunk_size: int = 500, overlap: int = 100) -> list[dict]:
    """
    Convert hierarchical structure into flat, overlapping text chunks.

    Each chunk carries full metadata for ChromaDB storage.

    Args:
        hierarchy: Output of parse_hierarchy()
        chunk_size: Target chunk size in words
        overlap: Overlap in words between adjacent chunks

    Returns:
        List of chunk dicts:
        {
            "id": "act843_p1_s3_chunk0",
            "text": "...",
            "metadata": {
                "law_name": "Act 843",
                "part_number": "I",
                "part_title": "Preliminary",
                "section_number": "3",
                "section_title": "Application",
                "chunk_index": 0,
            }
        }
    """
    if chunk_size <= 0:
        raise ValueError(f"chunk_size must be > 0, got {chunk_size}")

    stride = max(chunk_size - overlap, 1)

    chunks = []
    law_name = hierarchy.get("law_name", "unknown")
    law_slug = re.sub(r"\s+", "_", law_name.lower())
    doc_counter = 0

    for part in hierarchy.get("parts", []):
        for section in part.get("sections", []):
            section_text = f"{section['number']}. {section['title']}\n{section['text']}"
            words = section_text.split()
            if not words:
                continue

            start = 0
            chunk_index = 0
            while start < len(words):
                end = min(start + chunk_size, len(words))
                chunk_text = " ".join(words[start:end])

                chunk_id = (
                    f"{law_slug}_chunk{doc_counter}"
                )
                doc_counter += 1
                chunks.append(
                    {
                        "id": chunk_id,
                        "text": chunk_text,
                        "metadata": {
                            "law_name": law_name,
                            "part_number": str(part["number"]),
                            "part_title": part["title"],
                            "section_number": str(section["number"]),
                            "section_title": section["title"],
                            "chunk_index": chunk_index,
                        },
                    }
                )

                if end == len(words):
                    break
                start += stride
                chunk_index += 1

    return chunks


def extract_metadata(text: str) -> dict:
    """
    Extract top-level law metadata from the opening lines of the text.

    Returns:
        {
            "law_number": "843",
            "year": "2012",
            "title": "Data Protection Act",
            "commencement_date": "...",
        }
    """
    metadata = {"law_number": None, "year": None, "title": None, "commencement_date": None}

    # Look for "Act NNN" or "Act, YYYY"
    act_match = re.search(r"Act[,\s]+(\d{3,4})", text[:2000], re.IGNORECASE)
    if act_match:
        metadata["law_number"] = act_match.group(1)

    year_match = re.search(r"\b(19|20)\d{2}\b", text[:500])
    if year_match:
        metadata["year"] = year_match.group(0)

    # Title is usually the first ALL-CAPS line
    for line in text.split("\n")[:20]:
        if line.isupper() and len(line) > 10:
            metadata["title"] = line.strip().title()
            break

    return metadata


def save_chunks(chunks: list[dict], output_dir: str | Path) -> Path:
    """
    Save chunks as a JSON file to the chunks/ directory.

    Returns:
        Path to saved file
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not chunks:
        out_path = output_dir / "empty.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump([], f)
        return out_path

    law_slug = re.sub(r"\s+", "_", chunks[0]["metadata"]["law_name"].lower())
    output_path = output_dir / f"{law_slug}_chunks.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    return output_path
