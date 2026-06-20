#!/usr/bin/env python3
"""
LAN photo gallery server with folder navigation and a swipeable
full-screen viewer.

Usage:
  1. Put this script in the top-level folder you want to browse from
     (it will let you navigate into subfolders and back out).
  2. Run: python3 gallery_server.py
  3. On your device of choice (same Wi-Fi network as this PC), open the URL
     it prints, e.g. http://000.123.0.00:8000
  4. Tap a folder to go into it, tap ".." or a breadcrumb to go back up.
  5. Tap a photo to open it full-screen, then swipe left/right to move (if on a touch device)
     between photos in that folder. Tap the image or the X to close.
"""

import http.server
import socketserver
import os
import socket
import json
import urllib.parse

PORT = 8000
PHOTO_DIR = '.'  # the top-level folder; subfolders are browsable from here
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.heic'}

ROOT_REAL = os.path.realpath(PHOTO_DIR)


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip


def safe_join(rel_path):
    rel_path = rel_path.strip('/')
    candidate = os.path.normpath(os.path.join(PHOTO_DIR, rel_path)) if rel_path else os.path.normpath(PHOTO_DIR)
    real_candidate = os.path.realpath(candidate)
    if real_candidate != ROOT_REAL and not real_candidate.startswith(ROOT_REAL + os.sep):
        return PHOTO_DIR, ''
    return candidate, rel_path.replace('\\', '/')


def url_path(rel_path):
    parts = [p for p in rel_path.split('/') if p]
    return '/'.join(urllib.parse.quote(p) for p in parts)


class GalleryHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PHOTO_DIR, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path in ('/', '/index.html'):
            qs = urllib.parse.parse_qs(parsed.query)
            raw_rel = qs.get('path', [''])[0]
            self.send_gallery(raw_rel)
        else:
            super().do_GET()

    def send_gallery(self, raw_rel):
        target_dir, rel_path = safe_join(raw_rel)

        try:
            entries = os.listdir(target_dir)
        except OSError:
            entries = []

        folders = sorted(
            e for e in entries
            if not e.startswith('.') and os.path.isdir(os.path.join(target_dir, e))
        )
        images = sorted(
            e for e in entries
            if os.path.splitext(e)[1].lower() in IMAGE_EXTENSIONS
        )

        # breadcrumb
        crumbs = [('Home', '')]
        accum = ''
        if rel_path:
            for part in rel_path.split('/'):
                accum = f'{accum}/{part}' if accum else part
                crumbs.append((part, accum))

        breadcrumb_html = ' / '.join(
            f'<a href="/?path={url_path(p)}">{name}</a>' for name, p in crumbs
        )

        tiles = []

        if rel_path:
            parent = '/'.join(rel_path.split('/')[:-1])
            tiles.append(
                f'<a href="/?path={url_path(parent)}" class="tile folder">'
                f'<div class="icon">&#8593;</div><div class="label">..</div></a>'
            )

        for folder in folders:
            child_rel = f'{rel_path}/{folder}' if rel_path else folder
            tiles.append(
                f'<a href="/?path={url_path(child_rel)}" class="tile folder">'
                f'<div class="icon">&#128193;</div><div class="label">{folder}</div></a>'
            )

        img_index = 0
        for img in images:
            img_url = ('/' + url_path(rel_path) + '/' if rel_path else '/') + urllib.parse.quote(img)
            tiles.append(
                f'<a href="#" class="tile thumb" data-index="{img_index}">'
                f'<img src="{img_url}" loading="lazy" alt="{img}"></a>'
            )
            img_index += 1

        tiles_html = '\n'.join(tiles) if tiles else '<p class="empty">Nothing here.</p>'
        images_json = json.dumps([
            ('/' + url_path(rel_path) + '/' if rel_path else '/') + urllib.parse.quote(img)
            for img in images
        ])

        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no">
