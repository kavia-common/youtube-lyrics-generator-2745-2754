# PDF Description → Image Generator (Console)

Run the console app:

1) Install dependencies:
   pip install -r requirements.txt

2) Apply migrations (standard Django step, though not strictly needed here):
   python manage.py migrate

3) Run the console command:
   python manage.py youtube_lyrics

Flow:
- Enter a PDF URL (http/https) when prompted.
- The tool downloads the PDF to a temporary file and extracts a description (first 'Description' section or the first substantial paragraph).
- An image is generated using a placeholder renderer (Pillow) with the description text.
- The image is saved to 'generated_image.png'. A 'generated_image_manifest.txt' summarizing the inputs (including source URL) is also written.
- The temporary file is deleted at the end of the command, even on most error paths.

Networking & validation:
- Downloads use requests with timeouts and SSL verification.
- The downloader checks for a PDF header signature (%PDF-) and handles non-200 responses.
- Clear error messages are shown for invalid URLs, permission errors, and network failures.

Robust PDF extraction:
- The tool tries multiple backends to extract text:
  1) PyPDF2
  2) pdfplumber
  3) PyMuPDF (fitz)
  4) OCR with pytesseract (for scanned PDFs or when other methods fail; requires the system Tesseract binary)

If OCR is needed, install Tesseract:
- Ubuntu/Debian: `sudo apt-get update && sudo apt-get install -y tesseract-ocr`
- macOS (Homebrew): `brew install tesseract`
- Windows: Install from https://github.com/tesseract-ocr/tesseract and ensure it is on PATH

If extraction fails, the command will print detailed guidance and the errors from each attempted backend.

Notes:
- This implementation avoids any external paid API calls and works locally. OCR requires Tesseract installed system-wide.
- To integrate a real image generation model, replace LyricistAgent._render_placeholder with an API call and ensure proper environment variables are provided. Do not hard-code secrets.
