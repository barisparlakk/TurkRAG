"""Document text extraction for PDF, DOCX, and TXT files."""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_document(file_path: str) -> str:
    """Extract raw text from a PDF, DOCX, or TXT file.

    Strips common header/footer noise heuristically.
    Returns clean plain text suitable for chunking.
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    logger.info("Parsing document: %s (type=%s)", path.name, suffix)

    if suffix == ".pdf":
        text = _parse_pdf(file_path)
    elif suffix == ".docx":
        text = _parse_docx(file_path)
    elif suffix == ".txt":
        text = _parse_txt(file_path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}. Supported: .pdf, .docx, .txt")

    text = _clean_text(text)
    logger.info("Parsed %d characters from %s", len(text), path.name)
    return text


def _parse_pdf(file_path: str) -> str:
    """Extract text from a PDF using pdfplumber."""
    import pdfplumber

    pages = []
    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_text = page.extract_text()
            if page_text:
                pages.append(page_text)
                logger.debug("PDF page %d: %d chars", i + 1, len(page_text))
    return "\n\n".join(pages)


def _parse_docx(file_path: str) -> str:
    """Extract text from a DOCX file using python-docx."""
    from docx import Document

    doc = Document(file_path)
    paragraphs = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _parse_txt(file_path: str) -> str:
    """Read a plain text file with UTF-8 encoding (fallback to latin-1)."""
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return Path(file_path).read_text(encoding="latin-1")


def _clean_text(text: str) -> str:
    """Remove common header/footer artifacts and normalize whitespace."""
    # Remove page numbers like "- 1 -" or "Sayfa 1/10"
    text = re.sub(r"[-–]\s*\d+\s*[-–]", " ", text)
    text = re.sub(r"[Ss]ayfa\s+\d+\s*/\s*\d+", " ", text)
    text = re.sub(r"\bPage\s+\d+\b", " ", text, flags=re.IGNORECASE)

    # Collapse excessive blank lines (more than 2 in a row)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Normalize unicode whitespace characters
    text = re.sub(r"[\t\r\xa0​]", " ", text)

    # Collapse multiple spaces
    text = re.sub(r" {2,}", " ", text)

    return text.strip()


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if len(sys.argv) < 2:
        print("Usage: python -m ingestion.parser <file_path>")
        sys.exit(1)
    result = parse_document(sys.argv[1])
    print(result[:2000])
    print(f"\n[Total: {len(result)} characters]")