<title>Photo Gallery</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 16px; background: #111; font-family: -apple-system, sans-serif; }}
  .crumbs {{ color: #999; font-size: 13px; margin-bottom: 12px; word-break: break-word; }}
  .crumbs a {{ color: #6cf; text-decoration: none; }}
  h1 {{ color: #eee; font-size: 16px; font-weight: 500; margin: 0 0 16px; }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
    gap: 8px;
  }}
  .tile {{ display: block; aspect-ratio: 1; overflow: hidden; border-radius: 6px; text-decoration: none; }}
  .tile.thumb img {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
  .tile.folder {{
    background: #1d1d1d; display: flex; flex-direction: column;
    align-items: center; justify-content: center; gap: 6px;
    border: 1px solid #2a2a2a;
  }}
  .tile.folder .icon {{ font-size: 32px; }}
  .tile.folder .label {{
    color: #ccc; font-size: 12px; text-align: center; padding: 0 4px;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%;
  }}
  .empty {{ color: #888; }}

  #viewer {{
    position: fixed; inset: 0; background: #000;
    display: none; align-items: center; justify-content: center;
    z-index: 1000; touch-action: pan-y;
    overscroll-behavior: contain;
  }}
  #viewer.open {{ display: flex; }}
  #viewer img {{
    max-width: 100%; max-height: 100%; object-fit: contain;
    user-select: none; -webkit-user-drag: none;
  }}
  #closeBtn {{
    position: absolute; top: 16px; right: 16px;
    width: 40px; height: 40px; border-radius: 50%;
    background: rgba(255,255,255,0.15); color: #fff;
    border: none; font-size: 20px; line-height: 40px; text-align: center;
    z-index: 1001;
  }}
  #counter {{
    position: absolute; top: 24px; left: 16px;
    color: #ddd; font-size: 14px; z-index: 1001;
  }}
</style>
</head>
<body>
<div class="crumbs">{breadcrumb_html}</div>
<h1>{len(folders)} folder{'s' if len(folders) != 1 else ''}, {len(images)} photo{'s' if len(images) != 1 else ''}</h1>
<div class="grid">
{tiles_html}
</div>

<div id="viewer">
  <div id="counter"></div>
  <button id="closeBtn" aria-label="Close">&times;</button>
  <img id="viewerImg" src="" alt="">
</div>

<script>
const images = {images_json};
let current = 0;

const viewer = document.getElementById('viewer');
const viewerImg = document.getElementById('viewerImg');
const counter = document.getElementById('counter');
const closeBtn = document.getElementById('closeBtn');

function show(index) {{
  if (images.length === 0) return;
  current = (index + images.length) % images.length;
  viewerImg.src = images[current];
  counter.textContent = (current + 1) + ' / ' + images.length;
}}

function openViewer(index) {{
  show(index);
  viewer.classList.add('open');
}}

function closeViewer() {{
  viewer.classList.remove('open');
  viewerImg.src = '';
}}

document.querySelectorAll('.tile.thumb').forEach(el => {{
  el.addEventListener('click', e => {{
    e.preventDefault();
    openViewer(parseInt(el.dataset.index, 10));
  }});
}});

closeBtn.addEventListener('click', closeViewer);

viewer.addEventListener('click', e => {{
  if (e.target === viewer) closeViewer();
}});

let touchStartX = null;
let touchStartY = null;
const SWIPE_THRESHOLD = 50;

viewer.addEventListener('touchstart', e => {{
  touchStartX = e.changedTouches[0].clientX;
  touchStartY = e.changedTouches[0].clientY;
}}, {{ passive: true }});

viewer.addEventListener('touchend', e => {{
  if (touchStartX === null) return;
  const dx = e.changedTouches[0].clientX - touchStartX;
  const dy = e.changedTouches[0].clientY - touchStartY;

  if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > SWIPE_THRESHOLD) {{
    if (dx < 0) {{
      show(current + 1);
    }} else {{
      show(current - 1);
    }}
  }} else if (Math.abs(dy) > 80 && dy > 0) {{
    closeViewer();
  }} else if (Math.abs(dx) < 10 && Math.abs(dy) < 10) {{
    closeViewer();
  }}
  touchStartX = null;
  touchStartY = null;
}});

document.addEventListener('keydown', e => {{
  if (!viewer.classList.contains('open')) return;
  if (e.key === 'ArrowRight') show(current + 1);
  if (e.key === 'ArrowLeft') show(current - 1);
  if (e.key === 'Escape') closeViewer();
}});
</script>
</body>
</html>"""

        encoded = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        pass  # quiet the default request logging


if __name__ == '__main__':
    ip = get_local_ip()
    with socketserver.TCPServer(('0.0.0.0', PORT), GalleryHandler) as httpd:
        print('Photo gallery running.')
        print(f'Open this on your phone (same Wi-Fi network): http://{ip}:{PORT}')
        print('Press Ctrl+C to stop.')
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('\nStopped.')