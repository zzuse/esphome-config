#!/usr/bin/env python3
"""Random-photo server for the ESP32-P4 panel's screensaver page.

Every GET /photo picks a random image under PHOTO_DIR, fixes its EXIF
rotation, resizes it to fit WIDTH x HEIGHT, and returns it as a JPEG the
panel's online_image component can decode. Resizing here (instead of on the
panel) keeps a 12MP phone photo from ever reaching the ESP32.

Config via environment variables: PHOTO_DIR, WIDTH, HEIGHT, QUALITY, PORT,
RESCAN_SECONDS. See docker-compose.yml.
"""

import io
import os
import random
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PIL import Image, ImageOps

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

EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".webp") + HEIF_EXTS

_files: list[str] = []
_scanned_at = 0.0
_lock = threading.Lock()


def photo_list() -> list[str]:
    """Recursive file list under PHOTO_DIR, cached for RESCAN_SECONDS."""
    global _files, _scanned_at
    with _lock:
        if not _files or time.time() - _scanned_at > RESCAN_SECONDS:
            files = []
            for root, dirs, names in os.walk(PHOTO_DIR):
                # Skip hidden dirs and Synology's @eaDir thumbnail trees.
                dirs[:] = [d for d in dirs if not d.startswith((".", "@"))]
                for name in names:
                    if name.lower().endswith(EXTS) and not name.startswith("."):
                        files.append(os.path.join(root, name))
            _files = files
            _scanned_at = time.time()
            print(f"scanned {PHOTO_DIR}: {len(files)} photos", flush=True)
        return _files


def render_random_photo() -> bytes | None:
    files = photo_list()
    # A deleted/corrupt file shouldn't error out the panel — try a few picks.
    for _ in range(5):
        if not files:
            return None
        path = random.choice(files)
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


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        route = self.path.split("?", 1)[0]
        if route in ("/", "/photo"):
            data = render_random_photo()
            if data is None:
                self.send_error(503, f"no readable photos in {PHOTO_DIR}")
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        elif route == "/health":
            body = f"{len(photo_list())} photos\n".encode()
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
    print(f"serving photos from {PHOTO_DIR} on :{PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
