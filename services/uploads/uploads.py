import os
import random
import re
import uuid
from io import BytesIO

from PIL import Image as PILImage

from util.phlog import PIHOME_LOGGER

# User-uploaded images live here.  This directory is gitignored — it holds the
# user's own image files (and is shared across screens, not just wallpaper).
UPLOAD_DIR = "./uploads"

# Allowed image extensions for storage.  ``.gif`` is allowed for storage but the
# wallpaper source skips animated gifs (mirrors the existing ".gif" filter).
ALLOWED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")

# Reject anything larger than this on upload (raw decoded bytes).
MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB


class Uploads:
    """Passive store for user-uploaded images.

    Owns the ``./uploads`` directory and exposes a small, safe API so any screen
    (not just the wallpaper service) can list, fetch, add, or remove user images.
    There is no background work — this is plain file storage.
    """

    def __init__(self, **kwargs):
        super(Uploads, self).__init__(**kwargs)
        os.makedirs(UPLOAD_DIR, exist_ok=True)

    # ── Internal helpers ──────────────────────────────────────────────

    def _safe_name(self, filename):
        """Produce a collision-free, traversal-safe storage name.

        Keeps the original (slugified) stem for readability and appends a short
        unique suffix so repeated uploads of the same name don't clobber each
        other.  The server never trusts the client-supplied name as a path.
        """
        base = os.path.basename(filename or "")
        stem, ext = os.path.splitext(base)
        ext = ext.lower()
        if ext not in ALLOWED_EXTENSIONS:
            ext = ".png"
        stem = re.sub(r"[^A-Za-z0-9._-]", "_", stem).strip("._-") or "image"
        stem = stem[:48]
        return "{}_{}{}".format(stem, uuid.uuid4().hex[:8], ext)

    # ── Public API ────────────────────────────────────────────────────

    def save_image(self, filename, raw_bytes):
        """Validate and persist *raw_bytes* as an image. Returns the stored name.

        Raises ``ValueError`` on oversized payloads or non-image content.
        """
        if raw_bytes is None or len(raw_bytes) == 0:
            raise ValueError("empty image payload")
        if len(raw_bytes) > MAX_UPLOAD_BYTES:
            raise ValueError(
                "image too large ({} bytes, max {})".format(len(raw_bytes), MAX_UPLOAD_BYTES)
            )

        # Verify the bytes really are a decodable image before touching disk.
        try:
            PILImage.open(BytesIO(raw_bytes)).verify()
        except Exception as e:
            raise ValueError("not a valid image: {}".format(e))

        name = self._safe_name(filename)
        path = os.path.join(UPLOAD_DIR, name)
        with open(path, "wb") as f:
            f.write(raw_bytes)
        PIHOME_LOGGER.info("Uploads: saved image {}".format(name))
        return name

    def list_images(self):
        """Return all stored image filenames, newest first."""
        if not os.path.isdir(UPLOAD_DIR):
            return []
        names = [
            f for f in os.listdir(UPLOAD_DIR)
            if os.path.splitext(f)[1].lower() in ALLOWED_EXTENSIONS
            and os.path.isfile(os.path.join(UPLOAD_DIR, f))
        ]
        names.sort(
            key=lambda n: os.path.getmtime(os.path.join(UPLOAD_DIR, n)),
            reverse=True,
        )
        return names

    def list_page(self, offset=0, limit=24):
        """Return a paginated slice of stored images plus the total count.

        Pagination keeps the web gallery from requesting hundreds of images at
        once, which would overload the Pi's single-threaded HTTP server.
        """
        try:
            offset = max(0, int(offset))
        except (TypeError, ValueError):
            offset = 0
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 24
        limit = max(1, min(limit, 100))  # clamp to a sane page size

        names = self.list_images()
        page = names[offset:offset + limit]
        return {"names": page, "total": len(names), "offset": offset, "limit": limit}

    def path_for(self, name):
        """Resolve a stored name to an absolute path *inside* UPLOAD_DIR.

        Returns ``None`` if the name escapes the directory or doesn't exist.
        """
        if not name or ".." in name or "/" in name or "\\" in name:
            return None
        base = os.path.abspath(UPLOAD_DIR)
        path = os.path.abspath(os.path.join(base, name))
        if os.path.commonpath([base, path]) != base:
            return None
        if not os.path.isfile(path):
            return None
        return path

    def delete_image(self, name):
        """Delete a stored image. Returns True if a file was removed."""
        path = self.path_for(name)
        if path is None:
            return False
        try:
            os.remove(path)
            PIHOME_LOGGER.info("Uploads: deleted image {}".format(name))
            return True
        except OSError as e:
            PIHOME_LOGGER.error("Uploads: failed to delete {}: {}".format(name, e))
            return False

    def random_image(self):
        """Return the absolute path of a random stored (non-gif) image, or None."""
        names = [n for n in self.list_images() if not n.lower().endswith(".gif")]
        if not names:
            return None
        return os.path.join(UPLOAD_DIR, random.choice(names))


UPLOADS = Uploads()
