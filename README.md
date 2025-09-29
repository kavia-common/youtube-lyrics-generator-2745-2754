# youtube-lyrics-generator-2745-2754

This console app has been repurposed to:
- Read a local PDF, extract a description (WatcherAgent).
- Generate an image using that description (LyricistAgent) and save it to `generated_image.png`.

Run:
- pip install -r python_console_app/requirements.txt
- cd python_console_app
- python manage.py migrate
- python manage.py youtube_lyrics