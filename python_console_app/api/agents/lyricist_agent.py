from dataclasses import dataclass
from typing import Optional, Tuple
import textwrap
import os
import base64
import json
import traceback

# Optional external APIs (lazy import in methods)
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

    Behavior:
    1) If configured, attempts to generate a real image using an AI image generation API:
       - Replicate (Stable Diffusion etc.) via REPLICATE_API_TOKEN
       - OpenAI DALL·E via OPENAI_API_KEY
    2) On failure or when no API key is present, falls back to an offline Pillow
       placeholder that renders the description as styled text.

    Configuration (environment variables):
    - REPLICATE_API_TOKEN: Use Replicate image generation (no model hard-coded; uses a default popular sd model).
    - REPLICATE_MODEL: Optional override model slug (e.g., "stability-ai/sdxl").
    - OPENAI_API_KEY: Use OpenAI Images API (DALL·E 3 if available).
    - OPENAI_IMAGE_MODEL: Optional override image model (default "gpt-image-1" or "dall-e-3" depending on library).
    - IMAGE_SIZE: Optional WxH (e.g., "1024x1024") for APIs that accept it.

    Notes:
    - Do not hard-code secrets. All configuration must come from env variables.
    - This class gracefully falls back to local rendering if APIs are unreachable.
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

        description = description.strip()

        # Try Replicate first if available
        replicate_token = os.getenv("REPLICATE_API_TOKEN", "").strip()
        openai_key = os.getenv("OPENAI_API_KEY", "").strip()

        # Attempt external AI generation as requested
        api_errors = []
        # Track which providers were attempted and the prompt used, for clear diagnostics
        attempted = []

        if replicate_token:
            attempted.append("Replicate")
            try:
                self._generate_with_replicate(description, output_path)
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    return ImageResult(success=True, image_path=output_path, details=f"Generated via Replicate | prompt snippet: {description[:80]}")
                else:
                    raise RuntimeError("Replicate returned no image bytes or file is empty.")
            except Exception as e:
                api_errors.append(f"Replicate failed: {e}\n{traceback.format_exc(limit=1)}")

        if openai_key:
            attempted.append("OpenAI")
            try:
                provider_detail = self._generate_with_openai(description, output_path)
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    # provider_detail indicates whether b64 or url was used and which model
                    return ImageResult(success=True, image_path=output_path, details=f"Generated via OpenAI ({provider_detail}) | prompt snippet: {description[:80]}")
                else:
                    raise RuntimeError("OpenAI returned no image bytes or file is empty.")
            except Exception as e:
                api_errors.append(f"OpenAI failed: {e}\n{traceback.format_exc(limit=1)}")

        # Fallback to Pillow rendering if APIs are not configured or failed
        if Image is None or ImageDraw is None or ImageFont is None:
            # Even fallback needs Pillow; if missing, return error with setup instructions
            details = f"Attempted: {', '.join(attempted) or 'none'} | " + (" | ".join(api_errors) if api_errors else "No API keys configured.")
            return ImageResult(
                success=False,
                error="No image generated. Pillow not installed and external APIs unavailable/failed.",
                details=details + " Install Pillow or set REPLICATE_API_TOKEN / OPENAI_API_KEY in environment."
            )

        try:
            self._render_placeholder(description, output_path)
        except Exception as e:
            details = f"Attempted: {', '.join(attempted) or 'none'} | " + (" | ".join(api_errors) if api_errors else "No API keys configured.")
            return ImageResult(success=False, error="Failed to generate image (fallback).", details=f"{details} | {e}")

        if not os.path.exists(output_path):
            details = f"Attempted: {', '.join(attempted) or 'none'} | " + (" | ".join(api_errors) if api_errors else "No API keys configured.")
            return ImageResult(success=False, error="Image file not created.", details=f"{details} Tried: {output_path}")

        suffix = " (fallback placeholder)"
        # Explicitly indicate fallback usage in details so user can distinguish
        return ImageResult(success=True, image_path=output_path, details=f"Rendered locally{suffix} | prompt snippet: {description[:80]}")

    # --- External integrations ---

    def _generate_with_replicate(self, prompt: str, output_path: str) -> None:
        """
        Generate an image using Replicate. Requires REPLICATE_API_TOKEN.
        Optional env: REPLICATE_MODEL (defaults to a common SDXL model).
        """
        import time
        import requests

        token = os.getenv("REPLICATE_API_TOKEN", "").strip()
        if not token:
            raise RuntimeError("REPLICATE_API_TOKEN not set")

        model = os.getenv("REPLICATE_MODEL", "stability-ai/sdxl")
        api_url = "https://api.replicate.com/v1/predictions"
        headers = {
            "Authorization": f"Token {token}",
            "Content-Type": "application/json",
        }

        payload = {
            "version": model,
            "input": {
                "prompt": prompt,
            }
        }

        resp = requests.post(api_url, headers=headers, json=payload, timeout=60)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Replicate API create prediction failed: {resp.status_code} {resp.text}")

        prediction = resp.json()
        get_url = prediction.get("urls", {}).get("get")
        if not get_url:
            raise RuntimeError(f"Unexpected Replicate response (no polling URL): {json.dumps(prediction)}")

        # Poll until completed
        for _ in range(60):
            pr = requests.get(get_url, headers=headers, timeout=30)
            if pr.status_code != 200:
                raise RuntimeError(f"Replicate polling failed: {pr.status_code} {pr.text}")
            pdata = pr.json()
            status = pdata.get("status")
            if status in ("succeeded", "failed", "canceled"):
                if status != "succeeded":
                    raise RuntimeError(f"Replicate prediction status: {status} details={json.dumps(pdata)}")
                output = pdata.get("output")
                if not output:
                    raise RuntimeError(f"Replicate returned no output: {json.dumps(pdata)}")
                first_url = output[0] if isinstance(output, list) else output
                img_resp = requests.get(first_url, timeout=60)
                if img_resp.status_code != 200:
                    raise RuntimeError(f"Failed to download image from Replicate URL: {img_resp.status_code} {img_resp.text[:200]}")
                with open(output_path, "wb") as f:
                    f.write(img_resp.content)
                return
            time.sleep(2)

        raise RuntimeError("Replicate prediction timed out")

    def _generate_with_openai(self, prompt: str, output_path: str) -> str:
        """
        Generate an image using OpenAI Images API. Requires OPENAI_API_KEY.
        Supports new SDK (openai>=1.*) and legacy import fallback.

        Returns:
            A detail string indicating transport (b64/url) and model used on success.
        """
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")

        # Try new SDK first
        try:
            from openai import OpenAI  # type: ignore
            client = OpenAI(api_key=api_key)
            model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
            size = os.getenv("IMAGE_SIZE", "1024x1024")

            # Validate size format for clarity
            if "x" not in size:
                size = "1024x1024"

            result = client.images.generate(
                model=model,
                prompt=prompt,
                size=size,
                n=1,
            )
            data0 = result.data[0]

            if getattr(data0, "b64_json", None):
                img_bytes = base64.b64decode(data0.b64_json)
                with open(output_path, "wb") as f:
                    f.write(img_bytes)
                return f"b64_json; model={model}; size={size}"

            if getattr(data0, "url", None):
                import requests
                img_resp = requests.get(data0.url, timeout=60)
                if img_resp.status_code != 200:
                    raise RuntimeError(f"Failed to download image from OpenAI URL: {img_resp.status_code} {img_resp.text[:200]}")
                with open(output_path, "wb") as f:
                    f.write(img_resp.content)
                return f"url; model={model}; size={size}"

            # If neither field is present, include raw-ish structure for debugging
            try:
                raw_dump = result.model_dump()
            except Exception:
                raw_dump = str(result)
            raise RuntimeError(f"OpenAI Images returned unexpected payload: {raw_dump}")

        except Exception as e_new:
            # Legacy fallback: old import style
            try:
                import openai  # type: ignore
                openai.api_key = api_key
                model = os.getenv("OPENAI_IMAGE_MODEL", "dall-e-3")
                size = os.getenv("IMAGE_SIZE", "1024x1024")
                if "x" not in size:
                    size = "1024x1024"

                # In some older SDKs, the call is openai.Image.create; in newer legacy, it's openai.images.generate
                detail = ""
                try:
                    # Preferred legacy method per >=1.x compatibility layer
                    result = openai.images.generate(
                        model=model,
                        prompt=prompt,
                        size=size,
                        n=1,
                    )
                    data0 = result["data"][0]
                    detail = "images.generate"
                except Exception:
                    # Older fallback method
                    result = openai.Image.create(
                        prompt=prompt,
                        n=1,
                        size=size,
                    )
                    data0 = result["data"][0]
                    detail = "Image.create"

                if "b64_json" in data0 and data0["b64_json"]:
                    img_bytes = base64.b64decode(data0["b64_json"])
                    with open(output_path, "wb") as f:
                        f.write(img_bytes)
                    return f"b64_json; model={model}; size={size}; via={detail}"

                if "url" in data0 and data0["url"]:
                    import requests
                    img_resp = requests.get(data0["url"], timeout=60)
                    if img_resp.status_code != 200:
                        raise RuntimeError(f"Failed to download image from OpenAI URL: {img_resp.status_code} {img_resp.text[:200]}")
                    with open(output_path, "wb") as f:
                        f.write(img_resp.content)
                    return f"url; model={model}; size={size}; via={detail}"

                raise RuntimeError(f"OpenAI Images (legacy) returned unexpected payload: {json.dumps(result)}")

            except Exception as e_legacy:
                raise RuntimeError(f"OpenAI generation failed (new SDK): {e_new} | legacy attempt: {e_legacy}")

    # --- Local placeholder rendering ---

    def _render_placeholder(self, text: str, output_path: str) -> None:
        """
        Create a simple poster-like image with the text centered, wrapped nicely.
        """
        W, H = self.DEFAULT_SIZE
        if Image is None:
            raise RuntimeError("Pillow not installed for fallback rendering.")

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
        title = "Generated Image (Placeholder)"
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
