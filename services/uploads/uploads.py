import os
import random
import re
import shutil
import uuid
from io import BytesIO

from PIL import Image as PILImage

from util.phlog import PIHOME_LOGGER

# User-uploaded images live here.  This directory is gitignored — it holds the
# user's own image files (and is shared across screens, not just wallpaper).
UPLOAD_DIR = "./uploads"

# Images are grouped into albums (subdirectories of UPLOAD_DIR).  An image lives
# in exactly one album.  This reserved album always exists and cannot be deleted.
DEFAULT_ALBUM = "Default"

# Allowed image extensions for storage.  ``.gif`` is allowed for storage but the
# wallpaper source skips animated gifs (mirrors the existing ".gif" filter).
ALLOWED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")

# Reject anything larger than this on upload (raw decoded bytes).
MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB


class Uploads:
    """Passive store for user-uploaded images, grouped into albums.

    Owns the ``./uploads`` directory.  Each album is a subdirectory; an image
    lives in exactly one album.  Exposes a small, safe API so any screen (not
    just the wallpaper service) can list, fetch, add, or remove user images.
    There is no background work — this is plain file storage.
    """

    def __init__(self, **kwargs):
        super(Uploads, self).__init__(**kwargs)
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        os.makedirs(os.path.join(UPLOAD_DIR, DEFAULT_ALBUM), exist_ok=True)
        self._migrate_flat_uploads()

    # ── Internal helpers ──────────────────────────────────────────────

    def _migrate_flat_uploads(self):
        """Move any loose image files in UPLOAD_DIR (pre-album layout) into the
        Default album.  Idempotent — a no-op once nothing sits at the root."""
        try:
            entries = os.listdir(UPLOAD_DIR)
        except OSError:
            return
        default_dir = os.path.join(UPLOAD_DIR, DEFAULT_ALBUM)
        for entry in entries:
            src = os.path.join(UPLOAD_DIR, entry)
            if os.path.isfile(src) and os.path.splitext(entry)[1].lower() in ALLOWED_EXTENSIONS:
                try:
                    shutil.move(src, os.path.join(default_dir, entry))
                    PIHOME_LOGGER.info("Uploads: migrated {} into {}".format(entry, DEFAULT_ALBUM))
                except OSError as e:
                    PIHOME_LOGGER.error("Uploads: failed to migrate {}: {}".format(entry, e))

    def _safe_album(self, album):
        """Sanitize an album name to a safe directory name. Returns None if empty."""
        if not album:
            return None
        name = re.sub(r"[^A-Za-z0-9 _-]", "_", str(album)).strip(" ._-")
        name = re.sub(r"\s+", " ", name)[:48]
        return name or None

    def _album_dir(self, album):
        """Resolve an album to an absolute directory path *inside* UPLOAD_DIR.

        Returns ``None`` if the name is empty or escapes UPLOAD_DIR.  Does not
        require the directory to exist (callers create it as needed).
        """
        safe = self._safe_album(album)
        if safe is None:
            return None
        base = os.path.abspath(UPLOAD_DIR)
        path = os.path.abspath(os.path.join(base, safe))
        if os.path.commonpath([base, path]) != base or path == base:
            return None
        return path

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

    # ── Album management ──────────────────────────────────────────────

    def list_albums(self):
        """Return albums as ``[{"name", "count"}]``, Default first then A–Z."""
        if not os.path.isdir(UPLOAD_DIR):
            return []
        albums = []
        for entry in os.listdir(UPLOAD_DIR):
            d = os.path.join(UPLOAD_DIR, entry)
            if os.path.isdir(d):
                albums.append({"name": entry, "count": len(self.list_images(entry))})
        albums.sort(key=lambda a: (a["name"] != DEFAULT_ALBUM, a["name"].lower()))
        return albums

    def create_album(self, name):
        """Create an album. Returns the sanitized name, or None if invalid."""
        d = self._album_dir(name)
        if d is None:
            return None
        os.makedirs(d, exist_ok=True)
        PIHOME_LOGGER.info("Uploads: created album {}".format(os.path.basename(d)))
        return os.path.basename(d)

    def delete_album(self, name):
        """Delete an album directory AND all images inside it.

        Refuses to delete the Default album. Returns True if removed.
        """
        d = self._album_dir(name)
        if d is None or os.path.basename(d) == DEFAULT_ALBUM:
            return False
        if not os.path.isdir(d):
            return False
        try:
            shutil.rmtree(d)
            PIHOME_LOGGER.info("Uploads: deleted album {}".format(os.path.basename(d)))
            return True
        except OSError as e:
            PIHOME_LOGGER.error("Uploads: failed to delete album {}: {}".format(name, e))
            return False

    def rename_album(self, old, new):
        """Rename an album. Refuses to rename Default. Returns new name or None."""
        old_dir = self._album_dir(old)
        new_dir = self._album_dir(new)
        if old_dir is None or new_dir is None:
            return None
        if os.path.basename(old_dir) == DEFAULT_ALBUM:
            return None
        if not os.path.isdir(old_dir) or os.path.exists(new_dir):
            return None
        try:
            os.rename(old_dir, new_dir)
            PIHOME_LOGGER.info("Uploads: renamed album {} -> {}".format(
                os.path.basename(old_dir), os.path.basename(new_dir)))
            return os.path.basename(new_dir)
        except OSError as e:
            PIHOME_LOGGER.error("Uploads: failed to rename album {}: {}".format(old, e))
            return None

    # ── Image API (album-scoped) ──────────────────────────────────────

    def save_image(self, filename, raw_bytes, album=DEFAULT_ALBUM):
        """Validate and persist *raw_bytes* into *album*. Returns the stored name.

        Raises ``ValueError`` on an invalid album, oversized payload, or
        non-image content.
        """
        album_dir = self._album_dir(album)
        if album_dir is None:
            raise ValueError("invalid album")
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

        os.makedirs(album_dir, exist_ok=True)
        name = self._safe_name(filename)
        with open(os.path.join(album_dir, name), "wb") as f:
            f.write(raw_bytes)
        PIHOME_LOGGER.info("Uploads: saved image {}/{}".format(os.path.basename(album_dir), name))
        return name

    def list_images(self, album=DEFAULT_ALBUM):
        """Return image filenames in *album*, newest first."""
        album_dir = self._album_dir(album)
        if album_dir is None or not os.path.isdir(album_dir):
            return []
        names = [
            f for f in os.listdir(album_dir)
            if os.path.splitext(f)[1].lower() in ALLOWED_EXTENSIONS
            and os.path.isfile(os.path.join(album_dir, f))
        ]
        names.sort(
            key=lambda n: os.path.getmtime(os.path.join(album_dir, n)),
            reverse=True,
        )
        return names

    def list_page(self, album=DEFAULT_ALBUM, offset=0, limit=24):
        """Return a paginated slice of an album plus the total count.

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

        names = self.list_images(album)
        page = names[offset:offset + limit]
        return {"names": page, "total": len(names), "offset": offset, "limit": limit}

    def path_for(self, album, name):
        """Resolve an album + name to an absolute path *inside* that album dir.

        Returns ``None`` if either segment escapes UPLOAD_DIR or the file is
        missing.
        """
        album_dir = self._album_dir(album)
        if album_dir is None:
            return None
        if not name or ".." in name or "/" in name or "\\" in name:
            return None
        path = os.path.abspath(os.path.join(album_dir, name))
        if os.path.commonpath([album_dir, path]) != album_dir:
            return None
        if not os.path.isfile(path):
            return None
        return path

    def delete_image(self, album, name):
        """Delete an image from *album*. Returns True if a file was removed."""
        path = self.path_for(album, name)
        if path is None:
            return False
        try:
            os.remove(path)
            PIHOME_LOGGER.info("Uploads: deleted image {}/{}".format(album, name))
            return True
        except OSError as e:
            PIHOME_LOGGER.error("Uploads: failed to delete {}/{}: {}".format(album, name, e))
            return False

    def random_image(self, album=DEFAULT_ALBUM):
        """Return the absolute path of a random (non-gif) image in *album*, or None."""
        album_dir = self._album_dir(album)
        if album_dir is None:
            return None
        names = [n for n in self.list_images(album) if not n.lower().endswith(".gif")]
        if not names:
            return None
        return os.path.join(album_dir, random.choice(names))


UPLOADS = Uploads()
