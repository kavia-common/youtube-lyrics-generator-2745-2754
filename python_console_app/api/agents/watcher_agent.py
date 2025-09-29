from dataclasses import dataclass
from typing import Optional, Tuple
import re
import os
from urllib.parse import urlparse, parse_qs, urlunparse

# Attempt to import third-party tools used for fetching transcripts/audio.
# We keep imports optional and handle absence gracefully to avoid hard failures.
try:
    from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
except Exception:  # pragma: no cover
    YouTubeTranscriptApi = None  # type: ignore
    TranscriptsDisabled = Exception  # type: ignore
    NoTranscriptFound = Exception  # type: ignore

# Prefer yt_dlp for robust downloads; fall back to pytube if unavailable
try:
    import yt_dlp  # type: ignore
except Exception:  # pragma: no cover
    yt_dlp = None  # type: ignore

try:
    from pytube import YouTube as PyTubeYouTube  # For fallback audio download
except Exception:  # pragma: no cover
    PyTubeYouTube = None  # type: ignore


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
    2) If unavailable, optionally download audio via yt_dlp (fallback to pytube) and (placeholder) transcribe.
       - Actual speech-to-text is out of scope unless env/API is provided; we return a helpful error.
    """

    YT_ID_PATTERN = re.compile(r"(?:v=|/)([0-9A-Za-z_-]{11}).*")

    # PUBLIC_INTERFACE
    def get_transcript(self, youtube_url: str) -> WatcherResult:
        """
        Attempt to fetch a transcript for the given YouTube URL.

        Parameters:
            youtube_url: Full YouTube video URL, possibly with playlist/radio parameters.

        Returns:
            WatcherResult with success flag and transcript or error message.
        """
        normalized_url = self._normalize_url(youtube_url)
        video_id = self._extract_video_id(normalized_url)
        if not video_id:
            return WatcherResult(
                success=False,
                error="Could not parse a valid YouTube video ID from the provided URL.",
                details=f"Provided URL: {youtube_url}"
            )

        # First: try official transcripts via YouTubeTranscriptApi
        transcript = self._try_youtube_transcript_api(video_id)
        if transcript:
            return WatcherResult(success=True, transcript=transcript)

        # Fallback: try audio path (download) and inform user transcription requires API
        audio_path, err = self._try_download_audio(normalized_url, video_id)
        if err:
            return WatcherResult(
                success=False,
                error="Transcript unavailable and audio download failed.",
                details=(
                    f"{err}\n"
                    f"Tips: If this is age/gated or region-limited content, you may need to provide cookies to yt_dlp.\n"
                    f"URL used: {normalized_url}\nVideo ID: {video_id}"
                )
            )

        # At this point, we would transcribe using an external STT service.
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

    def _normalize_url(self, url: str) -> str:
        """
        Normalize YouTube URL to a single video URL by removing playlist/radio parameters.
        Keeps only the 'v' parameter for watch URLs or path id for youtu.be.
        """
        try:
            parsed = urlparse(url)
            qs = parse_qs(parsed.query, keep_blank_values=True)
            # If we have a video id 'v', strip unrelated params like list, start_radio, index, pp, etc.
            if "v" in qs and qs["v"]:
                clean_qs_items = [("v", qs["v"][0])]
                new_query = "&".join([f"{k}={v}" for k, v in clean_qs_items])
                cleaned = parsed._replace(query=new_query)
                return urlunparse(cleaned)
            # For youtu.be links, they are fine as-is; ensure we strip query entirely if it contains playlist bits
            if parsed.netloc.endswith("youtu.be"):
                # retain path only, drop query to avoid playlist confusion
                cleaned = parsed._replace(query="")
                return urlunparse(cleaned)
            # Default: return original if nothing to clean
            return url
        except Exception:
            # In case parsing fails for some reason, return original to avoid blocking
            return url

    def _extract_video_id(self, url: str) -> Optional[str]:
        # Handles common YouTube URL formats (watch?v=, youtu.be/, embed/, shorts/)
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
            except (NoTranscriptFound, TranscriptsDisabled):
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id)

            if not transcript_list:
                return None
            text = " ".join([seg.get("text", "") for seg in transcript_list if seg.get("text")])
            cleaned = self._clean_text(text)
            return cleaned or None
        except Exception:
            # We hide internal API errors for simplicity; call-site will use fallback
            return None

    def _try_download_audio(self, youtube_url: str, video_id: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        """
        Try to download audio using yt_dlp into a temp file; if unavailable, fall back to pytube.
        Returns (path, error). On success, error is None.
        """
        # Try yt_dlp first
        if yt_dlp is not None:
            try:
                # Output file name ensuring unique by video id
                base_out = f"temp_youtube_audio_{video_id or 'unknown'}.m4a"
                ydl_opts = {
                    "format": "bestaudio/best",
                    "outtmpl": base_out,
                    "quiet": True,
                    "no_warnings": True,
                    "ignoreerrors": True,
                    # Postprocessor to extract audio if container differs
                    "postprocessors": [
                        {"key": "FFmpegExtractAudio", "preferredcodec": "m4a", "preferredquality": "192"}
                    ],
                    # Set a common user agent to avoid 403 in some regions
                    "http_headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([youtube_url])
                if os.path.exists(base_out):
                    return base_out, None
                # Sometimes yt_dlp names files slightly differently; try to find by prefix
                for fname in os.listdir("."):
                    if fname.startswith(f"temp_youtube_audio_{video_id or 'unknown'}"):
                        return fname, None
                return None, "yt_dlp did not produce an audio file."
            except Exception as e:
                # Continue to fallback if possible
                yt_dlp_err = f"yt_dlp error: {e}"
            else:
                yt_dlp_err = None
        else:
            yt_dlp_err = "yt_dlp not installed."

        # Fallback: pytube
        if PyTubeYouTube is None:
            return None, f"{yt_dlp_err} | pytube is not installed; cannot attempt fallback audio download."
        try:
            # Use normalized URL and prefer progressive=False audio streams
            yt = PyTubeYouTube(youtube_url)
            stream = yt.streams.filter(only_audio=True).first()
            if not stream:
                return None, f"{yt_dlp_err} | No audio stream found via pytube."
            output_path = stream.download(filename=f"temp_youtube_audio_{video_id or 'unknown'}")
            return output_path, None
        except Exception as e:
            return None, f"{yt_dlp_err} | pytube error: {e}"

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
