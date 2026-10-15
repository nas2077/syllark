"""Regression check for pointer events while switching views in WebView2.

The watchdog fails the check even if JavaScript gets stuck in an infinite loop.
Run with dev/.venv/Scripts/python.exe dev/navigation_check.py.
"""
import os
import sys
import threading
import time
import traceback

import webview

HERE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
sys.path.insert(0, HERE)
from app import read_interface


class Api:
    def initial_state(self):
        return {"folder": "C:\\Transcripts", "model": "large-v3-turbo",
                "language": "auto", "format": "md", "theme": "dark",
                "models": [], "languages": [], "gpu": {"ok": False},
                "ui_language": "en",
                "whisper": True, "cpu": 4}

    def check_browsers(self):
        return {"ok": True, "browsers": []}

    def history(self):
        return {"ok": True, "items": []}

    def about(self):
        return {"python": "3.12", "cpu": 4, "transcribers": 2, "threads": 2,
                "downloaders": 3, "device": "processor", "packages": [],
                "models": [], "cache": "C:\\Cache", "app_folder": HERE}

    def window_state(self):
        return {"maximized": False}


finished = threading.Event()
failed = False
phase = "startup"


def watchdog():
    if not finished.wait(30):
        print(f"FAIL: JavaScript stopped responding during {phase}", flush=True)
        os._exit(1)


def run(w):
    global failed, phase
    try:
        time.sleep(2)
        phase = "hidden canvas pointer events"
        # Deterministic reproduction: a move arrives after display:none,
        # before IntersectionObserver can stop Orbi's next simulation step.
        assert w.evaluate_js("""(() => {
          document.querySelector('[data-view=gallery]').click();
          const c=document.querySelector('#orbi');
          if(c.getBoundingClientRect().width!==0) throw Error('canvas is still visible');
          for(let i=0;i<100;i++) window.dispatchEvent(new PointerEvent('pointermove',
            {clientX:480+i,clientY:45,pointerType:'mouse'}));
          c.dispatchEvent(new PointerEvent('pointerdown',
            {clientX:500,clientY:45,pointerType:'mouse',button:0}));
          Orbi.instances[0].stepFrames(1);
          document.querySelector('[data-view=extract]').click();
          Orbi.instances[0].stepFrames(1);
          return true;
        })()""")
        print("OK: hidden canvas pointer events do not block JavaScript", flush=True)

        phase = "large and non-finite pointer coordinates"
        assert w.evaluate_js("""(() => {
          for(const x of [1e20,-1e20,Infinity,-Infinity,NaN]) {
            const e=new PointerEvent('pointermove',{clientY:45,pointerType:'mouse'});
            Object.defineProperty(e,'clientX',{value:x});
            window.dispatchEvent(e);
            Orbi.instances[0].stepFrames(1);
          }
          return Orbi.instances[0].state().gaze.every(Number.isFinite);
        })()""")
        print("OK: out-of-range coordinates do not block hit testing", flush=True)

        phase = "visible canvas interaction"
        assert w.evaluate_js("""(() => {
          const o=Orbi.instances[0], c=document.querySelector('#orbi');
          o.stepFrames(50);
          const r=c.getBoundingClientRect(), x=r.left+r.width/2, y=r.top+r.height/2;
          window.dispatchEvent(new PointerEvent('pointermove',
            {clientX:x,clientY:y,pointerType:'mouse'}));
          o.stepFrames(1);
          if(!o.state().hovered) return false;
          c.dispatchEvent(new PointerEvent('pointerdown',
            {clientX:x,clientY:y,pointerType:'mouse',button:0,pointerId:1}));
          o.stepFrames(1);
          window.dispatchEvent(new PointerEvent('pointermove',
            {clientX:x+20,clientY:y,pointerType:'mouse',buttons:1}));
          o.stepFrames(1);
          const grabbed=o.state().mood==='held';
          window.dispatchEvent(new PointerEvent('pointerup',{pointerType:'mouse'}));
          o.stepFrames(1);
          return grabbed;
        })()""")
        print("OK: visible Orbi still responds to hover and dragging", flush=True)

        phase = "rapid navigation with pointer events"
        w.evaluate_js("""window.__navigationDone=false;
          (async () => {
            const views=['gallery','history','about','extract'];
            for(let i=0;i<240;i++) {
              document.querySelector('[data-view='+views[i%4]+']').click();
              window.dispatchEvent(new PointerEvent('pointermove',
                {clientX:400+i%200,clientY:45,pointerType:'mouse'}));
              await new Promise(resolve=>setTimeout(resolve,5));
            }
            document.querySelector('[data-view=extract]').click();
            window.__navigationDone=true;
          })(); void 0;""")
        for _ in range(100):
            time.sleep(0.05)
            if w.evaluate_js("window.__navigationDone"):
                break
        assert w.evaluate_js("window.__navigationDone"), "navigation did not finish"
        first = w.evaluate_js("Orbi.instances[0].state().step")
        time.sleep(0.5)
        assert w.evaluate_js("Orbi.instances[0].state().step") > first, "Orbi did not resume"
        assert w.evaluate_js("document.querySelector('.view.on').id") == "v-extract"
        assert not w.evaluate_js("window.__errors"), "JavaScript reported errors"
        print("OK: 240 rapid view switches; Orbi resumes and the page responds", flush=True)
    except Exception:
        failed = True
        traceback.print_exc()
    finally:
        finished.set()
        w.destroy()


html = read_interface().replace(
    '<script>\n"use strict";',
    '<script>window.__errors=[];window.addEventListener("error",e=>window.__errors.push(e.message));\n"use strict";')
w = webview.create_window("Navigation regression check", html=html, js_api=Api(),
                          width=1280, height=860)
threading.Thread(target=watchdog, daemon=True).start()
threading.Thread(target=run, args=(w,), daemon=True).start()
webview.start(gui="edgechromium", debug=False, private_mode=True)
sys.exit(1 if failed else 0)
