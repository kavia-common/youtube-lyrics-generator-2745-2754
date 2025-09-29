# PDF Description → Image Generator (Console)

Run the console app:

1) Install dependencies:
   pip install -r requirements.txt

2) Apply migrations (standard Django step, though not strictly needed here):
   python manage.py migrate

3) Run the console command:
   python manage.py youtube_lyrics

Flow:
- Enter a local PDF file path when prompted.
- The tool reads the PDF and extracts a description (first 'Description' section or the first substantial paragraph).
- An image is generated using a placeholder renderer (Pillow) with the description text.
- The image is saved to 'generated_image.png'. A 'generated_image_manifest.txt' summarizing the inputs is also written.

Notes:
- This implementation avoids any external API calls and works fully offline.
- To integrate a real image generation model, replace LyricistAgent._render_placeholder with an API call and ensure proper environment variables are provided. Do not hard-code secrets.
