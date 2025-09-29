from dataclasses import dataclass
from typing import Optional
import re
import os

try:
    # PyPDF2 is a common, lightweight PDF library suitable for simple text extraction
    import PyPDF2  # type: ignore
except Exception:  # pragma: no cover
    PyPDF2 = None  # type: ignore


@dataclass
class WatcherResult:
    """Holds the result of reading a PDF and extracting a description."""
    success: bool
    description: Optional[str] = None
    error: Optional[str] = None
    details: Optional[str] = None


class WatcherAgent:
    """
    PUBLIC_INTERFACE
    Reads a local PDF file and extracts a description text.

    Strategy:
    1) Open the given PDF file path.
    2) Extract text from the first few pages.
    3) Heuristically identify the first major block or a 'description' field.
       - Prefer a section headed by 'Description' (case-insensitive).
       - Otherwise, use the first non-trivial paragraph as the description.

    Notes:
    - This avoids external services and works locally.
    - For more robust parsing (layouts, tables), consider integrating pdfminer.six.
    """

    # PUBLIC_INTERFACE
    def get_description_from_pdf(self, pdf_path: str) -> WatcherResult:
        """
        Extract a description from a local PDF file.

        Parameters:
            pdf_path: Path to a local PDF file.

        Returns:
            WatcherResult with success flag and description or error details.
        """
        if not pdf_path or not pdf_path.strip():
            return WatcherResult(
                success=False,
                error="No PDF path provided.",
                details="Please provide a valid path to a PDF file."
            )

        path = pdf_path.strip()
        if not os.path.exists(path) or not os.path.isfile(path):
            return WatcherResult(
                success=False,
                error="PDF file does not exist.",
                details=f"Provided path: {path}"
            )

        if PyPDF2 is None:
            return WatcherResult(
                success=False,
                error="PyPDF2 is not installed.",
                details="Install PyPDF2 in your environment to enable PDF text extraction."
            )

        try:
            text = self._extract_text_with_pypdf2(path)
        except Exception as e:
            return WatcherResult(
                success=False,
                error="Failed to extract text from PDF.",
                details=str(e)
            )

        description = self._find_description_block(text)
        if not description:
            return WatcherResult(
                success=False,
                error="No suitable description text found in the PDF.",
                details="Ensure the PDF contains readable text (not images only)."
            )

        return WatcherResult(success=True, description=description)

    def _extract_text_with_pypdf2(self, path: str) -> str:
        # Read the first few pages to find a description; limit to avoid heavy processing.
        chunks = []
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)  # type: ignore
            num_pages = min(len(reader.pages), 5)  # read at most first 5 pages
            for i in range(num_pages):
                page = reader.pages[i]
                # extract_text can be None; handle gracefully
                page_text = page.extract_text() or ""
                chunks.append(page_text)
        raw = "\n".join(chunks)
        # Normalize whitespace
        raw = re.sub(r"\r", "\n", raw)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()

    def _find_description_block(self, text: str) -> str:
        """
        Attempt to find a 'Description' section; otherwise pick the first meaningful paragraph.
        """
        if not text:
            return ""

        # 1) Look for a 'Description' heading and capture its following paragraph(s)
        #    We capture up to the next heading-like line or a blank line block.
        lines = [l.strip() for l in text.split("\n")]
        for idx, line in enumerate(lines):
            if re.match(r"^\s*description\s*[:\-]?\s*$", line, flags=re.IGNORECASE):
                block = []
                for j in range(idx + 1, len(lines)):
                    if self._looks_like_heading(lines[j]):
                        break
                    block.append(lines[j])
                candidate = self._normalize_paragraphs(block)
                candidate = candidate.strip()
                if candidate:
                    # Limit length to a reasonable size to fit in image
                    return candidate[:1200].strip()

        # 2) Fallback: take the first non-trivial paragraph
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        for p in paragraphs:
            # ignore boilerplate like headers or very short lines
            if len(p) >= 40:
                return p[:1200].strip()

        # 3) Last resort: return the first 300 chars of the raw text
        return text[:300].strip()

    def _looks_like_heading(self, line: str) -> bool:
        if not line:
            return False
        # Heuristics: lines that are short and Title Case or all caps often are headings.
        if len(line) <= 4:
            return True
        if line.isupper() and len(line) <= 60:
            return True
        if re.match(r"^[A-Z][A-Za-z0-9 ]{0,60}$", line) and len(line.split()) <= 8:
            return True
        return False

    def _normalize_paragraphs(self, lines: list[str]) -> str:
        buf = []
        cur = []
        for l in lines:
            if not l:
                if cur:
                    buf.append(" ".join(cur))
                    cur = []
                continue
            cur.append(l)
        if cur:
            buf.append(" ".join(cur))
        # Join paragraphs with a blank line
        return "\n\n".join(buf)
