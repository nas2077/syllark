"""Check Nas v2 commands, keyboard tabs, saved motion and window layout."""
import json
import os
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
from screenshots import Api as DemoApi, capture


class Api(DemoApi):
    def __init__(self):
        self.saved = []

    def initial_state(self):
        state = super().initial_state()
        state.update(motion="off", theme="dark")
        return state

    def save_settings(self, values):
        self.saved.append(values)
        return {"ok": True}


CHECK = r"""
window.__designDone=false;window.__designFailure=null;
(async()=>{
  const q=s=>document.querySelector(s), all=s=>[...document.querySelectorAll(s)];
  const wait=ms=>new Promise(r=>setTimeout(r,ms||100));
  const assert=(ok,message)=>{if(!ok)throw Error(message);};
  const key=(el,key,ctrlKey=false)=>el.dispatchEvent(new KeyboardEvent('keydown',
    {key,ctrlKey,bubbles:true,cancelable:true}));
  assert(Nas.configuration().personality==='workshop','incorrect preset');
  assert(q('#sw-motion').checked&&Nas.configuration().motion==='off','saved motion ignored');
  const first=Orbi.instances[0].state().step;
  await wait(350);
  assert(Orbi.instances[0].state().step===first,'Orbi moved with motion off');
  assert(all('[data-n-reveal]').every(el=>getComputedStyle(el).opacity==='1'),'content hidden with motion off');
  Nas.celebrate(q('#go'));assert(!q('.n-confettiItem'),'particles with motion off');
  q('#sw-motion').click();await wait(350);
  assert(Nas.configuration().motion==='quiet'&&Orbi.instances[0].state().step>first,'motion did not resume');

  q('#profile').focus();key(document,'k',true);await wait();
  assert(q('#commands').open&&document.activeElement.id==='commands-search','Ctrl K did not open or focus commands');
  q('#commands-search').value='zzzz';q('#commands-search').dispatchEvent(new Event('input',{bubbles:true}));
  assert(!q('[data-n-empty]').hidden,'missing empty search state');
  q('#commands-search').value='Gallery';q('#commands-search').dispatchEvent(new Event('input',{bubbles:true}));
  assert(all('[data-n-item]:not([hidden])').length===1,'command search not filtering');
  key(q('#commands-search'),'ArrowDown');
  assert(document.activeElement.dataset.commandView==='gallery','arrow navigation failed');
  q('#commands').close();await wait();
  assert(document.activeElement.id==='profile','dialog did not restore focus');
  key(document,'k',true);await wait();
  q('#commands-search').value='Gallery';q('#commands-search').dispatchEvent(new Event('input',{bubbles:true}));
  key(q('#commands-search'),'Enter');await wait(450);
  assert(!q('#commands').open&&q('.view.on').id==='v-gallery','command did not navigate');

  q('[data-view=extract]').click();await wait(450);
  q('#tab-log').focus();key(q('#tab-log'),'ArrowRight');
  assert(q('#tab-err').getAttribute('aria-selected')==='true'&&!q('#errpane').hidden&&
    getComputedStyle(q('#errpane')).display!=='none'&&q('#logbox').hidden,'keyboard did not show error panel');
  key(q('#tab-err'),'Home');
  assert(!q('#logbox').hidden&&q('#errpane').hidden,'Home did not restore details');

  // Opening commands closes pickers and the language popup.
  q('#model-picker').click();key(document,'k',true);await wait();
  assert(q('#commands').open&&!q('#picker-popup'),'picker overlapped commands');
  q('#commands').close();q('#ui-language').click();key(document,'k',true);await wait();
  assert(q('#commands').open&&q('#locale-menu').hidden,'language menu overlapped commands');
  q('#commands').close();

  for(const code of window.APP_LANGUAGES.map(x=>x.code)){
    I18n.change(code);q('#open-commands').click();await wait(30);
    assert(q('#commands-title').textContent===I18n.text('Commands'),'untranslated command title');
    const r=q('#commands').getBoundingClientRect();
    assert(r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight,'command dialog outside window');
    q('#commands').close();
  }
  I18n.change('it');q('[data-view=about]').click();q('#sw-motion').click();await wait();
  assert(Nas.configuration().motion==='off','motion switch failed');
  q('[data-view=extract]').click();await wait(450);
  const frozen=Orbi.instances[0].state().step;await wait(300);
  assert(Orbi.instances[0].state().step===frozen,'view switching restarted frozen Orbi');
  for(const theme of ['light','dark']){
    applyTheme(theme);await wait(350);
    const expected=document.createElement('canvas');expected.width=56;expected.height=46;
    Orbi.draw(expected,{t:0,face:'neutral'});
    assert(q('#orbi').toDataURL()===expected.toDataURL(),'theme change lost the frozen smiling pose');
  }
  assert(!window.__errors.length,window.__errors.join('; '));
})().catch(e=>window.__designFailure=e.stack).finally(()=>window.__designDone=true);void 0;
"""

