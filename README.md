# youtube-lyrics-generator-2745-2754

This console app has been repurposed to:
- Download a PDF from a user-provided URL.
- Extract a description from the PDF (WatcherAgent).
- Generate an image using that description (LyricistAgent) and save it to `generated_image.png`.

Run:
- pip install -r python_console_app/requirements.txt
- cd python_console_app
- python manage.py migrate
- python manage.py youtube_lyrics

CLI Flow:
- Enter a PDF URL (http/https) when prompted.
- The app downloads the PDF to a temporary file (with SSL, timeout, and header checks), extracts a description, generates an image, and cleans up the temporary file.
- A `generated_image_manifest.txt` is produced with the source URL, temp file path (for traceability), and the description used.

Error handling:
- If the URL is invalid/unsupported scheme, the network times out, or the server returns an error code, the command prints clear messages and aborts.
- If the downloaded file is not a valid PDF (checked via header `%PDF-`), the command removes the temp file and reports the error.
- Permission or I/O errors while writing the temp file or output image are handled with messages.

## PDF extraction robustness

If you encounter errors like "EOF marker not found" with PyPDF2 (even if your PDF opens fine in a viewer), the WatcherAgent now:
1) Tries PyPDF2 (fast).
2) Falls back to pdfplumber.
3) Falls back to PyMuPDF (fitz).
4) If still no text (or the PDF is scanned), it attempts OCR using pytesseract.

To enable OCR, ensure the system Tesseract binary is installed and on your PATH:
- Ubuntu/Debian: `sudo apt-get update && sudo apt-get install -y tesseract-ocr`
- macOS (Homebrew): `brew install tesseract`
- Windows: Install from https://github.com/tesseract-ocr/tesseract and restart the terminal.

The app will print detailed error messages and guidance if extraction fails across all backends.