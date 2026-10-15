"""Real WebView2 check: paste a link and transcribe, with no access setup."""
import json
import os
import sys
import threading
import time
import traceback
from pathlib import Path

import webview
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import app
from screenshots import Api as DemoApi, capture


class Api(DemoApi):
    def __init__(self):
        self.started, self.explored = [], []
    def initial_state(self):
        state = super().initial_state()
        state.update(browser="firefox", ui_language="it", theme="dark", motion="off")
        return state
    def start(self, options):
        self.started.append(options)
        return {"ok": True}
    def explore(self, profile, limit=None):
        self.explored.append(profile)
        return {"ok": True}
    def save_settings(self, values):
        assert "browser" not in values
        return {"ok": True}


failed = False
finished = threading.Event()


def run(window, api):
    global failed
    try:
        time.sleep(2.5)
        forbidden = "#access-open,#access-dialog,#access-public,#ck-recheck,#browser,#info-access,#gal-access"
        assert window.evaluate_js("document.querySelectorAll(" + json.dumps(forbidden) + ").length") == 0
        assert window.evaluate_js("!document.querySelector('#go').disabled")
        print("OK: no login, cookies, browser picker or access dialog; ready immediately", flush=True)
        link = "https://www.tiktok.com/@sample/video/7300000000000000001"
        window.evaluate_js("document.querySelector('#profile').value=" + json.dumps(link) + ";document.querySelector('#go').click()")
        time.sleep(.25)
        assert len(api.started) == 1 and api.started[0]["profile"] == link
        assert "browser" not in api.started[0]
        window.evaluate_js("window.receiveEvents([{type:'profile',handle:'sample',total:1},{type:'video',id:'1',state:'queued',index:0,title:'Example'},{type:'video',id:'1',state:'done',words:20},{type:'finished',ok:1,errors:0,skipped:0}]);")
        time.sleep(.2)
        assert window.evaluate_js("!S.active && !document.querySelector('#go').disabled")
        print("OK: one click starts the link, no authentication parameters; completion restores the form", flush=True)
        window.evaluate_js("document.querySelector('[data-view=gallery]').click();document.querySelector('#gal-profile').value='@sample';document.querySelector('#gal-go').click();")
        time.sleep(.2)
        assert api.explored == ["@sample"]
        window.evaluate_js("window.receiveEvents([{type:'gal_start',handle:'sample',folder:'x'},{type:'gal_done',total:0}]);")
        for language in json.loads((ROOT / "src/locales/languages.json").read_text(encoding="utf-8")):
            code = language["code"]
            for theme in ("dark", "light"):
                window.evaluate_js("I18n.change(" + json.dumps(code) + ");applyTheme(" + json.dumps(theme) + ");document.querySelector('[data-view=extract]').click();document.querySelector('.pane').scrollTop=0;")
                time.sleep(.03)
                assert not window.evaluate_js("document.querySelector('.content').scrollWidth>document.querySelector('.pane').clientWidth"), (code, theme)
                if code == "it":
                    time.sleep(.12)
                    capture(window.native.Handle.ToInt64(), str(ROOT / "dev/shots" / ("anonymous-" + theme + ".png")))
        assert not window.evaluate_js("window.__errors.length"), window.evaluate_js("window.__errors")
        print("OK: gallery is direct too; 14 languages, both themes, RTL and minimum window size", flush=True)
    except Exception:
        failed = True
        traceback.print_exc()
    finally:
        finished.set()
        window.destroy()


def watchdog():
    if not finished.wait(55):
        print("FAIL: anonymous UI stopped responding", flush=True)
        os._exit(1)


if __name__ == "__main__":
    html = app.read_interface().replace("</head>", "<script>window.__errors=[];addEventListener('error',e=>window.__errors.push(e.message));</script></head>")
    api = Api()
    window = webview.create_window("Anonymous check", html=html, js_api=api, width=1000, height=680, frameless=True, easy_drag=False)
    threading.Thread(target=watchdog, daemon=True).start()
    threading.Thread(target=run, args=(window, api), daemon=True).start()
    webview.start(gui="edgechromium", private_mode=True)
    sys.exit(1 if failed else 0)
