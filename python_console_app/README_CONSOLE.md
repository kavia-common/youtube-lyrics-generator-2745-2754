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
- The LyricistAgent attempts to generate a real image using AI image generation:
  • Replicate (Stable Diffusion, SDXL, etc.) if REPLICATE_API_TOKEN is set.
  • OpenAI DALL·E / Images API if OPENAI_API_KEY is set.
  • If neither is configured (or external calls fail), it falls back to a local Pillow placeholder that renders the text.
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

Real image generation setup (optional):
- Replicate (recommended for Stable Diffusion-like models):
  1) Create an account and obtain an API token from https://replicate.com/account/api-tokens
  2) Set environment variable:
     export REPLICATE_API_TOKEN="your_token_here"
  3) Optional: choose a model slug via:
     export REPLICATE_MODEL="stability-ai/sdxl"
     (defaults to a popular SDXL model)
  4) Optional image size (some models support or ignore this):
     export IMAGE_SIZE="1024x1024"
- OpenAI (DALL·E / Images API):
  1) Obtain an API key from https://platform.openai.com/api-keys
  2) Set:
     export OPENAI_API_KEY="your_key_here"
  3) Optional model override:
     export OPENAI_IMAGE_MODEL="gpt-image-1"   # or "dall-e-3" depending on availability
  4) Optional:
     export IMAGE_SIZE="1024x1024"

Behavior and fallback:
- If at least one of REPLICATE_API_TOKEN or OPENAI_API_KEY is set, LyricistAgent tries those providers in order.
- If all external calls fail (network issues, quota, invalid model, etc.), it gracefully falls back to a local placeholder using Pillow.
- If Pillow is not installed and no external API succeeds, the command reports an error with setup guidance.

Troubleshooting:
- Replicate:
  • Ensure REPLICATE_API_TOKEN is valid and you have access to the selected model.
  • Some models require specific input keys; the default config uses "prompt".
- OpenAI:
  • Ensure OPENAI_API_KEY is valid and the model is available in your account/region.
  • The SDK version can differ; this project supports both new and legacy clients.
- Pillow placeholder:
  • If you see text-only images, it means external APIs were not configured or failed; check the console details.
