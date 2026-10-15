"""Catalog, export, persistence, layout and live language-switch checks."""
import json
import os
import re
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path

import webview

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import app
import tiktok_core as core
from localization import catalogs, translate
from screenshots import Api as DemoApi, capture

catalog = catalogs()
keys = set(catalog["en"])
for code, values in catalog.items():
    assert set(values) == keys, (code, "missing or extra catalog entries")
    for key, value in values.items():
        assert value or not key, (code, key, "empty translation")
        assert sorted(re.findall(r"\{\w+\}", key)) == sorted(re.findall(r"\{\w+\}", value)), (code, key)
print(f"OK: {len(catalog)} complete catalogs, {len(keys)} entries each", flush=True)

with tempfile.TemporaryDirectory() as folder:
    rows = []
    for i, code in enumerate(catalog):
        video = {"id": str(7000000000000000000 + i), "title": "Original video title",
                 "url": "https://www.tiktok.com/@sample/video/123", "duration": 30,
                 "timestamp": 1750000000}
        row = core.write_transcript(folder, video, {}, [{"text": "Original spoken words", "start": 0}],
                                    {"language": "en", "confidence": 0.9}, ui_language=code)
        header, body = core._read_transcript(row["path"])
        assert body == "Original spoken words"
        assert header["language"] == "en" and header["duration"] == "30"
        assert header["url"] == video["url"] and header["date"] == core._date(video["timestamp"])
        rows.append(row)
        for fmt in ("md", "txt"):
            silent = core.compose(video, {}, [], {}, fmt=fmt, ui_language=code)
            path = Path(folder) / ("silence." + fmt)
            path.write_text(silent, encoding="utf-8")
            assert core._read_transcript(path)[1] == "", (code, fmt)
    assert core.rebuild_collection(folder, "sample", rows, "it") == len(catalog)
    summary = (Path(folder) / "_ALL @sample.md").read_text(encoding="utf-8")
    assert summary.count("Original spoken words") == len(catalog)
print("OK: localized exports read back correctly; mixed-language collections retain all transcripts", flush=True)

with tempfile.TemporaryDirectory() as folder:
    old_settings = app.SETTINGS_FILE
    app.SETTINGS_FILE = str(Path(folder) / "settings.json")
    api = app.Api()
    api.save_settings({"language": "it"})
    workers = [threading.Thread(target=api.save_settings, args=({"ui_language": code},)) for code in catalog]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    saved = json.loads(Path(app.SETTINGS_FILE).read_text(encoding="utf-8"))
    assert saved["ui_language"] in catalog and saved["language"] == "it"
    restored = app.Api()
    assert restored._ui_language() == saved["ui_language"]
    app.SETTINGS_FILE = old_settings
print("OK: concurrent language saves persist correctly and preserve the speech language", flush=True)


class Api(DemoApi):
    def __init__(self):
        self.saved = []

    def save_settings(self, data):
        self.saved.append(data)
        return {"ok": True}


finished = threading.Event()
failed = False
phase = "startup"
out = ROOT / "dev" / "shots"
out.mkdir(exist_ok=True)


def watchdog():
    if not finished.wait(90):
        print("FAIL: window stopped responding during " + phase, flush=True)
        os._exit(1)


