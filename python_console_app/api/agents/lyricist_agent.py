from dataclasses import dataclass
from typing import Optional, List


@dataclass
class LyricsResult:
    """Holds the result of generating lyrics from a transcript."""
    success: bool
    lyrics: Optional[str] = None
    error: Optional[str] = None
    details: Optional[str] = None


class LyricistAgent:
    """
    PUBLIC_INTERFACE
    Generates structured song-like lyrics from a given transcript.

    This implementation is self-contained and heuristic-based to avoid external dependencies.
    It splits transcript text into thematic stanzas and formats them as:
      - Intro (optional)
      - Verse 1
      - Chorus
      - Verse 2
      - Bridge (optional)
      - Chorus (repeat)
      - Outro (optional)

    Supports style hints like: "pop", "hiphop", "rock", "ballad", "country", "electronic".
    """

    SUPPORTED_STYLES: List[str] = ["pop", "hiphop", "rock", "ballad", "country", "electronic"]

    # PUBLIC_INTERFACE
    def generate_lyrics(self, transcript: str, style: str = "pop") -> LyricsResult:
        """
        Convert transcript text into stylized, structured lyrics.

        Parameters:
            transcript: The input spoken content.
            style: A style hint influencing word choice and stanza structure.

        Returns:
            LyricsResult containing success and lyrics, or error details.
        """
        if not transcript or not transcript.strip():
            return LyricsResult(success=False, error="Transcript is empty.", details="Provide a non-empty transcript.")

        style = style.lower().strip()
        if style not in self.SUPPORTED_STYLES:
            style = "pop"  # fallback

        # Tokenize into phrases/sentences
        base_lines = self._to_lines(transcript)

        # Derive key motif from transcript
        motif = self._derive_motif(base_lines)

        # Build sections
        verse1 = self._verse_from(base_lines[:8], style, motif, verse_number=1)
        chorus = self._chorus_from(motif, style)
        verse2 = self._verse_from(base_lines[8:16], style, motif, verse_number=2)
        bridge = self._bridge_from(base_lines[16:22], style, motif)

        # Compose full lyrics
        sections = []
        sections.append(self._header("Verse 1"))
        sections.extend(verse1)
        sections.append("")
        sections.append(self._header("Chorus"))
        sections.extend(chorus)
        sections.append("")
        sections.append(self._header("Verse 2"))
        sections.extend(verse2)
        if bridge:
            sections.append("")
            sections.append(self._header("Bridge"))
            sections.extend(bridge)
        sections.append("")
        sections.append(self._header("Chorus"))
        sections.extend(chorus)

        lyrics_text = "\n".join(sections).strip()
        return LyricsResult(success=True, lyrics=lyrics_text)

    def _to_lines(self, transcript: str) -> List[str]:
        # Gentle sentence splitting
        raw = transcript.replace("\n", " ")
        chunks = [c.strip() for c in self._split_sentences(raw) if c.strip()]
        # Normalize line length
        lines = []
        for c in chunks:
            if len(c) <= 70:
                lines.append(c)
            else:
                # Break long sentences into ~70 char segments
                words = c.split()
                buf = []
                cur = 0
                for w in words:
                    if cur + len(w) + 1 > 70 and buf:
                        lines.append(" ".join(buf))
                        buf = [w]
                        cur = len(w)
                    else:
                        buf.append(w)
                        cur += len(w) + 1
                if buf:
                    lines.append(" ".join(buf))
        return lines or ["We wander through the echoes, searching for a sign."]

    def _split_sentences(self, text: str) -> List[str]:
        # Very simple sentence split
        import re
        parts = re.split(r"(?<=[\.\!\?])\s+", text)
        return parts

    def _derive_motif(self, lines: List[str]) -> str:
        # Take a few meaningful words from the earliest lines to become the chorus hook
        import re
        words = []
        for line in lines[:6]:
            for token in re.findall(r"[A-Za-z']+", line):
                t = token.lower()
                if len(t) > 3 and t not in ("this", "that", "with", "have", "from", "your", "their", "about"):
                    words.append(t)
        if not words:
            return "Hold on, let the daylight find our way"
        # Build a short motif phrase
        chosen = words[:5]
        phrase = " ".join(chosen).strip().title()
        return phrase if phrase else "Hold on, let the daylight find our way"

    def _verse_from(self, lines: List[str], style: str, motif: str, verse_number: int) -> List[str]:
        flavor_prefix = self._style_prefix(style)
        return [
            f"{flavor_prefix}{line}" for line in (lines or [f"In the {style} rhythm, we tell the tale {verse_number}."])
        ][:8]

    def _chorus_from(self, motif: str, style: str) -> List[str]:
        hook = self._style_hook(style)
        return [
            f"{hook} {motif}",
            f"{hook} We sing it loud, we sing it true",
            f"{hook} {motif}",
            f"{hook} Let the night turn into blue",
        ]

    def _bridge_from(self, lines: List[str], style: str, motif: str) -> List[str]:
        if not lines:
            return []
        mood = self._style_bridge_mood(style)
        bridge_lines = [f"{mood}{l}" for l in lines[:4]]
        bridge_lines.append(f"{mood}{motif.lower()} fades then rises new")
        return bridge_lines

    def _header(self, title: str) -> str:
        return f"[{title}]"

    def _style_prefix(self, style: str) -> str:
        mapping = {
            "pop": "",
            "hiphop": "",
            "rock": "",
            "ballad": "",
            "country": "",
            "electronic": "",
        }
        return mapping.get(style, "")

    def _style_hook(self, style: str) -> str:
        hooks = {
            "pop": "Oh",
            "hiphop": "Yeah",
            "rock": "Hey",
            "ballad": "Ooh",
            "country": "Whoa",
            "electronic": "Ah",
        }
        return hooks.get(style, "Oh")

    def _style_bridge_mood(self, style: str) -> str:
        moods = {
            "pop": "",
            "hiphop": "",
            "rock": "",
            "ballad": "",
            "country": "",
            "electronic": "",
        }
        return moods.get(style, "")
