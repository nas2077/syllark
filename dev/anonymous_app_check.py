"""Exercise the real app and real TikTok/Whisper through WebView2 buttons.

Disposable settings/output, a cached model and a hard guard against reading any
browser account. Covers profile transcription, gallery transcription and download.
"""
import json
import os
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path
from unittest.mock import patch

import webview

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import app
import tiktok_core as core

finished = threading.Event()
failed = False


def until(window, expression, timeout=100):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = window.evaluate_js(expression)
        if value:
            return value
        time.sleep(.2)
    raise AssertionError("Timed out: " + expression)


def run(window, output):
    global failed
    try:
        until(window, "document.querySelector('#model').options.length>0")
        window.evaluate_js("document.querySelector('#how-many').add(new Option('2','2'));document.querySelector('#how-many').value='2';document.querySelector('#profile').value='@nasa';document.querySelector('#go').click();")
        until(window, "!S.active")
        assert window.evaluate_js("Number(document.querySelector('#s-ok').textContent)") == 2
        assert window.evaluate_js("Number(document.querySelector('#s-err').textContent)") == 0
        folder = output / "@nasa"
        assert len(core.transcripts_on_disk(str(folder))) == 2
        assert api.workshop._engine.name == "qwen3-asr"
        assert (folder / "_ALL @nasa.md").is_file() and (folder / "_index @nasa.csv").is_file()
        print("OK: real Transcribe button -> public profile -> two Natural transcripts -> exports", flush=True)

        window.evaluate_js("document.querySelector('[data-view=gallery]').click();document.querySelector('#gal-profile').value='@zachking';document.querySelector('#gal-how-many').add(new Option('2','2'));document.querySelector('#gal-how-many').value='2';document.querySelector('#gal-go').click();")
        until(window, "!S.galLoading && document.querySelectorAll('#gal-grid .gv').length===2")
        window.evaluate_js("document.querySelector('#gal-opts').click();document.querySelector('#g-format [data-v=txt]').click();document.querySelector('#g-times').click();const m=document.querySelector('#model');m.value='small';m.dispatchEvent(new Event('change'));const l=document.querySelector('#language');l.value='en';l.dispatchEvent(new Event('change'));window.pywebview.api.save_settings({whisper_model:'small',language:'en',format:'txt',timestamps:true}).then(()=>window.__galleryPrefsSaved=true);")
        until(window, "window.__galleryPrefsSaved")
        window.evaluate_js("document.querySelector('#gal-grid .transcribe').click();")
        until(window, "document.querySelector('#gal-grid .gv').dataset.f==='1'")
        until(window, "document.querySelector('#gal-grid .gv')._v.file")
        folder = output / "@zachking"
        assert len(core.transcripts_on_disk(str(folder))) == 1
        transcript = Path(next(iter(core.transcripts_on_disk(str(folder)).values())))
        assert transcript.suffix == ".txt"
        header, text = core._read_transcript(transcript)
        assert header.get("duration") and header.get("language") == "en" and text
        print("OK: real Gallery/Explore/Transcribe buttons, switch to Small/manual English/TXT/timestamps -> saved metadata", flush=True)

        window.evaluate_js("document.querySelectorAll('#gal-grid .grab')[1].click();")
        until(window, "document.querySelectorAll('#gal-grid .gv')[1]._v.downloaded")
        assert list((folder / "video").glob("*.mp4"))
        assert not window.evaluate_js("window.__errors.length"), window.evaluate_js("window.__errors")
        assert not window.evaluate_js("document.querySelector('#access-open,#access-dialog,#browser')")
        print("OK: real Download file button -> MP4 saved; no login controls, cookies or JS errors", flush=True)
        report = {"passed": True, "real_network_and_asr": True, "profile_model": "qwen3-asr",
                  "profile_transcripts": 2, "gallery_model": api.workshop._engine.name,
                  "gallery_transcripts": 1, "gallery_format": "txt", "gallery_language": "en",
                  "gallery_timestamps": True, "mp4_download": True, "browser_accounts": False,
                  "javascript_errors": 0}
        target = ROOT / "dev/speech-quality/integration/gui-network.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except Exception:
        failed = True
        traceback.print_exc()
        try:
            print(window.evaluate_js("document.querySelector('#logbox').textContent"), flush=True)
        except Exception:
            pass
    finally:
        finished.set()
        window.destroy()


def watchdog():
    if not finished.wait(150):
        print("FAIL: real app timed out", flush=True)
        os._exit(1)


if __name__ == "__main__":
    assert core.model_downloaded(), "Default model must already be cached"
    with tempfile.TemporaryDirectory(prefix="anonymous_app_") as directory, \
         patch("yt_dlp.cookies.extract_cookies_from_browser", side_effect=AssertionError("browser cookies requested")):
        output = Path(directory) / "output"
        output.mkdir()
        app.SETTINGS_FILE = str(Path(directory) / "settings.json")
        api = app.Api()
        api.save_settings({"folder": str(output), "limit": 2, "ui_language": "it", "motion": "off"})
        html = app.read_interface().replace("</head>", "<script>window.__errors=[];addEventListener('error',e=>window.__errors.push(e.message));</script></head>")
        window = webview.create_window("Anonymous real app check", html=html, js_api=api,
                                       width=1100, height=760, frameless=True, easy_drag=False)
        app.window = window
        threading.Thread(target=watchdog, daemon=True).start()
        threading.Thread(target=run, args=(window, output), daemon=True).start()
        webview.start(gui="edgechromium", private_mode=True)
    sys.exit(1 if failed else 0)