finished = threading.Event()
failed = False


def watchdog():
    if not finished.wait(60):
        print("FAIL: design checks stopped responding", flush=True)
        os._exit(1)


def run(w, api):
    global failed
    try:
        time.sleep(3)
        w.evaluate_js(CHECK)
        for _ in range(200):
            time.sleep(.1)
            if w.evaluate_js("window.__designDone"):
                break
        assert w.evaluate_js("window.__designDone"), "checks did not finish"
        assert not w.evaluate_js("window.__designFailure"), w.evaluate_js("window.__designFailure")
        assert {"motion": "off"} in api.saved and {"motion": "quiet"} in api.saved
        assert not any("undefined" in value for value in api.saved), api.saved
        print("OK: saved motion, frozen/resumed Orbi, visible content and no particles while motion is off", flush=True)
        print("OK: Ctrl K, filtering, empty results, arrows, Enter, focus restoration and exclusive menus", flush=True)
        print("OK: keyboard details/errors tabs and localized commands in 14 languages at 1000 x 680", flush=True)
        out = ROOT / "dev/shots"
        out.mkdir(exist_ok=True)
        for theme in ("dark", "light"):
            w.evaluate_js("applyTheme(" + json.dumps(theme) + ");document.querySelector('.pane').scrollTop=0;")
            time.sleep(.35)
            capture(w.native.Handle.ToInt64(), str(out / ("nas-v2-" + theme + "-minimum.png")))
            w.evaluate_js("document.querySelector('#open-commands').click();")
            time.sleep(.35)
            capture(w.native.Handle.ToInt64(), str(out / ("nas-v2-" + theme + "-commands.png")))
            w.evaluate_js("document.querySelector('#commands').close();")
    except Exception:
        failed = True
        traceback.print_exc()
    finally:
        finished.set()
        w.destroy()


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as folder:
        original = app.SETTINGS_FILE
        try:
            app.SETTINGS_FILE = str(Path(folder) / "settings.json")
            assert app.Api().save_settings({"motion": "off", "language": "it"})["ok"]
            restored = app.Api()
            assert restored._setting("motion", "quiet") == "off"
            assert restored._setting("language", "auto") == "it"
        finally:
            app.SETTINGS_FILE = original
    print("OK: motion preference survives a new API instance and preserves speech settings", flush=True)
    html = app.read_interface().replace('<script>\n"use strict";',
        '<script>window.__errors=[];window.addEventListener("error",e=>window.__errors.push(e.message));\n"use strict";')
    assert 'src="vendor/' not in html and 'href="vendor/' not in html
    api = Api()
    w = webview.create_window("Nas v2 check", html=html, js_api=api, width=1000, height=680,
                              frameless=True, easy_drag=False)
    threading.Thread(target=watchdog, daemon=True).start()
    threading.Thread(target=run, args=(w, api), daemon=True).start()
    webview.start(gui="edgechromium", private_mode=True)
    sys.exit(1 if failed else 0)
