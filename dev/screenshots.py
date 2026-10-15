"""Capture both interface themes using demo data and Windows PrintWindow.

No network or recognition calls are made. Images are written to dev/shots.
"""
import ctypes
import json
import os
import struct
import sys
import threading
import time
import zlib
from ctypes import wintypes

import webview

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import app as application  # noqa: E402

OUT = os.path.join(ROOT, "dev", "shots")
W, H = 1280, 860

TITLES = ["How I made a car disappear", "The magic of perspective, explained",
          "Behind the scenes of my latest trick", "Three edits you never noticed",
          "Answering your questions about magic", "This took 40 takes"]


class Api:
    theme = ""

    def initial_state(self):
        return {
            "folder": r"C:\Users\you\Documents\TikTok Transcripts",
            "model": "large-v3-turbo", "language": "auto", "format": "md",
            "timestamps": False, "resume": True, "limit": None,
            "theme": self.theme,
            "ui_language": "en",
            "models": [{"id": key, **value, "downloaded": key == application.core.DEFAULT_MODEL}
                       for key, value in application.core.MODELS.items()],
            "gpu": {"ok": True, "why": "gpu ready"},
            "languages": [{"id": "auto", "name": "detect from the video"},
                          {"id": "en", "name": "english"}, {"id": "it", "name": "italian"}],
            "whisper": True, "cpu": 12,
        }

    def history(self):
        return {"ok": True, "items": [
            {"handle": "@zachking", "videos": 212, "size": 1_500_000,
             "when": "2026-10-12 21:40", "ts": 2, "path": "x"},
            {"handle": "@khaby.lame", "videos": 40, "size": 420_000,
             "when": "2026-10-10 18:02", "ts": 1, "path": "y"},
            {"handle": "@nasa", "videos": 8, "size": 52_000,
             "when": "2026-10-02 09:15", "ts": 0, "path": "z"}]}

    def about(self):
        return {"python": "3.12.10", "cpu": 12, "transcribers": 2, "threads": 0,
                "downloaders": 4, "device": "graphics card",
                "packages": [{"name": "yt-dlp", "v": "2026.8.19"},
                             {"name": "faster-whisper", "v": "1.2.1"}],
                "models": [{"id": "large-v3-turbo", "label": "large-v3 turbo",
                            "downloaded": True, "size": 1_617_000_000, "selected": True}],
                "cache": r"C:\Users\you\.cache\huggingface\hub",
                "app_folder": r"C:\tiktok-transcriber",
                "data_folder": r"C:\tiktok-transcriber\data"}

    def __getattr__(self, name):
        return lambda *a, **k: {"ok": True}


def capture(hwnd, path):
    """the window as a png, through PrintWindow (PW_RENDERFULLCONTENT)"""
    u, g = ctypes.windll.user32, ctypes.windll.gdi32
    rect = wintypes.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    dc = u.GetWindowDC(hwnd)
    mem = g.CreateCompatibleDC(dc)
    bmp = g.CreateCompatibleBitmap(dc, w, h)
    g.SelectObject(mem, bmp)
    u.PrintWindow(hwnd, mem, 2)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD),
                    ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                    ("biXPelsPerMeter", ctypes.c_long), ("biYPelsPerMeter", ctypes.c_long),
                    ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

    info = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    g.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(info), 0)
    g.DeleteObject(bmp)
    g.DeleteDC(mem)
    u.ReleaseDC(hwnd, dc)

    raw = bytearray()
    data = buf.raw
    for y in range(h):
        raw.append(0)
        row = data[y * w * 4:(y + 1) * w * 4]
        for x in range(0, len(row), 4):
            raw += bytes((row[x + 2], row[x + 1], row[x], 255))

    def chunk(kind, body):
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


DEMO_RUN = """
window.receiveEvents([{type:'profile', handle:'zachking', total:null}]);
const titles = %s;
const ev = [];
for (let i=0;i<40;i++) ev.push({type:'video', id:'v'+i, index:i, state:'queued',
  title:titles[i%%titles.length], duration:18+(i*7)%%70, url:'https://www.tiktok.com/@zachking/video/'+i});
window.receiveEvents(ev);
const st = [];
for (let i=0;i<14;i++) st.push({type:'video', id:'v'+i, state:'done', words:40+i*9, language:'en'});
st.push({type:'video', id:'v14', state:'error', message:'tiktok refused the request (403). almost always the session'});
st.push({type:'video', id:'v15', state:'downloading'}, {type:'percent', id:'v15', pct:55});
st.push({type:'video', id:'v16', state:'transcribing'});
st.push({type:'progress', done:15, ok:14, errors:1, skipped:0, running:2, queued:23, total:40, listing:false, eta:190});
st.push({type:'log', text:'reading public videos', level:'ok'});
st.push({type:'log', text:'model ready in 3.1s on cuda, 2 transcriptions in parallel', level:'ok'});
st.push({type:'log', text:'language: en. taking it as given from here on, which is faster.', level:'info'});
window.receiveEvents(st);
""" % json.dumps(TITLES)

