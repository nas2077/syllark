/* Nas interactions: presets, motion, accessible controls, and Orbi lifecycle. */
(function () {
  'use strict';
  const Nas = window.Nas = window.Nas || {};
  if (window.Orbi) Nas.Orbi = window.Orbi;
  if (Nas.init) return;
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const initialized = new WeakMap(), animations = new Set(), mascots = new Set();
  const options = {
    personality: ['orbit','studio','workshop'], theme: ['dark','light','system'],
    motion: ['quiet','expressive','off'], density: ['comfortable','compact','airy']
  };
  const base = { personality: 'orbit', theme: 'system', motion: 'expressive', density: 'comfortable' };
  const move = () => !reducedMotion.matches && document.documentElement.dataset.motion !== 'off';
  const elements = (root, selector) => [...(root.matches?.(selector) ? [root] : []), ...root.querySelectorAll(selector)];
  function configuration() {
    const d = document.documentElement.dataset;
    return Object.fromEntries(Object.keys(base).map(k => [k,options[k].includes(d[k]) ? d[k] : base[k]]));
  }
  function updateMotion() {
    if (!move()) {
      animations.forEach(a => a.cancel()); animations.clear();
      document.querySelectorAll('.n-pending').forEach(el => el.classList.remove('n-pending'));
    }
    mascots.forEach(m => move() ? m.resume() : m.frame(0,'neutral'));
  }
  function configure(config = {}) {
    Object.entries(config).forEach(([k,v]) => {
      if (!options[k]?.includes(v)) return;
      if (k === 'theme' && v === 'system') delete document.documentElement.dataset.theme;
      else document.documentElement.dataset[k] = v;
    });
    updateMotion();
    document.dispatchEvent(new CustomEvent('nas:configuration',{ detail: configuration() }));
    return configuration();
  }
  function presetCSS(config = configuration()) {
    const c = { ...base };
    Object.entries(config).forEach(([k,v]) => { if (options[k]?.includes(v)) c[k] = v; });
    const p = {
      orbit: { radius:'10px','radius-card':'16px','page-max':'1120px','section-space':'96px','card-space':'28px','duration-media':'320ms' },
      studio: { radius:'6px','radius-card':'10px','page-max':'1200px','section-space':'112px','card-space':'32px','duration-media':'320ms' },
      workshop: { radius:'8px','radius-card':'12px','page-max':'1040px','section-space':'64px','card-space':'20px','duration-media':'240ms' }
    }[c.personality];
    if (c.density === 'compact') Object.assign(p,{'card-space':'20px','section-space':'64px'});
    if (c.density === 'airy') Object.assign(p,{'card-space':'32px','section-space':'112px'});
    Object.assign(p, c.motion === 'quiet' ? { 'distanza-entrance':'8px','duration-entrance':'380ms','lift':'-2px' } : { 'distanza-entrance':'26px','duration-entrance':'680ms','lift':'-6px' });
    return '/* Nas · '+c.personality+'\n   Load after nas.css. Set theme and motion with the preset HTML attributes. */\n:root {\n'+Object.entries(p).map(([k,v]) => '  --'+k+': '+v+';').join('\n')+'\n}\n';
  }
  function download(name, content, kind = 'text/plain;charset=utf-8') {
    const url = URL.createObjectURL(new Blob([content],{ type:kind }));
    const a = document.createElement('a'); a.href = url; a.download = name;
    document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url),10000);
  }
  function reveal(root = document) {
    const els = elements(root,'[data-n-reveal]');
    if (!move() || !('IntersectionObserver' in window)) return () => {};
    const io = new IntersectionObserver(entries => entries.forEach(({ target,isIntersecting }) => {
      if (!isIntersecting) return;
      target.classList.remove('n-pending'); target.classList.add('n-revealed'); io.unobserve(target);
    }),{ threshold:.12 });
    els.forEach(el => { el.classList.add('n-pending'); io.observe(el); });
    return () => { io.disconnect(); els.forEach(el => el.classList.remove('n-pending')); };
  }
  function replay(el) {
    el.classList.remove('n-revealed');
    if (move()) { void el.offsetWidth; el.classList.add('n-revealed'); }
  }
  function celebrate(el) {
    if (!move() || !el?.animate) return;
    const r = el.getBoundingClientRect(), colors = ['var(--pixel-orange)','var(--text)','var(--action)'];
    for (let i = 0; i < 14; i++) {
      const p = document.createElement('span'); p.className = 'n-confettiItem'; p.setAttribute('aria-hidden','true');
      p.style.left = r.left + r.width / 2 + 'px'; p.style.top = r.top + r.height / 2 + 'px'; p.style.background = colors[i % 3];
      document.body.append(p);
      const x = Math.round(Math.cos(i * 2.4) * (40 + i * 3)), y = -35 - i * 5;
      const a = p.animate([{transform:'translate(0,0)',opacity:1},{transform:`translate(${x}px,${y}px)`,opacity:1,offset:.65},{transform:`translate(${x}px,${y+24}px)`,opacity:0}],{duration:650+i*18,easing:'steps(10,end)'});
      animations.add(a); a.finished.catch(() => {}).finally(() => { animations.delete(a); p.remove(); });
    }
  }
  function toast(text, { duration = 5000 } = {}) {
    let area = document.querySelector('.n-toast-area');
    if (!area) {
      area = document.createElement('div'); area.className = 'n-toast-area'; area.setAttribute('aria-label','Notifications'); document.body.append(area);
    }
    const el = document.createElement('div'); el.className = 'n-toast';
    el.innerHTML = '<svg class="n-pixel-check" viewBox="0 0 10 10" aria-hidden="true"><path d="M1 5h2v2H1zM3 7h2v2H3zM5 5h2v2H5zM7 3h2v2H7zM9 1h1v2H9z"/></svg><span class="n-toast__text" role="status"></span><button type="button" class="n-dismiss" aria-label="Dismiss notification">×</button>';
    area.append(el); el.querySelector('[role="status"]').textContent = String(text);
    let timer, remaining = Math.max(1000,duration), startedAt, pointerInside = false;
    const dismiss = () => { clearTimeout(timer); el.remove(); };
    const pause = () => { clearTimeout(timer); if (startedAt) remaining = Math.max(0,remaining - (Date.now() - startedAt)); startedAt = 0; };
    const resume = () => { if (duration === 0 || pointerInside || el.contains(document.activeElement)) return; clearTimeout(timer); startedAt = Date.now(); timer = setTimeout(dismiss,remaining); };
    el.querySelector('button').addEventListener('click',dismiss);
    el.addEventListener('pointerenter',() => { pointerInside = true; pause(); });
    el.addEventListener('pointerleave',() => { pointerInside = false; resume(); });
    el.addEventListener('focusin',pause); el.addEventListener('focusout',() => setTimeout(resume,0));
    resume(); return { element:el, dismiss };
  }
  function openDialog(id, trigger) {
    const d = typeof id === 'string' ? document.getElementById(id) : id;
    if (!(d instanceof HTMLDialogElement)) return;
    if (d.open) return;
    d.showModal();
    if (trigger) d.addEventListener('close',() => { if (trigger.isConnected) trigger.focus(); },{once:true});
    const input = d.querySelector('[data-n-filter]'); if (input) { input.value = ''; filterItems(input); input.focus(); }
  }
  function filterItems(input) {
    const d = input.closest('dialog') || input.parentElement;
    const q = input.value.toLocaleLowerCase('it').trim();
    d.querySelectorAll('[data-n-item]').forEach(el => { el.hidden = !el.textContent.toLocaleLowerCase('it').includes(q); });
    const empty = d.querySelector('[data-n-empty]');
    if (empty) empty.hidden = !!d.querySelector('[data-n-item]:not([hidden])');
  }
  function activateTab(tab) {
    const group = tab?.closest('[data-n-tabs]'); if (!group) return;
    group.querySelectorAll('[role="tab"]').forEach(t => {
      const enabled = t === tab; t.setAttribute('aria-selected',enabled); t.tabIndex = enabled ? 0 : -1;
      const p = document.getElementById(t.getAttribute('aria-controls')); if (p) p.hidden = !enabled;
    });
    group.dispatchEvent(new CustomEvent('nas:tab',{ bubbles:true, detail:{ id:tab.id } }));
  }
  function init(root = document) {
    if (initialized.has(root)) return initialized.get(root);
    const controller = new AbortController(), signal = controller.signal, cleanups = [reveal(root)];
    elements(root,'[data-n-tabs]').forEach(g => activateTab(g.querySelector('[aria-selected="true"]') || g.querySelector('[role="tab"]')));
    root.addEventListener('click',e => {
      const tab = e.target.closest?.('[data-n-tabs] [role="tab"]'); if (tab) activateTab(tab);
      const trigger = e.target.closest?.('[data-n-open]'); if (trigger) openDialog(trigger.dataset.nOpen,trigger);
      const close = e.target.closest?.('[data-n-close]'); if (close) close.closest('dialog')?.close();
      const msg = e.target.closest?.('[data-n-toast]'); if (msg) toast(msg.dataset.nToast);
      const celebration = e.target.closest?.('[data-n-celebrate]'); if (celebration) celebrate(celebration);
    },{signal});
    root.addEventListener('input',e => { if (e.target.matches?.('[data-n-filter]')) filterItems(e.target); },{signal});
    root.addEventListener('keydown',e => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        const d = root.querySelector('[data-n-command]');
        if (d && !document.querySelector('dialog[open]')) { e.preventDefault(); openDialog(d,document.activeElement); }
      }
      const tab = e.target.closest?.('[data-n-tabs] [role="tab"]');
      if (tab && ['ArrowLeft','ArrowRight','Home','End'].includes(e.key)) {
        e.preventDefault(); const tabs = [...tab.closest('[data-n-tabs]').querySelectorAll('[role="tab"]')];
        const i = tabs.indexOf(tab), next = e.key === 'Home' ? 0 : e.key === 'End' ? tabs.length-1 : (i + (e.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
        tabs[next].focus(); activateTab(tabs[next]);
      }
      const dialog = e.target.closest?.('[data-n-command]');
      if (dialog && ['ArrowDown','ArrowUp','Enter'].includes(e.key)) {
        const items = [...dialog.querySelectorAll('[data-n-item]:not([hidden])')];
        if (!items.length) return;
        if (e.key === 'Enter' && e.target.matches('[data-n-filter]')) { e.preventDefault(); items[0].click(); }
        else if (e.key !== 'Enter') { e.preventDefault(); const i = items.indexOf(document.activeElement); const next = i < 0 ? (e.key === 'ArrowDown' ? 0 : items.length-1) : (i + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length; items[next].focus(); }
      }
    },{signal});
    elements(root,'[data-n-magnetic]').forEach(el => {
      const reset = () => { el.style.translate = ''; };
      el.addEventListener('pointermove',e => {
        if (!move() || !matchMedia('(hover:hover) and (pointer:fine)').matches || e.pointerType !== 'mouse') return reset();
        const r = el.getBoundingClientRect(); el.style.translate = `${Math.round((e.clientX-r.left-r.width/2)*.09)}px ${Math.round((e.clientY-r.top-r.height/2)*.09)}px`;
      },{signal});
      el.addEventListener('pointerleave',reset,{signal});
      document.addEventListener('nas:configuration',reset,{signal}); reducedMotion.addEventListener('change',reset,{signal}); cleanups.push(reset);
    });
    const cleanup = () => { controller.abort(); cleanups.forEach(f => f()); initialized.delete(root); };
    initialized.set(root,cleanup); return cleanup;
  }
  function orbi(canvas, orbiOptions = {}) {
    const engine = Nas.Orbi || window.Orbi;
    if (!engine) throw new Error('Load orbi.js before Nas.orbi().');
    const m = engine.create(canvas,orbiOptions); mascots.add(m);
    const destroy = m.destroy.bind(m);
    m.destroy = () => { mascots.delete(m); destroy(); };
    if (!move()) m.frame(0,'neutral'); return m;
  }
  reducedMotion.addEventListener('change',updateMotion);
  Object.assign(Nas,{ init,configure,configuration,presetCSS,download,toast,openDialog,celebrate,orbi,motion:{ reveal,replay,enabled:move } });
})();
