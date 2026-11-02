#!/usr/bin/env python3
"""Photo server for the ESP32-P4 panel's screensaver page.

Every GET /photo hands out the next image under PHOTO_DIR, fixes its EXIF
rotation, resizes it to fit WIDTH x HEIGHT, and returns it as a JPEG the
panel's online_image component can decode. Resizing here (instead of on the
panel) keeps a 12MP phone photo from ever reaching the ESP32.

Photos are served in ascending file-name order and wrap around at the end, so
the panel walks the library as a cycle rather than repeating/skipping photos
the way random picking does. Set ORDER=random for the old behaviour.

GET /grafana serves the panel's Grafana status page: the newest image in
GRAFANA_DIR, resized the same way. Something outside this repo writes that
image, so anything older than GRAFANA_MAX_AGE seconds gets a red STALE banner
rather than passing off an old status as the current one.

Config via environment variables: PHOTO_DIR, WIDTH, HEIGHT, QUALITY, PORT,
RESCAN_SECONDS, ORDER, GRAFANA_DIR, GRAFANA_MAX_AGE. See docker-compose.yml.
"""

import io
import os
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PIL import Image, ImageDraw, ImageFont, ImageOps

# HEIC/HEIF (iPhone photos) supported when pillow-heif is installed.
try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIF_EXTS = (".heic", ".heif")
except ImportError:
    HEIF_EXTS = ()

PHOTO_DIR = os.environ.get("PHOTO_DIR", "/photos")
WIDTH = int(os.environ.get("WIDTH", "1280"))
HEIGHT = int(os.environ.get("HEIGHT", "800"))
QUALITY = int(os.environ.get("QUALITY", "85"))
PORT = int(os.environ.get("PORT", "8128"))
RESCAN_SECONDS = int(os.environ.get("RESCAN_SECONDS", "600"))
ORDER = os.environ.get("ORDER", "sequential").strip().lower()
GRAFANA_DIR = os.environ.get("GRAFANA_DIR", "/grafana-export")
GRAFANA_MAX_AGE = int(os.environ.get("GRAFANA_MAX_AGE", "600"))

EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".webp") + HEIF_EXTS

_files: list[str] = []
_scanned_at = 0.0
_cursor = 0  # index of the photo to serve next, in _files
_current = ""  # last path handed out, so a rescan can resume after it
# Re-entrant: next_path() holds the lock while calling photo_list().
_lock = threading.RLock()

_grafana_lock = threading.Lock()
_grafana_frame: Image.Image | None = None  # last export that decoded cleanly
_grafana_source: tuple[str, float] | None = None  # its (path, mtime)


def photo_list() -> list[str]:
    """Recursive file list under PHOTO_DIR, cached for RESCAN_SECONDS."""
    global _files, _scanned_at, _cursor
    with _lock:
        if not _files or time.time() - _scanned_at > RESCAN_SECONDS:
            files = []
            for root, dirs, names in os.walk(PHOTO_DIR):
                # Skip hidden dirs and Synology's @eaDir thumbnail trees.
                dirs[:] = [d for d in dirs if not d.startswith((".", "@"))]
                for name in names:
                    if name.lower().endswith(EXTS) and not name.startswith("."):
                        files.append(os.path.join(root, name))
            # Ascending by file name, ignoring which folder a photo sits in
            # (camera filenames like IMG_1234.JPG are roughly date order).
            # Case-insensitive, with the full path as tie-breaker so two
            # same-named files in different folders keep a stable order.
            files.sort(key=lambda f: (os.path.basename(f).lower(), f))
            _files = files
            _scanned_at = time.time()
            # Keep our place across a rescan: photos added or removed earlier
            # in the list would otherwise shift the cursor and replay/skip a
            # stretch of the library. Resume right after the last one served.
            if _current in files:
                _cursor = files.index(_current) + 1
            elif _cursor > len(files):
                _cursor = 0
            print(f"scanned {PHOTO_DIR}: {len(files)} photos", flush=True)
        return _files


