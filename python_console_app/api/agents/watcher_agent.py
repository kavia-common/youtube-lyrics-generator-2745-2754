from dataclasses import dataclass
from typing import Optional, List, Tuple
import re
import os
import io

# Primary lightweight backend
try:
    import PyPDF2  # type: ignore
except Exception:  # pragma: no cover
    PyPDF2 = None  # type: ignore

# Fallback backends for robustness against malformed files
try:
    import pdfplumber  # type: ignore
except Exception:  # pragma: no cover
    pdfplumber = None  # type: ignore

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None  # type: ignore

# OCR fallback for scanned/image-based PDFs
try:
    import pytesseract  # type: ignore
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover
    pytesseract = None  # type: ignore
    Image = None  # type: ignore


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
    Reads a PDF file and extracts a description text.

    Strategy (robust, multi-backend):
    1) Try PyPDF2 (fast, lightweight).
    2) Fallback to pdfplumber (better layout handling and resilience).
    3) Fallback to PyMuPDF/fitz (robust parser, handles malformed PDFs).
    4) As a last resort, OCR pages using pytesseract (for scanned or severely malformed PDFs).

    Then:
    - Heuristically identify a 'Description' section or first non-trivial paragraph.

    Notes:
    - OCR requires Tesseract installed on the system. If unavailable, we provide
      actionable instructions in the error details.
    - This agent operates on a local file path. For URLs, download to a temp file first.
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

        texts: List[Tuple[str, str]] = []  # [(source, text)]
        errors: List[str] = []

        # 1) PyPDF2
        if PyPDF2 is not None:
            try:
                texts.append(("PyPDF2", self._extract_text_with_pypdf2(path)))
            except Exception as e:
                errors.append(f"PyPDF2 failed: {e}")

        # 2) pdfplumber
        if pdfplumber is not None:
            try:
                texts.append(("pdfplumber", self._extract_text_with_pdfplumber(path)))
            except Exception as e:
                errors.append(f"pdfplumber failed: {e}")
        else:
            errors.append("pdfplumber not installed.")

        # 3) PyMuPDF/fitz
        if fitz is not None:
            try:
                texts.append(("PyMuPDF", self._extract_text_with_pymupdf(path)))
            except Exception as e:
                errors.append(f"PyMuPDF failed: {e}")
        else:
            errors.append("PyMuPDF (fitz) not installed.")

        # 4) OCR fallback (only if we still have no text or very short text)
        best_text = self._pick_best_text([t for _, t in texts])
        used_backend = None
        if best_text:
            # Find which backend produced non-empty text
            for backend, t in texts:
                if t and t.strip():
                    used_backend = backend
                    break
        if not best_text or len(best_text.strip()) < 40:
            if pytesseract is not None and fitz is not None:
                try:
                    ocr_text = self._extract_text_with_ocr(path, max_pages=3)
                    if ocr_text and len(ocr_text.strip()) > len(best_text or ""):
                        best_text = ocr_text
                        used_backend = "OCR(pytesseract)+PyMuPDF"
                except Exception as e:
                    errors.append(f"OCR fallback failed: {e}")
            else:
                if pytesseract is None:
                    errors.append("OCR not available: pytesseract not installed.")
                if fitz is None:
                    errors.append("OCR requires PyMuPDF (fitz) to rasterize pages to images.")

        text = self._normalize_whitespace(best_text or "")

        description = self._find_description_block(text)
        if not description:
            # Provide richer error feedback and guidance.
            guidance = self._build_guidance_message(errors)
            return WatcherResult(
                success=False,
                error="No suitable description text found in the PDF.",
                details=guidance
            )

        # If we got a description, but the backend used is useful to mention for diagnostics
        backend_note = f"Extracted via: {used_backend}" if used_backend else "Extracted via: Unknown backend"
        final_desc = description
        return WatcherResult(success=True, description=final_desc, details=backend_note)

    def _extract_text_with_pypdf2(self, path: str) -> str:
        chunks: List[str] = []
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)  # type: ignore
            num_pages = min(len(reader.pages), 5)
            for i in range(num_pages):
                page = reader.pages[i]
                page_text = page.extract_text() or ""
                chunks.append(page_text)
        return self._normalize_whitespace("\n".join(chunks))

    def _extract_text_with_pdfplumber(self, path: str) -> str:
        chunks: List[str] = []
        with pdfplumber.open(path) as pdf:  # type: ignore
            num_pages = min(len(pdf.pages), 5)
            for i in range(num_pages):
                page = pdf.pages[i]
                page_text = page.extract_text() or ""
                chunks.append(page_text)
        return self._normalize_whitespace("\n".join(chunks))

    def _extract_text_with_pymupdf(self, path: str) -> str:
        chunks: List[str] = []
        doc = fitz.open(path)  # type: ignore
        try:
            num_pages = min(doc.page_count, 5)
            for i in range(num_pages):
                page = doc.load_page(i)
                # Use text extraction method that balances reliability
                page_text = page.get_text("text") or ""  # "text" often yields linearized text
                chunks.append(page_text)
        finally:
            doc.close()
        return self._normalize_whitespace("\n".join(chunks))

    def _extract_text_with_ocr(self, path: str, max_pages: int = 3) -> str:
        """
        Render first N pages to images and run OCR.
        Requires: fitz (PyMuPDF) for rendering and pytesseract + Tesseract binary.
        """
        if pytesseract is None or fitz is None:
            return ""

        # OCR hint: User might need to install Tesseract system binary.
        # This code will raise if tesseract is not on PATH.
        texts: List[str] = []
        doc = fitz.open(path)  # type: ignore
        try:
            pages = min(doc.page_count, max_pages)
            for i in range(pages):
                page = doc.load_page(i)
                # Render at 2x scale for better OCR quality
                mat = fitz.Matrix(2, 2)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img_bytes = pix.tobytes("png")
                if Image is None:
                    continue
                image = Image.open(io.BytesIO(img_bytes))
                ocr_text = pytesseract.image_to_string(image)  # type: ignore
                if ocr_text:
                    texts.append(ocr_text)
        finally:
            doc.close()

        return self._normalize_whitespace("\n".join(texts))

    def _pick_best_text(self, candidates: List[str]) -> str:
        """
        Pick the 'best' text by length (simple heuristic); prefers longer content.
        """
        best = ""
        for c in candidates:
            if c and len(c.strip()) > len(best.strip()):
                best = c
        return best

    def _normalize_whitespace(self, raw: str) -> str:
        if not raw:
            return ""
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

        lines = [l.strip() for l in text.split("\n")]
        for idx, line in enumerate(lines):
            if re.match(r"^\s*description\s*[:\-]?\s*$", line, flags=re.IGNORECASE):
                block: List[str] = []
                for j in range(idx + 1, len(lines)):
                    if self._looks_like_heading(lines[j]):
                        break
                    block.append(lines[j])
                candidate = self._normalize_paragraphs(block).strip()
                if candidate:
                    return candidate[:1200].strip()

        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        for p in paragraphs:
            if len(p) >= 40:
                return p[:1200].strip()

        return text[:300].strip()

    def _looks_like_heading(self, line: str) -> bool:
        if not line:
            return False
        if len(line) <= 4:
            return True
        if line.isupper() and len(line) <= 60:
            return True
        if re.match(r"^[A-Z][A-Za-z0-9 ]{0,60}$", line) and len(line.split()) <= 8:
            return True
        return False

    def _normalize_paragraphs(self, lines: List[str]) -> str:
        buf: List[str] = []
        cur: List[str] = []
        for l in lines:
            if not l:
                if cur:
                    buf.append(" ".join(cur))
                    cur = []
                continue
            cur.append(l)
        if cur:
            buf.append(" ".join(cur))
        return "\n\n".join(buf)

    def _build_guidance_message(self, errors: List[str]) -> str:
        """
        Build an actionable details message enumerating attempted backends and how to fix common issues.
        """
        hints = [
            "- Ensure the PDF contains selectable text. If it's scanned, OCR is required.",
            "- If OCR failed, install the Tesseract binary and language data:",
            "  • Ubuntu/Debian: sudo apt-get update && sudo apt-get install -y tesseract-ocr",
            "  • macOS (Homebrew): brew install tesseract",
            "  • Windows: Install from https://github.com/tesseract-ocr/tesseract and ensure it is on PATH",
            "- Re-run after installing system dependencies and Python packages.",
        ]
        attempted = "\n".join(f"* {e}" for e in errors) if errors else "* No errors captured (empty text)."
        return (
            "Tried multiple extraction backends but could not obtain a suitable description.\n\n"
            "Attempted backends and errors:\n"
            f"{attempted}\n\n"
            "How to proceed:\n"
            + "\n".join(hints)
        )