DEMO_GALLERY = """
document.querySelector('[data-view=gallery]').click();
document.querySelector('#gal-profile').value='@zachking';
window.receiveEvents([{type:'gal_start', handle:'zachking', folder:'x'}]);
const shades = ['#2c3b4d','#a35139','#c9c1b1','#6e3424','#1b2632','#ffb162'];
const cover = (i) => 'data:image/svg+xml;utf8,' + encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 9 16"><rect width="9" height="16" fill="'+shades[i%%6]+'"/>'
  + '<rect x="2" y="5" width="5" height="6" fill="'+shades[(i+2)%%6]+'"/></svg>');
const titles = %s;
window.receiveEvents([{type:'gal_batch', total:10, videos: Array.from({length:10}, (_,i) => ({
  id:'g'+i, title:titles[i%%titles.length], duration:20+i*9, timestamp:1791000000-i*86400,
  cover:cover(i), views:120000*(i+1), likes:9000*(i+2), done:i%%4===1, file:i%%4===1?'f':null,
  downloaded:false, video_file:null, url:'https://www.tiktok.com/@zachking/video/'+i}))}]);
window.receiveEvents([{type:'gal_done', total:10, stopped:false}]);
// the cards go in on the next frame: their states come after
setTimeout(() => window.receiveEvents([
  {type:'gallery', id:'g2', state:'downloading', pct:58},
  {type:'gallery', id:'g6', state:'error', message:'tiktok refused the request'}]), 300);
// what hovering a card looks like: focus shows the same three buttons
setTimeout(() => document.querySelector('[data-id=g0] .transcribe').focus(), 400);
""" % json.dumps(TITLES)


def shoot(theme, results):
    api = Api()
    api.theme = theme
    w = webview.create_window("shots", html=application.read_interface(), js_api=api,
                              width=W, height=H, frameless=True, easy_drag=False,
                              background_color="#1B2632" if theme != "light" else "#EEE9DF")

    def run():
        try:
            time.sleep(4)
            hwnd = w.native.Handle.ToInt64()
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            time.sleep(2.5)   # Orbi's entrance takes a few seconds
            capture(hwnd, os.path.join(OUT, f"{theme}-home.png"))
            w.evaluate_js(DEMO_RUN)
            w.evaluate_js("document.querySelector('.pane').scrollTop ="
                          " document.querySelector('#card-progress').offsetTop - 24")
            time.sleep(1)
            capture(hwnd, os.path.join(OUT, f"{theme}-progress.png"))
            w.evaluate_js("document.querySelector('.pane').scrollTop ="
                          " document.querySelector('.options').offsetTop - 120")
            time.sleep(0.6)
            capture(hwnd, os.path.join(OUT, f"{theme}-options.png"))
            w.evaluate_js(DEMO_GALLERY)
            time.sleep(1.2)
            capture(hwnd, os.path.join(OUT, f"{theme}-gallery.png"))
            w.evaluate_js("document.querySelector('[data-view=history]').click()")
            time.sleep(0.8)
            capture(hwnd, os.path.join(OUT, f"{theme}-history.png"))
            w.evaluate_js("document.querySelector('[data-view=about]').click()")
            time.sleep(0.8)
            capture(hwnd, os.path.join(OUT, f"{theme}-about.png"))
            results.append(w.evaluate_js(
                "JSON.stringify({orbi: !!(window.Orbi && Orbi.instances.length),"
                " step: window.Orbi && Orbi.instances[0] ? Orbi.instances[0].state().step : -1,"
                " theme: document.documentElement.dataset.theme || 'system'})"))
        except Exception as e:
            results.append(f"error: {e}")
        finally:
            w.destroy()

    threading.Thread(target=run, daemon=True).start()


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    themes = sys.argv[1:] or ["dark", "light"]
    for theme in themes:
        results = []
        shoot(theme, results)
        webview.start(gui="edgechromium", private_mode=True)
        print(theme, results)
    print("pictures in", OUT)
