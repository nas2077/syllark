"""
interface check: opens the real page, fires fake events into it and measures
the dom. it also holds the page to the Nas design system: six colours and no
more, Inter, Orbi alive at a whole scale, no icons inside buttons, nothing in
capitals, both themes readable.

    python dev/ui_check.py
"""
import json
import os
import sys
import threading
import time

import webview

# the project root: these checks live in dev/, the app one level up
HERE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
sys.path.insert(0, HERE)
from app import read_interface  # noqa: E402
import tiktok_core as core

results = []
saved, stops, links = [], [], []

# the palette of the design system, plus the two shadow tones and the veil
# over the cover photos. any other colour on screen is a mistake
PALETTE = {
    "rgb(27, 38, 50)", "rgb(44, 59, 77)", "rgb(238, 233, 223)", "rgb(201, 193, 177)",
    "rgb(163, 81, 57)", "rgb(255, 177, 98)", "rgb(17, 25, 34)", "rgb(110, 52, 36)",
    "rgba(17, 25, 34, 0.8)",
}


class Api:
    def initial_state(self):
        return {
            "folder": r"C:\Users\someone\Documents\TikTok Transcripts",
            "model": "large-v3-turbo", "language": "auto", "format": "md",
            "timestamps": False, "resume": True, "limit": None,
            "theme": "dark",
            "ui_language": "en",
            "models": [{"id": key, **value, "downloaded": key == core.DEFAULT_MODEL}
                       for key, value in core.MODELS.items()],
            "gpu": {"ok": True, "why": "gpu ready"},
            "languages": [{"id": "auto", "name": "detect from the video"},
                          {"id": "it", "name": "italian"}, {"id": "en", "name": "english"}],
            "whisper": True, "cpu": 12,
        }

    def history(self):
        return {"ok": True, "base": "x", "items": [
            {"handle": "@marcomontemagno", "videos": 212, "size": 1_500_000,
             "when": "2026-08-04 07:12", "ts": 1, "path": "x"},
            {"handle": "@zachking", "videos": 10, "size": 42_000,
             "when": "2026-08-03 19:40", "ts": 0, "path": "y"},
        ]}

    def about(self):
        return {"python": "3.12.10", "cpu": 12, "transcribers": 4, "threads": 3,
                "downloaders": 4, "device": "graphics card",
                "packages": [{"name": "yt-dlp", "v": "2026.7.4"}, {"name": "curl_cffi", "v": "0.15.0"}],
                "models": [{"id": "large-v3-turbo", "label": "large-v3 turbo", "downloaded": True,
                            "size": 1_600_000_000, "selected": True},
                           {"id": "large-v3", "label": "large-v3", "downloaded": False,
                            "size": 0, "selected": False}],
                "cache": r"C:\cache", "app_folder": HERE, "data_folder": HERE}

    def explore(self, profile, limit=None): return {"ok": True}
    def stop_explore(self): return {"ok": True}
    def cancel_one(self, i): return {"ok": True}
    def download_mp4(self, v): return {"ok": True}
    def transcribe_one(self, v): return {"ok": True}
    def open_file(self, p): return {"ok": True}

    def save_settings(self, d):
        saved.append(d)
        return {"ok": True}

    def start(self, o): return {"ok": True}

    def stop(self):
        stops.append(1)
        return {"ok": True}

    def pick_folder(self, current=None): return None
    def open_folder(self, p): return {"ok": True}

    def open_link(self, u):
        links.append(u)
        return {"ok": True}

    def minimize(self): return {"ok": True}
    def maximize(self): return {"ok": True, "maximized": False}
    def window_state(self): return {"maximized": False}
    def close(self): return {"ok": True}


def js(w, c):
    return w.evaluate_js(c)


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))


CONTRAST = """(() => {
  const lum=(c)=>{const [r,g,b]=c.match(/[\\d.]+/g).slice(0,3).map(Number).map(v=>{
    v/=255; return v<=.03928? v/12.92 : Math.pow((v+.055)/1.055,2.4);});
    return .2126*r+.7152*g+.0722*b;};
  const ratio=(a,b)=>{const x=lum(a),y=lum(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);};
  const bg=getComputedStyle(document.body).backgroundColor;
  const sel=(q)=>getComputedStyle(document.querySelector(q)).color;
  return {bg,
    text: Math.round(ratio(sel('#handle'),bg)*10)/10,
    second: Math.round(ratio(sel('.n-small'),bg)*10)/10,
    action: Math.round(ratio(getComputedStyle(document.querySelector('#go')).color,
                             getComputedStyle(document.querySelector('#go')).backgroundColor)*10)/10};
})()"""

