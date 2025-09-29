from datetime import datetime
from django.core.management.base import BaseCommand

from api.agents.watcher_agent import WatcherAgent
from api.agents.lyricist_agent import LyricistAgent
from api.utils.console import info, success, error, headline, prompt


OUTPUT_FILE = "lyrics_output.txt"


class Command(BaseCommand):
    """
    PUBLIC_INTERFACE
    Django management command: youtube_lyrics

    Purpose:
        Provides a console (stdin/stdout) interface to:
          - Prompt for a YouTube URL.
          - Attempt to retrieve/transcribe the video into a transcript (WatcherAgent).
          - Generate structured song-like lyrics from the transcript (LyricistAgent).
          - Save lyrics to 'lyrics_output.txt' and preview in console.

    Usage:
        python manage.py youtube_lyrics

    Return:
        Exits with status code 0 on success; 1 on failure.
    """

    help = "Generate song-like lyrics from a YouTube video's spoken content."

    def handle(self, *args, **options):
        headline("YouTube Lyrics Generator · Ocean Professional")
        info("This tool will convert spoken content from a YouTube video into stylized lyrics.")

        url = prompt("Enter a YouTube video URL:")
        if not url or not url.strip():
            error("No URL provided. Aborting.")
            self._set_return_code(1)
            return

        style = prompt("Select a lyrics style [pop | hiphop | rock | ballad | country | electronic] (default: pop):")
        style = style.strip().lower() or "pop"

        info("Processing video, attempting to retrieve transcript...")
        watcher = WatcherAgent()
        wres = watcher.get_transcript(url)
        if not wres.success or not wres.transcript:
            error("Failed to retrieve transcript.")
            if wres.error:
                error(f"Reason: {wres.error}")
            if wres.details:
                info(f"Details: {wres.details}")
            info("Hint: If your URL includes playlist params like 'list=' or '&start_radio=1', the tool now normalizes it automatically, but cookies may still be required for restricted videos.")
            self._set_return_code(1)
            return

        info("Generating lyrics...")
        lyricist = LyricistAgent()
        lres = lyricist.generate_lyrics(transcript=wres.transcript, style=style)
        if not lres.success or not lres.lyrics:
            error("Failed to generate lyrics.")
            if lres.error:
                error(f"Reason: {lres.error}")
            if lres.details:
                info(f"Details: {lres.details}")
            self._set_return_code(1)
            return

        # Save to file
        try:
            self._write_output(lres.lyrics)
        except Exception as e:
            error(f"Unable to write output file: {e}")
            self._set_return_code(1)
            return

        success(f"Lyrics generated successfully and saved to '{OUTPUT_FILE}'.")
        headline("Preview")
        print()
        print(lres.lyrics[:2000])  # Preview first 2000 chars
        print()
        info("Done.")
        self._set_return_code(0)

    def _write_output(self, lyrics: str) -> None:
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")
        content = f"# YouTube Lyrics\n# Generated: {timestamp}\n\n{lyrics}\n"
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(content)

    def _set_return_code(self, code: int):
        # Django's BaseCommand does not provide direct exit; raising SystemExit ensures CI recognizes success/failure.
        if code != 0:
            raise SystemExit(code)