def next_path() -> str | None:
    """Next photo in the cycle (or a random one when ORDER=random)."""
    global _cursor, _current
    with _lock:
        files = photo_list()
        if not files:
            return None
        if ORDER == "random":
            return random.choice(files)
        _cursor %= len(files)
        path = files[_cursor]
        _cursor += 1
        _current = path
        return path


def render_next_photo() -> bytes | None:
    # A deleted/corrupt file shouldn't error out the panel — try a few in a
    # row; each failed pick has already advanced the cursor past it.
    for _ in range(5):
        path = next_path()
        if path is None:
            return None
        try:
            with Image.open(path) as im:
                im = ImageOps.exif_transpose(im)
                im.thumbnail((WIDTH, HEIGHT), Image.LANCZOS)
                if im.mode != "RGB":
                    im = im.convert("RGB")
                buf = io.BytesIO()
                im.save(buf, "JPEG", quality=QUALITY)
                return buf.getvalue()
        except Exception as exc:  # noqa: BLE001 - any bad file, skip it
            print(f"skipping {path}: {exc}", flush=True)
    return None


def newest_grafana_export() -> tuple[str, float] | None:
    """(path, mtime) of the newest image in GRAFANA_DIR, if there is one."""
    try:
        with os.scandir(GRAFANA_DIR) as entries:
            found = [
                (entry.path, entry.stat().st_mtime)
                for entry in entries
                if entry.is_file()
                and entry.name.lower().endswith(EXTS)
                and not entry.name.startswith(".")
            ]
    except OSError:
        return None
    return max(found, key=lambda item: item[1], default=None)


def stamp_stale(frame: Image.Image, age_seconds: float) -> Image.Image:
    """Copy of frame with a red banner saying how old the export is."""
    frame = frame.copy()
    draw = ImageDraw.Draw(frame)
    draw.rectangle((0, 0, frame.width, 48), fill=(190, 20, 20))
    draw.text(
        (16, 8),
        f"STALE - last export {int(age_seconds // 60)} min ago",
        fill="white",
        font=ImageFont.load_default(size=28),
    )
    return frame


def render_grafana() -> bytes | None:
    global _grafana_frame, _grafana_source
    with _grafana_lock:
        newest = newest_grafana_export()
        if newest is not None and newest != _grafana_source:
            try:
                with Image.open(newest[0]) as im:
                    im.thumbnail((WIDTH, HEIGHT), Image.LANCZOS)
                    _grafana_frame = im.convert("RGB")
                _grafana_source = newest
            except Exception as exc:  # noqa: BLE001 - e.g. caught mid-write
                print(f"skipping {newest[0]}: {exc}", flush=True)
        if _grafana_frame is None or _grafana_source is None:
            return None
        frame = _grafana_frame
        age = time.time() - _grafana_source[1]
        if age > GRAFANA_MAX_AGE:
            frame = stamp_stale(frame, age)
        buf = io.BytesIO()
        frame.save(buf, "JPEG", quality=QUALITY)
        return buf.getvalue()


class Handler(BaseHTTPRequestHandler):
    def send_jpeg(self, data: bytes):
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        route = self.path.split("?", 1)[0]
        if route in ("/", "/photo"):
            data = render_next_photo()
            if data is None:
                self.send_error(503, f"no readable photos in {PHOTO_DIR}")
                return
            self.send_jpeg(data)
        elif route == "/grafana":
            data = render_grafana()
            if data is None:
                self.send_error(503, f"no readable images in {GRAFANA_DIR}")
                return
            self.send_jpeg(data)
        elif route == "/health":
            with _lock:
                total = len(photo_list())
                body = f"{total} photos, {ORDER}, next #{_cursor + 1}\n".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def log_message(self, fmt, *args):
        pass  # one log line per photo request is just noise


if __name__ == "__main__":
    print(f"serving photos from {PHOTO_DIR} on :{PORT} in {ORDER} order", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
