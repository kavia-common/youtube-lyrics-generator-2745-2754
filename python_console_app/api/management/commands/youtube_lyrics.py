from datetime import datetime
import os

from django.core.management.base import BaseCommand

from api.agents.watcher_agent import WatcherAgent
from api.agents.lyricist_agent import LyricistAgent
from api.utils.console import info, success, error, headline, prompt
from api.utils.downloader import download_pdf_to_temp


IMAGE_OUTPUT_FILE = "generated_image.png"


class Command(BaseCommand):
    """
    PUBLIC_INTERFACE
    Django management command: youtube_lyrics (repurposed for PDF → image)

    Purpose:
        Provides a console (stdin/stdout) interface to:
          - Prompt for a PDF URL.
          - Download the PDF to a temporary file with robust error handling.
          - Read the PDF and extract a description text (WatcherAgent).
          - Generate an image visualizing that description (LyricistAgent).
          - Save image to 'generated_image.png' and confirm in console.

    Usage:
        python manage.py youtube_lyrics

    Return:
        Exits with status code 0 on success; 1 on failure.
    """

    help = "Generate an image from a description extracted from a PDF URL."

    def handle(self, *args, **options):
        headline("PDF Description → Image · Ocean Professional")
        info("This tool downloads a PDF from a URL, extracts a description, and renders an image based on it.")

        pdf_url = prompt("Enter a PDF URL (http/https):")
        if not pdf_url or not pdf_url.strip():
            error("No URL provided. Aborting.")
            self._set_return_code(1)
            return

        info("Downloading PDF...")
        dres = download_pdf_to_temp(pdf_url)
        if not dres.success or not dres.file_path:
            error("Failed to download PDF.")
            if dres.error:
                error(f"Reason: {dres.error}")
            if dres.details:
                info(f"Details: {dres.details}")
            self._set_return_code(1)
            return

        temp_path = dres.file_path
        try:
            info("Reading PDF and extracting description...")
            watcher = WatcherAgent()
            wres = watcher.get_description_from_pdf(temp_path)
            if not wres.success or not wres.description:
                error("Failed to extract description from PDF.")
                if wres.error:
                    error(f"Reason: {wres.error}")
                if wres.details:
                    info(f"Details: {wres.details}")
                self._set_return_code(1)
                return

            info("Generating image from description...")
            lyricist = LyricistAgent()
            ires = lyricist.generate_image_from_description(description=wres.description, output_path=IMAGE_OUTPUT_FILE)
            if not ires.success or not ires.image_path:
                error("Failed to generate image.")
                if ires.error:
                    error(f"Reason: {ires.error}")
                if ires.details:
                    info(f"Details: {ires.details}")
                # Explicit environment echo to aid diagnostics
                info(f"Env OPENAI_API_KEY detected: {'yes' if (os.getenv('OPENAI_API_KEY') or '').strip() else 'no'}")
                info(f"Env REPLICATE_API_TOKEN detected: {'yes' if (os.getenv('REPLICATE_API_TOKEN') or '').strip() else 'no'}")
                self._set_return_code(1)
                return

            # Save confirmation
            try:
                self._write_manifest(
                    description=wres.description,
                    image_path=ires.image_path,
                    source_url=pdf_url,
                    temp_file=temp_path,
                )
            except Exception as e:
                error(f"Unable to write manifest: {e}")
                self._set_return_code(1)
                return

            # Explicitly inform whether this was an AI-generated image or local fallback
            if ires.details and "Rendered locally" in ires.details:
                success(f"Image saved to '{ires.image_path}' (LOCAL PLACEHOLDER).")
                info(f"Generator details: {ires.details}")
            else:
                success(f"Image saved to '{ires.image_path}' (AI GENERATED).")
                info(f"Generator details: {ires.details or 'No extra details'}")
            # Also show the first part of the prompt used
            info(f"Prompt used (snippet): {(wres.description or '')[:120]}...")
            info("Done.")
            self._set_return_code(0)
        finally:
            # Ensure temp file is removed
            try:
                if temp_path and os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                # Non-fatal cleanup failure
                pass

    def _write_manifest(self, description: str, image_path: str, *, source_url: str, temp_file: str) -> None:
        """
        Write a small manifest file capturing when and from what description the image was produced.
        """
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        content = (
            "# PDF → Image Manifest\n"
            f"# Generated: {timestamp}\n"
            f"# Image: {image_path}\n"
            f"# Source URL: {source_url}\n"
            f"# Temp File: {temp_file}\n\n"
            "## Description Used\n\n"
            f"{description}\n"
        )
        with open("generated_image_manifest.txt", "w", encoding="utf-8") as f:
            f.write(content)

    def _set_return_code(self, code: int):
        # Django's BaseCommand does not provide direct exit; raising SystemExit ensures CI recognizes success/failure.
        if code != 0:
            raise SystemExit(code)