COLOURS = """(() => {
  const seen=new Set();
  for (const el of document.querySelectorAll('body *')){
    if (el.closest('svg,canvas,img') || el.offsetParent===null) continue;
    const s=getComputedStyle(el);
    for (const c of [s.color, s.backgroundColor])
      if (c && c!=='rgba(0, 0, 0, 0)') seen.add(c);
  }
  return [...seen];
})()"""


def run(w):
    time.sleep(3.2)

    err = js(w, "window.__errors ? window.__errors.join(' | ') : ''")
    check("no javascript error", not err, err or "")

    # ---------------------------------------------------------- Orbi
    first = js(w, "Orbi.instances.length ? Orbi.instances[0].state().step : -1")
    time.sleep(1.0)
    orbi = js(w, """(() => {const c=document.querySelector('#orbi');
      return {n:Orbi.instances.length, step:Orbi.instances[0].state().step,
              scale:Number(c.dataset.scale), w:parseFloat(c.style.width),
              dpr:window.devicePixelRatio};})()""")
    check("Orbi is alive, one of him", orbi["n"] == 1 and orbi["step"] > first, str(orbi))
    check("Orbi at a whole scale",
          orbi["scale"] >= 2 and abs(orbi["w"] * orbi["dpr"] - 56 * orbi["scale"]) < 0.5, str(orbi))
    faces = js(w, """[...document.querySelectorAll('canvas.face[data-face]')].map(c=>{
      const d=c.getContext('2d').getImageData(0,0,56,46).data; let n=0;
      for(let i=3;i<d.length;i+=4) if(d[i]) n++; return n;})""")
    check("the still faces are drawn by the engine", faces and all(n > 300 for n in faces), str(faces))

    # ---------------------------------------------------------- startup
    check("all simple model choices in the menu", js(w, "document.querySelectorAll('#model option').length") == len(core.MODELS))
    check("the saved model is selected", js(w, "document.querySelector('#model').value") == "large-v3-turbo")
    check("model name, size and automatic download are explained",
          "Whisper large-v3 turbo" in (js(w, "document.querySelector('#model-note').textContent") or "")
          and "Downloads automatically" in (js(w, "document.querySelector('.model-explanation').textContent") or ""))
    check("gpu label", js(w, "document.querySelector('#engine-device').textContent") == "GPU")
    check("languages loaded", js(w, "document.querySelectorAll('#language option').length") >= 3)
    check("folder shown", bool(js(w, "document.querySelector('#folder').value")))
    check("no access options or browser setup", js(w, "document.querySelectorAll('#access-open,#browser,#access-dialog,#ck-recheck').length") == 0)
    check("one direct transcription action", js(w, "!document.querySelector('#go').disabled"))
    check("resume switch on, times switch off",
          js(w, "document.querySelector('#sw-resume').checked") is True
          and js(w, "document.querySelector('#sw-times').checked") is False)

    # the switch knob really travels: 22px to the right when on
    js(w, "document.querySelector('#sw-times').click()")
    time.sleep(0.5)
    knob = js(w, "getComputedStyle(document.querySelector('#sw-times + .n-switch__track'),'::after').transform")
    check("a switch turned on moves its knob", knob and "22" in knob, knob)
    check("the twin switch in the gallery follows", js(w, "document.querySelector('#g-times').checked") is True)
    check("and the setting is saved", {"timestamps": True} in saved, str(saved[-3:]))
    js(w, "document.querySelector('#sw-times').click()")

    saved.clear()
    js(w, "const l=document.querySelector('#language'); l.value='en'; l.dispatchEvent(new Event('change'))")
    js(w, "const m=document.querySelector('#model'); m.value='large-v3'; m.dispatchEvent(new Event('change'))")
    js(w, "const m=document.querySelector('#model'); m.value='large-v3-turbo'; m.dispatchEvent(new Event('change'))")
    time.sleep(0.4)
    check("language and model are saved on change",
          {"language": "en"} in saved and {"whisper_model": "large-v3"} in saved, str(saved))

    check("empty state visible", "gone" not in (js(w, "document.querySelector('#empty').className") or ""))
    check("history count in the bar", js(w, "document.querySelector('#n-history').textContent") == "2")
    ow = js(w, "document.documentElement.scrollWidth - document.documentElement.clientWidth")
    check("no horizontal scroll", ow <= 0, f"{ow}px over")

    # ---------------------------------------------------------- the design system
    check("Inter is the typeface", "Inter" in js(w, "getComputedStyle(document.body).fontFamily"))
    check("dark theme: the page is blue night",
          js(w, "getComputedStyle(document.body).backgroundColor") == "rgb(27, 38, 50)")
    icons = js(w, """[...document.querySelectorAll('button svg')].filter(s=>
      !s.closest('.n-button-theme') && !s.closest('.window-buttons')).length""")
    check("no icons inside buttons", icons == 0, f"{icons}")
    caps = js(w, """[...document.querySelectorAll('*')].filter(e=>
      getComputedStyle(e).textTransform==='uppercase').length""")
    check("nothing in capitals", caps == 0, f"{caps}")
    moon = js(w, """[...document.querySelectorAll('#theme svg')].filter(s=>
      getComputedStyle(s).display!=='none').length""")
    check("the theme button shows one picture", moon == 1, f"{moon} shown")

    # ---------------------------------------------------------- 212 videos
    js(w, "window.receiveEvents([{type:'profile', handle:'marcomontemagno', total:null}])")
    time.sleep(0.2)
    check("while the list streams in, no made-up total",
          "reading" in (js(w, "document.querySelector('#p-of').textContent") or ""),
          js(w, "document.querySelector('#p-of').textContent"))
    js(w, "window.receiveEvents([{type:'progress', done:0, ok:0, errors:0, skipped:0,"
          " running:0, queued:40, total:40, listing:true}])")
    time.sleep(0.2)
    check("the total shows it is still growing",
          "40+" in (js(w, "document.querySelector('#facts').textContent") or "")
          and "found so far" in (js(w, "document.querySelector('#p-of').textContent") or ""),
          js(w, "document.querySelector('#facts').textContent"))
    js(w, """
      window.receiveEvents([{type:'profile', handle:'marcomontemagno', total:212}]);
      const t = ['how i made 3 million with a newsletter','the truth about personal branding',
                 'why 90% of startups die','3 books that changed how i think',
                 'answering your questions about remote work'];
      const p = [];
      for (let i=0;i<212;i++) p.push({type:'video', id:'v'+i, index:i, state:'queued',
                                      title:t[i%5], duration:20+(i%70),
                                      url:'https://www.tiktok.com/@marcomontemagno/video/v'+i});
      window.receiveEvents(p);
    """)
    time.sleep(0.5)
    check("212 rows created", js(w, "document.querySelectorAll('.row').length") == 212)
    check("empty state gone", "gone" in (js(w, "document.querySelector('#empty').className") or ""))
    check("handle shown", js(w, "document.querySelector('#handle').textContent") == "@marcomontemagno")
    check("progress section appeared", js(w, "document.querySelector('#card-progress').hidden") is False)

    ms = js(w, """(() => {
      const t0 = performance.now();
      const p = [];
      for (let i=0;i<212;i++) p.push({type:'video', id:'v'+i, state: i%17===0?'error':'done',
                                      words:40+i%90, language:'en', message:'download failed'});
      p.push({type:'progress', done:212, ok:200, errors:12, skipped:0, total:212, eta:0});
      window.receiveEvents(p);
      return performance.now() - t0;
    })()""")
    check("updating 212 rows under 400ms", ms < 400, f"{ms:.0f}ms")
    time.sleep(0.3)   # the error panel fills on the next frame, by design
    check("done counter", js(w, "document.querySelector('#s-ok').textContent") == "200")
    check("error counter", js(w, "document.querySelector('#s-err').textContent") == "12")
    check("errors collected in the panel",
          js(w, "document.querySelectorAll('#errpane .item').length") == 13,
          js(w, "document.querySelector('#n-err').textContent"))
    full = js(w, "document.querySelectorAll('#bar > span.full').length")
    check("the twelve squares fill when everything is through", full == 12, f"{full}/12")
    js(w, "window.receiveEvents([{type:'progress', done:53, ok:50, errors:3, skipped:0, total:212}])")
    time.sleep(0.1)
    part = js(w, "document.querySelectorAll('#bar > span.full').length")
    check("a quarter of the way is three squares", part == 3, f"{part}/12")

    jitter = js(w, """(() => {
      const r=document.querySelector('[data-id=v1]'), p=r.querySelector('.badge');
      const h1=r.getBoundingClientRect().height;
      const s=r.dataset.s, t=p.textContent;
      r.dataset.s='downloading'; p.textContent='Downloading';
      const h2=r.getBoundingClientRect().height;
      r.dataset.s=s; p.textContent=t;
      return Math.abs(h1-h2);
    })()""")
    check("the row height never changes", jitter < 0.5, f"{jitter:.1f}px")

    js(w, "window.receiveEvents([{type:'video',id:'v5',state:'downloading'},{type:'percent',id:'v5',pct:64}])")
    time.sleep(0.35)
    mb = js(w, """(() => {
      const r=document.querySelector('[data-id=v5]');
      const b=r.querySelector('.minibar'), i=r.querySelector('.minibar > i');
      return {visible:getComputedStyle(b).display!=='none', width:i.style.width};
    })()""")
    check("the download of one row shows and tells the truth",
          mb["visible"] and mb["width"] == "64%", str(mb))

    js(w, "document.querySelector('.filter[data-f=error]').click()")
    time.sleep(0.25)
    v = js(w, "[...document.querySelectorAll('.row')].filter(r=>!r.classList.contains('hidden')).length")
    check("error filter", v == 13, f"{v} visible")
    js(w, "document.querySelector('.filter[data-f=all]').click()")
    js(w, "const c=document.querySelector('#search'); c.value='newsletter'; c.dispatchEvent(new Event('input'))")
    time.sleep(0.3)
    v = js(w, "[...document.querySelectorAll('.row')].filter(r=>!r.classList.contains('hidden')).length")
    check("search by caption", 40 <= v <= 45, f"{v} hits out of 212")
    js(w, "const c=document.querySelector('#search'); c.value=''; c.dispatchEvent(new Event('input'))")

    js(w, """document.querySelector('[data-id=v3] .t').textContent =
        'an absurdly long caption of the kind people write all the time because they stuff whole poems in there with hashtags everywhere and emoji all over the place';""")
    time.sleep(0.2)
    over = js(w, "(()=>{const r=document.querySelector('[data-id=v3]');return r.scrollWidth>r.clientWidth+1})()")
    check("a very long title does not break the row", not over)
    ow2 = js(w, "document.documentElement.scrollWidth - document.documentElement.clientWidth")
    check("no horizontal scroll with real data", ow2 <= 0, f"{ow2}px over")

    links.clear()
    js(w, "document.querySelector('[data-id=v8] .rowbtn').click()")
    time.sleep(0.3)
    check("the row opens the real link of the video",
          links == ["https://www.tiktok.com/@marcomontemagno/video/v8"], str(links))

    stops.clear()
    js(w, "document.querySelector('#profile').value='@x'; document.querySelector('#go').click()")
    time.sleep(0.3)
    check("while it works, stop takes the place of transcribe",
          js(w, "document.querySelector('#go').hidden && !document.querySelector('#stop').hidden"))
    js(w, "document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}))")
    time.sleep(0.2)
    check("escape does not stop a running extraction", not stops, f"{len(stops)} stops")
    js(w, "window.receiveEvents([{type:'finished', ok:1, errors:0, skipped:0, folder:'x'}])")
    time.sleep(0.2)
    check("and transcribe comes back at the end", js(w, "!document.querySelector('#go').hidden"))

    js(w, "window.receiveEvents([{type:'video', id:'v9', state:'done', words:null},"
          "{type:'progress'}, {type:'video', id:'v10', state:'done', words:5, language:'en'}])")
    time.sleep(0.3)
    check("an odd event does not swallow the rest of its packet",
          js(w, "document.querySelector('[data-id=v10]').dataset.s") == "done")

    js(w, "document.querySelector('.tab[data-tab=err]').click()")
    time.sleep(0.25)
    check("the errors tab opens",
          js(w, "getComputedStyle(document.querySelector('#errpane')).display") != "none")
    js(w, "document.querySelector('.tab[data-tab=log]').click()")

    contrast = js(w, CONTRAST)
    check("dark: text, secondary text and the action button readable",
          contrast["text"] >= 12 and contrast["second"] >= 8 and contrast["action"] >= 4.5, str(contrast))
    colours = set(js(w, COLOURS))
    check("dark: six colours and no more", colours <= PALETTE, str(sorted(colours - PALETTE)))

    # ---------------------------------------------------------- gallery
    js(w, "document.querySelector('.views button[data-view=gallery]').click()")
    time.sleep(0.3)
    check("the gallery view opens",
          js(w, "getComputedStyle(document.querySelector('#v-gallery')).display") != "none")
    js(w, "document.querySelector('#gal-profile').value='@marcomontemagno';"
          "document.querySelector('#gal-how-many').value='30';"
          "document.querySelector('#gal-go').click()")
    time.sleep(0.6)
    check("the loading row appears", "on" in (js(w, "document.querySelector('#gal-load').className") or ""))
    check("with a known total, the squares show", js(w, "document.querySelector('#gal-bar').hidden") is False)

    js(w, """
      window.receiveEvents([{type:'gal_start', handle:'marcomontemagno', folder:'x'}]);
      const make = (from, to) => ({type:'gal_batch', total:to, videos:
        Array.from({length:to-from}, (_,k) => { const i=from+k; return {
          id:'v'+i, title:'video number '+i+' with a realistic caption',
          duration:20+i%70, timestamp:1784640903-i*86400, cover:null,
          views:1000*(i+3), likes:100*(i+1), done:i%4===0,
          file:i%4===0?'f':null, downloaded:false, video_file:null,
          url:'https://www.tiktok.com/@x/video/v'+i};})});
      window.receiveEvents([make(0,12)]);
      window.receiveEvents([make(12,24)]);
      window.receiveEvents([make(24,30)]);
    """)
    time.sleep(0.6)
    check("the squares fill as they arrive",
          js(w, "document.querySelectorAll('#gal-bar > span.full').length") == 12)
    js(w, "window.receiveEvents([{type:'gal_done', total:30, stopped:false}])")
    time.sleep(0.6)
    check("the loading row goes away", "on" not in (js(w, "document.querySelector('#gal-load').className") or ""))
    check("30 cards in the grid", js(w, "document.querySelectorAll('#gal-grid .gv').length") == 30)
    check("the already transcribed ones are marked",
          js(w, "document.querySelectorAll('#gal-grid .gv[data-f=\"1\"]').length") == 8)
    grey = js(w, """(() => {
      const c=document.querySelector('#gal-grid .gv[data-f="1"]');
      return {mark:getComputedStyle(c.querySelector('.mark')).display,
              meta:getComputedStyle(c.querySelector('.meta')).opacity};
    })()""")
    check("a transcribed card has the mark and is dimmed",
          grey["mark"] != "none" and float(grey["meta"]) < 0.7, str(grey))
    check("every card has the three buttons",
          js(w, "document.querySelectorAll('#gal-grid .gv:first-child .over .n-button').length") == 3)
    check("the buttons stay hidden until you hover",
          float(js(w, "getComputedStyle(document.querySelector('#gal-grid .gv .over')).opacity")) == 0)

    js(w, "window.receiveEvents([{type:'gallery', id:'v3', state:'downloading', pct:45}])")
    time.sleep(0.3)
    work = js(w, """(() => {
      const c=document.querySelector('#gal-grid [data-id=v3]');
      return {state:c.dataset.s, shown:getComputedStyle(c.querySelector('.work')).display,
              text:c.querySelector('.work-text').textContent,
              squares:c.querySelectorAll('.squares > span.full').length};
    })()""")
    check("the card shows the download in squares and the real percentage",
          work["state"] == "downloading" and work["shown"] != "none"
          and "45" in work["text"] and work["squares"] == 5, str(work))
    js(w, "window.receiveEvents([{type:'gallery', id:'v5', state:'error', message:'tiktok refused'}])")
    time.sleep(0.3)
    fail = js(w, """(() => {const c=document.querySelector('#gal-grid [data-id=v5]');
      return {e:c.dataset.e, shown:getComputedStyle(c.querySelector('.fail')).display,
              tip:c.querySelector('.cover').title};})()""")
    check("a failed card says so, with the reason on hover",
          fail["e"] == "1" and fail["shown"] != "none" and "refused" in fail["tip"], str(fail))
    js(w, "window.receiveEvents([{type:'gallery', id:'v5', state:'queued'}])")
    time.sleep(0.2)
    check("trying again clears the failed mark",
          js(w, "document.querySelector('#gal-grid [data-id=v5]').dataset.e") == "")
    js(w, "window.receiveEvents([{type:'gallery', id:'v3', state:'done'}])")
    time.sleep(0.3)
    check("when the transcription ends the card goes grey",
          js(w, "document.querySelector('#gal-grid [data-id=v3]').dataset.f") == "1")
    check("gallery count in the bar", js(w, "document.querySelector('#n-gallery').textContent") == "30")
    ow3 = js(w, "document.documentElement.scrollWidth - document.documentElement.clientWidth")
    check("gallery with no horizontal scroll", ow3 <= 0, f"{ow3}px over")

    # ---------------------------------------------------------- history and about
    js(w, "document.querySelector('.views button[data-view=history]').click()")
    time.sleep(0.4)
    check("two entries in the history", js(w, "document.querySelectorAll('#hist-grid .tile').length") == 2)
    js(w, "document.querySelector('#hist-grid .tile .open-gal').click()")
    time.sleep(0.4)
    check("a history entry opens its videos in the gallery",
          js(w, "getComputedStyle(document.querySelector('#v-gallery')).display") != "none"
          and js(w, "document.querySelector('#gal-profile').value") == "@marcomontemagno")
    js(w, "window.receiveEvents([{type:'gal_done', total:0, stopped:true}])")
    js(w, "document.querySelector('.views button[data-view=about]').click()")
    time.sleep(0.4)
    check("the about view is filled in", js(w, "document.querySelectorAll('#i-machine dt').length") == 5)
    js(w, "document.querySelector('.views button[data-view=extract]').click()")
    time.sleep(0.2)

    # ---------------------------------------------------------- light theme
    saved.clear()
    js(w, "document.querySelector('#theme').click()")
    time.sleep(0.6)
    check("the theme button switches to light and saves it",
          js(w, "document.documentElement.dataset.theme") == "light" and {"theme": "light"} in saved,
          str(saved))
    check("light theme: the page is cream",
          js(w, "getComputedStyle(document.body).backgroundColor") == "rgb(238, 233, 223)")
    contrast = js(w, CONTRAST)
    check("light: text, secondary text and the action button readable",
          contrast["text"] >= 12 and contrast["second"] >= 8 and contrast["action"] >= 4.5, str(contrast))
    colours = set(js(w, COLOURS))
    check("light: six colours and no more", colours <= PALETTE, str(sorted(colours - PALETTE)))

    fractional = js(w, """(() => {
      const bad=new Set();
      for (const el of document.querySelectorAll('*')){
        const s=parseFloat(getComputedStyle(el).fontSize);
        if (Math.abs(s-Math.round(s))>0.01) bad.add(s);
      }
      return [...bad].join(', ');
    })()""")
    check("no fractional font size", not fractional, fractional or "")
    blur = js(w, """[...document.querySelectorAll('*')].filter(e=>{
      const b=getComputedStyle(e).backdropFilter; return b && b!=='none';}).length""")
    check("no backdrop-filter (it costs a lot while scrolling)", blur == 0, f"{blur} elements")

    err2 = js(w, "window.__errors ? window.__errors.join(' | ') : ''")
    check("no javascript error at the end", not err2, err2 or "")

    w.destroy()


html = read_interface().replace(
    '<script>\n"use strict";',
    '<script>window.__errors=[];window.onerror=(m,s,l)=>window.__errors.push(m+" @"+l);\n"use strict";')

w = webview.create_window("check", html=html, js_api=Api(), width=1280, height=860)
threading.Thread(target=run, args=(w,), daemon=True).start()
webview.start(gui="edgechromium", debug=False, private_mode=True)

print("\n" + "=" * 70)
bad = 0
for name, ok, detail in results:
    print(f"  {'OK  ' if ok else 'FAIL'}  {name}" + (f"   [{detail}]" if detail else ""))
    if not ok:
        bad += 1
print("=" * 70)
print(f"  {len(results) - bad}/{len(results)} passed")
sys.exit(1 if bad else 0)
