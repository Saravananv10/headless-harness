import io
import os
from typing import Tuple

from pypdf import PdfReader
from docx import Document


def extract_text(file_bytes: bytes, filename: str, mime: str) -> str:
    """Extract plain text from supported file types.

    Supported extensions (case‑insensitive):
    - .txt  – raw UTF‑8 text
    - .pdf  – PDF parsed with pypdf (text‑only PDFs)
    - .docx – Word documents via python‑docx

    Returns the extracted text or raises a ``ValueError`` if the content cannot be
    extracted (e.g., scanned PDF with no text).
    """
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".txt":
        return file_bytes.decode("utf-8", errors="replace")
    if ext == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            text = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text.append(page_text)
            if not text:
                raise ValueError("PDF contains no extractable text (possible scanned image)")
            return "\n".join(text)
        except Exception as e:
            raise ValueError(f"Failed to parse PDF: {e}")
    if ext == ".docx":
        try:
            doc = Document(io.BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception as e:
            raise ValueError(f"Failed to parse DOCX: {e}")
    raise ValueError(f"Unsupported file type: {ext}")
