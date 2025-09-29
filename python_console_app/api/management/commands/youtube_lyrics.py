from datetime import datetime
from django.core.management.base import BaseCommand

from api.agents.watcher_agent import WatcherAgent
from api.agents.lyricist_agent import LyricistAgent
from api.utils.console import info, success, error, headline, prompt


IMAGE_OUTPUT_FILE = "generated_image.png"


class Command(BaseCommand):
    """
    PUBLIC_INTERFACE
    Django management command: youtube_lyrics (repurposed for PDF → image)

    Purpose:
        Provides a console (stdin/stdout) interface to:
          - Prompt for a local PDF file path.
          - Read the PDF and extract a description text (WatcherAgent).
          - Generate an image visualizing that description (LyricistAgent).
          - Save image to 'generated_image.png' and confirm in console.

    Usage:
        python manage.py youtube_lyrics

    Return:
        Exits with status code 0 on success; 1 on failure.
    """

    help = "Generate an image from a description extracted from a local PDF."

    def handle(self, *args, **options):
        headline("PDF Description → Image · Ocean Professional")
        info("This tool reads a local PDF, extracts a description, and renders an image based on it.")

        pdf_path = prompt("Enter a local PDF file path:")
        if not pdf_path or not pdf_path.strip():
            error("No PDF path provided. Aborting.")
            self._set_return_code(1)
            return

        info("Reading PDF and extracting description...")
        watcher = WatcherAgent()
        wres = watcher.get_description_from_pdf(pdf_path)
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
            self._set_return_code(1)
            return

        # Save confirmation
        try:
            self._write_manifest(wres.description, ires.image_path)
        except Exception as e:
            error(f"Unable to write manifest: {e}")
            self._set_return_code(1)
            return

        success(f"Image generated successfully and saved to '{ires.image_path}'.")
        info("Done.")
        self._set_return_code(0)

    def _write_manifest(self, description: str, image_path: str) -> None:
        """
        Write a small manifest file capturing when and from what description the image was produced.
        """
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")
        content = (
            "# PDF → Image Manifest\n"
            f"# Generated: {timestamp}\n"
            f"# Image: {image_path}\n\n"
            "## Description Used\n\n"
            f"{description}\n"
        )
        with open("generated_image_manifest.txt", "w", encoding="utf-8") as f:
            f.write(content)

    def _set_return_code(self, code: int):
        # Django's BaseCommand does not provide direct exit; raising SystemExit ensures CI recognizes success/failure.
        if code != 0:
            raise SystemExit(code)
