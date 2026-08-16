"""
Local copy of the rare pepe collection.

The collection lives in a 183 MB zip on archive.org, and every image was served
by asking archive.org to extract one file from it on demand. That is slow when
it works, throttled under load, and unavailable when archive.org is — which is
how the command came to show nothing at all.

The zip is fetched once instead, unpacked onto the persistent volume, and the
images are served from there. One large sequential download is the access
pattern archive.org is built for; 1252 on-demand extractions is not.
"""

import logging
import os
import shutil
import tempfile
import threading
import zipfile
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

import httpx

from core.config import DATA_DIR

logger = logging.getLogger(__name__)

RARE_PEPE_DIR = DATA_DIR / "rare_pepes"

# The archive item holding the collection. Configurable so a future re-upload
# does not need a code change.
ARCHIVE_ZIP_URL = os.getenv(
    "RARE_PEPE_ZIP_URL",
    "https://archive.org/download/PepeImgurAlbum/Pepe%20-%20Imgur.zip",
)

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

# The download is one large file over a link that has been unreliable, so it
# gets a generous budget — unlike a viewer-facing fetch, nobody is waiting.
DOWNLOAD_TIMEOUT = float(os.getenv("RARE_PEPE_DOWNLOAD_TIMEOUT", "900"))

# Guards against a zip that expands far beyond what the volume can hold.
MAX_EXTRACTED_BYTES = int(os.getenv("RARE_PEPE_MAX_MB", "400")) * 1024 * 1024

_seeding = threading.Lock()
_last_error: Optional[str] = None


def local_name_for(url: str) -> Optional[str]:
    """
    The file name inside the zip that an archive.org download URL points at.

    Such a URL is /download/<item>/<archive>.zip/<path inside the zip>, so the
    part after the archive name identifies the picture. Anything else is not
    ours to serve locally.
    """
    if not url:
        return None
    path = urlparse(url).path
    marker = ".zip/"
    index = path.lower().rfind(marker)
    if index == -1:
        return None
    inner = unquote(path[index + len(marker):])
    # Only the base name is kept: a nested path would otherwise be able to
    # point outside the directory.
    name = Path(inner).name
    return name or None


def local_path_for(url: str) -> Optional[Path]:
    """Path to the locally stored copy of an image, if there is one."""
    name = local_name_for(url)
    if not name:
        return None
    candidate = RARE_PEPE_DIR / name
    try:
        # Resolved and checked, so a crafted name cannot escape the directory.
        if candidate.resolve().parent != RARE_PEPE_DIR.resolve():
            return None
    except OSError:
        return None
    return candidate if candidate.is_file() else None


def state() -> dict:
    """How much of the collection is stored locally."""
    files = 0
    total = 0
    if RARE_PEPE_DIR.is_dir():
        for entry in RARE_PEPE_DIR.iterdir():
            if entry.is_file():
                files += 1
                try:
                    total += entry.stat().st_size
                except OSError:
                    pass
    return {
        "files": files,
        "megabytes": round(total / (1024 * 1024), 1),
        "seeding": _seeding.locked(),
        "last_error": _last_error,
        "source": ARCHIVE_ZIP_URL,
    }


def _extract(zip_path: Path, target: Path) -> int:
    """Unpack the images from the zip into an empty directory."""
    written = 0
    extracted = 0
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            if member.is_dir():
                continue
            name = Path(member.filename).name
            if not name or Path(name).suffix.lower() not in IMAGE_SUFFIXES:
                continue

            written += member.file_size
            if written > MAX_EXTRACTED_BYTES:
                raise RuntimeError(
                    f"Archive expands past {MAX_EXTRACTED_BYTES // (1024 * 1024)} MB"
                )

            # Written by name rather than with extractall, which would honour
            # paths inside the zip and could write outside the target.
            with archive.open(member) as src, open(target / name, "wb") as dst:
                shutil.copyfileobj(src, dst)
            extracted += 1
    return extracted


def seed(force: bool = False) -> dict:
    """
    Download and unpack the collection. Safe to call repeatedly.

    Blocking and slow; callers run it off the event loop. The unpacked images
    are swapped in only once complete, so an interrupted run leaves the
    previous copy — or no copy — rather than half a collection.
    """
    global _last_error

    if not _seeding.acquire(blocking=False):
        return {"status": "already running", **state()}

    try:
        current = state()
        if current["files"] and not force:
            return {"status": "already seeded", **current}

        _last_error = None
        staging = Path(tempfile.mkdtemp(dir=str(DATA_DIR), prefix="rare_pepes_"))
        zip_path = staging / "collection.zip"

        try:
            logger.info("Downloading rare pepe collection from %s", ARCHIVE_ZIP_URL)
            with httpx.stream(
                "GET", ARCHIVE_ZIP_URL, timeout=DOWNLOAD_TIMEOUT, follow_redirects=True
            ) as response:
                response.raise_for_status()
                with open(zip_path, "wb") as handle:
                    for chunk in response.iter_bytes(1024 * 1024):
                        handle.write(chunk)

            size_mb = zip_path.stat().st_size / (1024 * 1024)
            logger.info("Downloaded %.1f MB, unpacking", size_mb)

            images = staging / "images"
            images.mkdir()
            count = _extract(zip_path, images)
            # Freed before the swap: the volume does not have room for the zip
            # and two copies of the collection at once.
            zip_path.unlink(missing_ok=True)

            if not count:
                raise RuntimeError("Archive contained no images")

            previous = RARE_PEPE_DIR.with_name(RARE_PEPE_DIR.name + "_old")
            shutil.rmtree(previous, ignore_errors=True)
            if RARE_PEPE_DIR.exists():
                RARE_PEPE_DIR.rename(previous)
            images.rename(RARE_PEPE_DIR)
            shutil.rmtree(previous, ignore_errors=True)

            logger.info("Rare pepe collection stored locally: %s images", count)
            return {"status": "seeded", **state()}
        except Exception as e:
            _last_error = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
            logger.warning("Seeding the rare pepe collection failed: %s", _last_error)
            return {"status": "failed", **state()}
        finally:
            shutil.rmtree(staging, ignore_errors=True)
    finally:
        _seeding.release()
