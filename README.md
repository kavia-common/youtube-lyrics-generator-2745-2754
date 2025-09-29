# youtube-lyrics-generator-2745-2754

This console app has been repurposed to:
- Download a PDF from a user-provided URL.
- Extract a description from the PDF (WatcherAgent).
- Generate a real image using that description (LyricistAgent) and save it to `generated_image.png`.
  • Uses Replicate (Stable Diffusion/SDXL) if REPLICATE_API_TOKEN is set, or OpenAI Images if OPENAI_API_KEY is set.
  • Gracefully falls back to a local Pillow-based text rendering if no API is configured or reachable.

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

## Real image generation configuration

You can enable AI image generation by setting environment variables before running the command:

- Replicate (Stable Diffusion/SDXL):
  export REPLICATE_API_TOKEN="your_token_here"
  # Optional overrides:
  export REPLICATE_MODEL="stability-ai/sdxl"
  export IMAGE_SIZE="1024x1024"

- OpenAI (DALL·E / Images API):
  export OPENAI_API_KEY="your_key_here"
  # Optional overrides:
  export OPENAI_IMAGE_MODEL="gpt-image-1"   # or "dall-e-3"
  export IMAGE_SIZE="1024x1024"

If neither is set, the app will fall back to an offline placeholder image using Pillow. This ensures the workflow remains functional without external services.

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