def run(w, api):
    global failed, phase
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not w.evaluate_js("document.querySelector('#language').options.length>0 && document.querySelector('#model-picker')"):
            time.sleep(.1)
        assert w.evaluate_js("document.querySelector('#language').options.length>0"), "interface did not initialize"
        w.evaluate_js("""
          document.querySelector('#profile').value='@sample';
          document.querySelector('#language').value='it';
          window.receiveEvents([{type:'profile',handle:'sample',total:2},
            {type:'video',id:'1',index:0,state:'queued',title:'Original video title'},
            {type:'video',id:'2',index:1,state:'queued',title:'Second original title'}]);
          window.receiveEvents([{type:'video',id:'1',state:'done',words:20,language:'it',file:'x'},
            {type:'log',text:'ready. 12 cores available.',level:'info'},
            {type:'gal_start',handle:'sample',folder:'x'},
            {type:'gal_batch',total:1,videos:[{id:'3',title:'Original gallery title',timestamp:1750000000,views:12000,likes:42}]}]);
          busyMode();
        """)
        time.sleep(0.2)
        expected = "Paste a profile and get every video back as text, transcribed on this computer."
        for code in catalog:
            phase = code + " language switch"
            state = w.evaluate_js("""(() => {
              document.querySelector('#ui-language').click();
              document.querySelector('[data-locale=%s]').click();
              return {lang:document.documentElement.lang,dir:document.documentElement.dir,
                hero:document.querySelector('.hero .n-subtitle').textContent,
                title:document.querySelector('[data-id="1"] .t').textContent,
                galleryTitle:document.querySelector('#gal-grid .t').textContent,
                speech:document.querySelector('#language').value,
                active:S.active,bar:document.querySelector('#bar').children.length,
                open:document.querySelector('#ui-language').getAttribute('aria-expanded')};
            })()""" % json.dumps(code))
            assert state["lang"] == code and state["hero"] == catalog[code][expected], (code, state)
            assert state["dir"] == ("rtl" if code == "ar" else "ltr")
            assert state["title"] == "Original video title" and state["galleryTitle"] == "Original gallery title"
            assert state["speech"] == "it" and state["active"] and state["bar"] == 12, state
            assert state["open"] == "false"
            time.sleep(0.03)
            assert {"ui_language": code} in api.saved, (code, "preference not saved")
            assert not any("language" in s for s in api.saved), "speech language changed"
            w.evaluate_js("window.receiveEvents([{type:'gallery',id:'3',state:'downloading',pct:45}]);")
            percent = w.evaluate_js("document.querySelector('#gal-grid .work-text').textContent")
            assert percent != "Downloading 45%" or code == "en", (code, percent)
            for view in ("extract", "gallery", "history", "about"):
                w.evaluate_js("document.querySelector('[data-view=%s]').click()" % json.dumps(view))
                time.sleep(0.06)
                layout = w.evaluate_js("""(() => {
                  const buttons=[...document.querySelectorAll('.toolbar button')];
                  return {overflow:document.querySelector('.content').scrollWidth>document.querySelector('.pane').clientWidth,
                    clipped:buttons.some(b=>b.scrollWidth>b.clientWidth+1),
                    overlap:document.querySelector('.views').getBoundingClientRect().right>
                      document.querySelector('.right').getBoundingClientRect().left};
                })()""")
                assert not any(layout.values()), (code, view, layout)
            if code in {"it", "de", "ar", "zh-Hans", "ja", "hi"}:
                w.evaluate_js("document.querySelector('[data-view=extract]').click();document.querySelector('#ui-language').click();")
                time.sleep(0.08)
                capture(w.native.Handle.ToInt64(), str(out / ("language-" + code + ".png")))
                w.evaluate_js("closeLanguageMenu();")
            print("OK: " + code + " live switch, saved preference, active work and four views", flush=True)
        phase = "keyboard and rapid language switches"
        w.evaluate_js("document.querySelector('#ui-language').click();document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}));")
        assert w.evaluate_js("document.querySelector('#locale-menu').hidden && document.activeElement.id==='ui-language'")
        for _ in range(5):
            for code in catalog:
                w.evaluate_js("I18n.change(%s);" % json.dumps(code))
        w.evaluate_js("document.querySelector('[data-view=extract]').click();I18n.change('en');")
        first = w.evaluate_js("Orbi.instances[0].state().step")
        time.sleep(0.4)
        assert w.evaluate_js("Orbi.instances[0].state().step") > first
        assert not w.evaluate_js("window.__errors"), w.evaluate_js("window.__errors")
        print("OK: keyboard dismissal, 70 rapid language switches and resumed Orbi animation", flush=True)
        phase = "minimum window size and light theme"
        w.resize(1000,680)
        w.evaluate_js("applyTheme('light');")
        time.sleep(0.2)
        for code in catalog:
            w.evaluate_js("I18n.change(%s);" % json.dumps(code))
            for view in ("extract", "gallery", "history", "about"):
                w.evaluate_js("document.querySelector('[data-view=%s]').click()" % json.dumps(view))
                time.sleep(0.03)
                assert not w.evaluate_js("""(() => {
                  const nav=document.querySelector('.views').getBoundingClientRect();
                  const controls=document.querySelector('.right').getBoundingClientRect();
                  const brand=document.querySelector('.brand').getBoundingClientRect();
                  return nav.left<brand.right-1 || nav.right>controls.left ||
                    document.querySelector('.content').scrollWidth>document.querySelector('.pane').clientWidth;
                })()"""), (code,view,"overflow at minimum window size")
        w.evaluate_js("I18n.change('it');document.querySelector('[data-view=extract]').click();document.querySelector('#ui-language').click();")
        time.sleep(0.1)
        capture(w.native.Handle.ToInt64(),str(out / "language-light-minimum.png"))
        print("OK: all 14 languages fit four views at 1000 x 680 in the light theme", flush=True)
    except Exception:
        failed = True
        traceback.print_exc()
    finally:
        finished.set()
        w.destroy()


html = app.read_interface().replace('<script>\n"use strict";',
    '<script>window.__errors=[];window.addEventListener("error",e=>window.__errors.push(e.message));\n"use strict";')
api = Api()
w = webview.create_window("Localization check", html=html, js_api=api, width=1280, height=860,
                          frameless=True, easy_drag=False)
threading.Thread(target=watchdog, daemon=True).start()
threading.Thread(target=run, args=(w, api), daemon=True).start()
webview.start(gui="edgechromium", private_mode=True)
sys.exit(1 if failed else 0)
