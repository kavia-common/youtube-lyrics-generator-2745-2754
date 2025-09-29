from dataclasses import dataclass
from typing import Optional, Tuple
import re
import os

# Attempt to import third-party tools used for fetching transcripts/audio.
# We keep imports optional and handle absence gracefully to avoid hard failures.
try:
    from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
except Exception:  # pragma: no cover
    YouTubeTranscriptApi = None  # type: ignore
    TranscriptsDisabled = Exception  # type: ignore
    NoTranscriptFound = Exception  # type: ignore

try:
    from pytube import YouTube  # For audio download if transcript is unavailable
except Exception:  # pragma: no cover
    YouTube = None  # type: ignore


@dataclass
class WatcherResult:
    """Holds the result of watching/transcribing a YouTube video."""
    success: bool
    transcript: Optional[str] = None
    error: Optional[str] = None
    details: Optional[str] = None


class WatcherAgent:
    """
    PUBLIC_INTERFACE
    Orchestrates retrieval of a transcript from a YouTube URL.

    Strategy:
    1) Try to fetch official YouTube transcript via youtube-transcript-api.
    2) If unavailable, optionally download audio via pytube and (placeholder) transcribe.
       - Actual speech-to-text is out of scope unless env/API is provided; we return a helpful error.
    """

    YT_ID_PATTERN = re.compile(
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*"
    )

    # PUBLIC_INTERFACE
    def get_transcript(self, youtube_url: str) -> WatcherResult:
        """
        Attempt to fetch a transcript for the given YouTube URL.

        Parameters:
            youtube_url: Full YouTube video URL.

        Returns:
            WatcherResult with success flag and transcript or error message.
        """
        video_id = self._extract_video_id(youtube_url)
        if not video_id:
            return WatcherResult(
                success=False,
                error="Could not parse a valid YouTube video ID from the provided URL.",
                details="Ensure the URL is a standard watch or share link."
            )

        # First: try official transcripts via YouTubeTranscriptApi
        transcript = self._try_youtube_transcript_api(video_id)
        if transcript:
            return WatcherResult(success=True, transcript=transcript)

        # Fallback: try audio path (download) and inform user transcription requires API
        audio_path, err = self._try_download_audio(youtube_url)
        if err:
            return WatcherResult(
                success=False,
                error="Transcript unavailable and audio download failed.",
                details=err
            )

        # At this point, we would transcribe using an external STT service.
        # As this project aims to be runnable without external secrets, we provide a gentle message.
        # If you want real transcription, set up a speech-to-text API and integrate here.
        self._safe_remove(audio_path)
        return WatcherResult(
            success=False,
            error="Transcript not available.",
            details=(
                "No official transcript found. Audio was downloadable, but speech-to-text is not configured.\n"
                "To enable transcription, integrate an STT provider (e.g., OpenAI Whisper API or Vosk) "
                "and provide necessary API keys via environment variables."
            )
        )

    def _extract_video_id(self, url: str) -> Optional[str]:
        # Handles common YouTube URL formats (watch?v=, youtu.be/, embed/)
        candidates = [
            r"v=([0-9A-Za-z_-]{11})",
            r"youtu\.be\/([0-9A-Za-z_-]{11})",
            r"embed\/([0-9A-Za-z_-]{11})",
            r"shorts\/([0-9A-Za-z_-]{11})",
        ]
        for pattern in candidates:
            m = re.search(pattern, url)
            if m:
                return m.group(1)
        # Fallback broader pattern
        m = self.YT_ID_PATTERN.search(url)
        if m:
            return m.group(1)
        return None

    def _try_youtube_transcript_api(self, video_id: str) -> Optional[str]:
        if YouTubeTranscriptApi is None:
            return None
        try:
            # Attempt English transcripts first, then any available languages
            transcript_list = None
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
            except (NoTranscriptFound, TranscriptsDisabled):  # try any language
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id)

            if not transcript_list:
                return None
            text = " ".join([seg.get("text", "") for seg in transcript_list if seg.get("text")])
            # Basic cleanup for artifacts like [Music]
            cleaned = self._clean_text(text)
            return cleaned or None
        except Exception:
            return None

    def _try_download_audio(self, youtube_url: str) -> Tuple[Optional[str], Optional[str]]:
        if YouTube is None:
            return None, "pytube is not installed; cannot attempt audio download."
        try:
            yt = YouTube(youtube_url)
            stream = yt.streams.filter(only_audio=True).first()
            if not stream:
                return None, "No audio stream found for the provided video."
            output_path = stream.download(filename="temp_youtube_audio")
            return output_path, None
        except Exception as e:
            return None, f"Audio download error: {e}"

    def _safe_remove(self, path: Optional[str]) -> None:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    def _clean_text(self, text: str) -> str:
        # Remove bracketed notes like [Music], [Applause], and extra spaces
        text = re.sub(r"\[.*?\]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()
