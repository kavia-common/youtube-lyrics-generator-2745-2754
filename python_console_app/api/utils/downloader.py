from dataclasses import dataclass
from typing import Optional
import os
import tempfile
import urllib.parse

import requests


@dataclass
class DownloadResult:
    """Represents the outcome of downloading a file from a URL."""
    success: bool
    file_path: Optional[str] = None
    error: Optional[str] = None
    details: Optional[str] = None


# PUBLIC_INTERFACE
def download_pdf_to_temp(url: str, *, timeout: int = 30, verify_pdf: bool = True) -> DownloadResult:
    """
    Download a PDF from the provided URL to a temporary file.

    Parameters:
        url: The URL pointing to a PDF file.
        timeout: Request timeout in seconds for connection and read.
        verify_pdf: If True, validates the content-type and basic PDF header.

    Returns:
        DownloadResult with success flag and path to the downloaded temporary file.
        Caller is responsible for deleting the temp file when done.

    Error handling:
        - Validates URL scheme (http/https).
        - Handles network errors, timeouts, non-200 responses.
        - Checks content-type and initial PDF header bytes if verify_pdf is True.
    """
    url = (url or "").strip()
    if not url:
        return DownloadResult(success=False, error="No URL provided.", details="Please provide a valid HTTPS/HTTP URL to a PDF.")

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return DownloadResult(success=False, error="Unsupported URL scheme.", details=f"URL must start with http or https. Got: {parsed.scheme or 'none'}")

    try:
        with requests.get(url, stream=True, timeout=(timeout, timeout)) as resp:
            if resp.status_code != 200:
                return DownloadResult(
                    success=False,
                    error=f"HTTP {resp.status_code} while downloading.",
                    details=f"URL: {url}"
                )

            content_type = resp.headers.get("Content-Type", "")
            if verify_pdf and "pdf" not in content_type.lower():
                # Some servers misreport Content-Type; we will still validate header after first chunk.
                pass

            # Create temp file
            fd, temp_path = tempfile.mkstemp(prefix="download_", suffix=".pdf")
            os.close(fd)  # We'll reopen for writing as a normal file handle

            wrote_first_chunk = False
            first_bytes: bytes = b""
            try:
                with open(temp_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:  # filter out keep-alive chunks
                            if not wrote_first_chunk:
                                first_bytes = chunk[:5]
                                wrote_first_chunk = True
                            f.write(chunk)

                # Verify PDF signature if requested
                if verify_pdf:
                    if first_bytes[:5] != b"%PDF-":
                        # Double-check by opening file head
                        try:
                            with open(temp_path, "rb") as rf:
                                head = rf.read(5)
                                if head != b"%PDF-":
                                    os.remove(temp_path)
                                    return DownloadResult(
                                        success=False,
                                        error="Downloaded file is not a valid PDF.",
                                        details="Header signature %PDF- not found."
                                    )
                        except Exception as e:
                            # If we cannot re-open, remove and report
                            try:
                                os.remove(temp_path)
                            except Exception:
                                pass
                            return DownloadResult(
                                success=False,
                                error="Failed to verify downloaded file.",
                                details=str(e)
                            )

                return DownloadResult(success=True, file_path=temp_path)
            except Exception as e:
                # Cleanup on any file I/O error
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except Exception:
                    pass
                return DownloadResult(success=False, error="Failed to write downloaded file.", details=str(e))
    except requests.exceptions.SSLError as e:
        return DownloadResult(success=False, error="SSL error during download.", details=str(e))
    except requests.exceptions.Timeout as e:
        return DownloadResult(success=False, error="Network timeout during download.", details=str(e))
    except requests.exceptions.RequestException as e:
        return DownloadResult(success=False, error="Network error during download.", details=str(e))
