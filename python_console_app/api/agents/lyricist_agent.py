from dataclasses import dataclass
from typing import Optional, Tuple
import textwrap
import os

try:
    from PIL import Image, ImageDraw, ImageFont  # type: ignore
except Exception:  # pragma: no cover
    Image = None  # type: ignore
    ImageDraw = None  # type: ignore
    ImageFont = None  # type: ignore


@dataclass
class ImageResult:
    """Holds the result of generating an image from a description."""
    success: bool
    image_path: Optional[str] = None
    error: Optional[str] = None
    details: Optional[str] = None


class LyricistAgent:
    """
    PUBLIC_INTERFACE
    Generates an image from a given description.

    Default implementation uses Pillow to render a placeholder image with the
    description text. This avoids external API calls and works offline.

    To integrate with an image generation API (e.g., Stable Diffusion, OpenAI, etc.),
    replace _render_placeholder with an API call and file saving logic.
    """

    DEFAULT_SIZE: Tuple[int, int] = (1024, 1024)
    DEFAULT_BG = (249, 250, 251)     # #f9fafb
    DEFAULT_FG = (17, 24, 39)        # #111827 (text)
    ACCENT = (37, 99, 235)           # #2563EB

    # PUBLIC_INTERFACE
    def generate_image_from_description(self, description: str, output_path: str = "generated_image.png") -> ImageResult:
        """
        Generate an image visualizing the provided description.

        Parameters:
            description: The textual description to visualize.
            output_path: Where to save the resulting image (PNG).

        Returns:
            ImageResult containing success flag and image path (or error details).
        """
        if not description or not description.strip():
            return ImageResult(success=False, error="Description is empty.", details="Provide a non-empty description.")

        # Ensure PIL (Pillow) is available
        if Image is None or ImageDraw is None or ImageFont is None:
            return ImageResult(
                success=False,
                error="Pillow is not installed.",
                details="Install pillow in your environment to enable image rendering."
            )

        try:
            self._render_placeholder(description.strip(), output_path)
        except Exception as e:
            return ImageResult(success=False, error="Failed to generate image.", details=str(e))

        if not os.path.exists(output_path):
            return ImageResult(success=False, error="Image file not created.", details=f"Tried: {output_path}")

        return ImageResult(success=True, image_path=output_path)

    def _render_placeholder(self, text: str, output_path: str) -> None:
        """
        Create a simple poster-like image with the text centered, wrapped nicely.
        """
        W, H = self.DEFAULT_SIZE
        img = Image.new("RGB", (W, H), self.DEFAULT_BG)
        draw = ImageDraw.Draw(img)

        # Accent border
        border = 20
        for i in range(0, 6):
            draw.rectangle([border - i, border - i, W - border + i, H - border + i], outline=self.ACCENT, width=1)

        # Try to load a decent font; fallback to default
        font = None
        for candidate in ["DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
            try:
                font = ImageFont.truetype(candidate, 36)
                break
            except Exception:
                continue
        if font is None:
            font = ImageFont.load_default()

        # Title
        title = "Generated Image"
        title_font = None
        try:
            title_font = ImageFont.truetype("DejaVuSans.ttf", 48)
        except Exception:
            title_font = font

        title_w, title_h = draw.textbbox((0, 0), title, font=title_font)[2:]
        draw.text(((W - title_w) / 2, 60), title, font=title_font, fill=self.ACCENT)

        # Wrap description
        max_width_chars = 40
        wrapped = textwrap.fill(text, width=max_width_chars)
        # Measure and draw paragraph centered horizontally
        y = 130
        line_spacing = 8
        for para in wrapped.split("\n"):
            bbox = draw.textbbox((0, 0), para, font=font)
            line_w, line_h = bbox[2], bbox[3]
            x = (W - line_w) / 2
            draw.text((x, y), para, font=font, fill=self.DEFAULT_FG)
            y += line_h + line_spacing

        # Signature/footer
        footer = "Ocean Professional"
        fw, fh = draw.textbbox((0, 0), footer, font=font)[2:]
        draw.text((W - fw - 20, H - fh - 20), footer, font=font, fill=self.ACCENT)

        img.save(output_path, format="PNG")
