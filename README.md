# youtube-lyrics-generator-2745-2754

This console app has been repurposed to:
- Read a local PDF, extract a description (WatcherAgent).
- Generate an image using that description (LyricistAgent) and save it to `generated_image.png`.

Run:
- pip install -r python_console_app/requirements.txt
- cd python_console_app
- python manage.py migrate
- python manage.py youtube_lyrics

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