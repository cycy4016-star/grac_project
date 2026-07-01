"""
PDF Tools

Used by: IngestorAgent
Responsibilities:
- Extract text from law PDFs using pdfplumber
- Detect scanned vs native PDFs
- Save extracted text to parsed/ folder
"""
import re
import json
from pathlib import Path
from typing import Optional


def extract_text_from_pdf(pdf_path: str | Path) -> dict:
    """
    Extract text from a PDF file.

    Tries pdfplumber first (best for structured legal docs).
    Falls back to PyMuPDF if pdfplumber returns nothing.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        {
            "text": str,           # Full extracted text
            "pages": int,          # Page count
            "source": str,         # PDF filename without extension
            "method": str,         # "pdfplumber" | "pymupdf"
            "is_scanned": bool,    # True if no text layer found
        }
    """
    import pdfplumber

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    source = pdf_path.stem
    pages_text = []
    method = "pdfplumber"
    page_count = 0

    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages_text.append(text)

    full_text = "\n".join(pages_text).strip()

    # If pdfplumber got nothing, try PyMuPDF
    if not full_text:
        try:
            import fitz  # PyMuPDF
            method = "pymupdf"
            doc = fitz.open(str(pdf_path))
            page_count = len(doc)
            pages_text = [page.get_text() for page in doc]
            full_text = "\n".join(pages_text).strip()
        except ImportError:
            pass

    is_scanned = (
        len(full_text) < 100
        or (page_count > 1 and len(full_text) / page_count < 50)
    )

    return {
        "text": full_text,
        "pages": page_count,
        "source": source,
        "method": method,
        "is_scanned": is_scanned,
    }


def save_extracted_text(text: str, source: str, output_dir: str | Path) -> Path:
    """
    Save extracted text to the parsed/ directory as a .txt file.

    Args:
        text: Extracted text content
        source: Name of the source (used as filename)
        output_dir: Path to parsed/ directory

    Returns:
        Path to saved file
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Sanitise filename
    safe_name = re.sub(r"[^\w\-_]", "_", source)
    output_path = output_dir / f"{safe_name}.txt"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)

    return output_path


def list_pdfs_in_directory(directory: str | Path) -> list[Path]:
    """Return all PDF files in a directory (non-recursive)."""
    directory = Path(directory)
    return sorted(directory.glob("*.pdf"))
