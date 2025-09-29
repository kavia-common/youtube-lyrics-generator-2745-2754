# YouTube Lyrics Generator (Console)

Run the console app:

1) Install dependencies:
   pip install -r requirements.txt

2) Apply migrations (standard Django step, though not strictly needed here):
   python manage.py migrate

3) Run the console command:
   python manage.py youtube_lyrics

Flow:
- Enter a YouTube URL when prompted.
- Choose a style (pop | hiphop | rock | ballad | country | electronic).
- The tool tries to fetch the official transcript using youtube-transcript-api.
- If no transcript is available, it attempts to download audio (pytube) and will inform you that speech-to-text is not configured.
- On success, lyrics are generated and saved to 'lyrics_output.txt' and previewed in the console.

Notes:
- For real audio transcription when transcripts are unavailable, integrate an STT service (e.g., OpenAI Whisper or Vosk) inside WatcherAgent._try_download_audio path and add necessary environment variables to your deployment. This project intentionally avoids hard-coding secrets or third-party API calls.
