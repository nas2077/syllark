/* Orbi pixel renderer and deterministic animation. Integer scaling and reduced motion are supported. */
(function () {
  'use strict';

  const W = 56, H = 46;
  const FPS = 12;
  const seconds = s => Math.round(s * FPS);
  const TAU = Math.PI * 2;

  const HEX = {
    dark: '#1b2632', blue: '#2c3b4d', cream: '#eee9df', sand: '#c9c1b1', rust: '#a35139', orange: '#ffb162',
    light: '#ffd7a8', band: '#f39a55', midtone: '#d98049', night: '#6e3424', darkCream: '#d9cdb8', cheek: '#e8805a'
  };
  const LE = new Uint8Array(new Uint32Array([1]).buffer)[0] === 1;
  const u32 = h => {
    const n = parseInt(h.slice(1), 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255;
    return (LE ? (0xff000000 | (b << 16) | (g << 8) | r) : ((r << 24) | (g << 16) | (b << 8) | 0xff)) >>> 0;
  };
  const C = {};
  for (const k in HEX) C[k] = u32(HEX[k]);

  const SHADES = [C.night, C.rust, C.midtone, C.band, C.orange, C.light];

  function palette(light) {
    return {
      light,
      eye: C.dark, highlight: C.cream, mouth: C.dark, inside: C.night, language: C.cheek,
      cheek: C.cheek, mark: C.rust,
      moon: light ? C.blue : C.cream, moonShadow: light ? C.dark : C.sand,
      ink: light ? C.blue : C.cream,

      ring: light
        ? { 1: [C.dark, C.dark], 2: [C.blue, C.dark], 3: [C.blue, C.dark], 4: [C.dark, C.dark] }
        : { 1: [C.band, C.midtone], 2: [C.cream, C.sand], 3: [C.darkCream, C.sand], 4: [C.midtone, C.rust] },
      radius: light ? C.dark : C.darkCream,
      shine: light ? C.sand : C.cream,

      tip: light ? C.rust : C.light,
      shootingStar: light ? [C.rust, C.midtone, C.orange, C.band, C.light] : [C.light, C.orange, C.band, C.midtone, C.rust]
    };
  }

  function rng(seed) {
    let s = seed >>> 0;
    return () => {
      s = (s + 0x6d2b79f5) >>> 0;
      let t = s;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  const CX = 28, CY = 22, R = 14;
  const TILT = -0.245;
  const RA = 25.5, RB = 7.4, RIN = 0.6;
  const GAP = [0.74, 0.79];
  const RING_DY = 0.5;
  const SHADOW_START = 0.87;
  const norm = v => { const l = Math.hypot(v[0], v[1], v[2]); return [v[0] / l, v[1] / l, v[2] / l]; };
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const LIGHT = norm([-0.38, -0.48, 0.79]);
  const HIGHLIGHT = norm([-0.66, -0.6, 0.45]);
  const REST_INCLINATION = RB / RA;
  const NORTH = (() => { const ic = RB / RA, is = Math.sqrt(1 - ic * ic); return [is * Math.sin(TILT), -is * Math.cos(TILT), ic]; })();

  const shapes = new Map();
  function shape(sx, dx, top, bottom) {
    const k = sx + ' ' + dx + ' ' + top + ' ' + bottom;
    let f = shapes.get(k);
    if (f) return f;
    const a = (dx - sx) / 2, b = (bottom - top) / 2, ox = (sx + dx) / 2, oy = (top + bottom) / 2, c = (a + b) / 2;
    const items = [], inside = new Set();
    for (let j = Math.floor(top); j < Math.ceil(bottom); j++) for (let i = Math.floor(sx); i < Math.ceil(dx); i++) {
      const nx = (i + 0.5 - ox) / a, ny = (j + 0.5 - oy) / b;
      if (nx * nx + ny * ny <= 1.0001) { items.push([i, j, nx, ny]); inside.add(i + ',' + j); }
    }
    const n = items.length;
    f = {
      k, n, ox, oy, radius: c,
      x: new Int8Array(n), y: new Int8Array(n), shade: new Uint8Array(n), edge: new Uint8Array(n),
      z: new Float32Array(n), p: new Float32Array(n * 3)
    };
    items.forEach(([i, j, nx, ny], q) => {
      const nz = Math.sqrt(Math.max(0, 1 - nx * nx - ny * ny));
      const nn = norm([nx / a, ny / b, nz / c]);
      const d = dot(nn, LIGHT);
      let t;
      if (dot(nn, HIGHLIGHT) > 0.965) t = 5;
      else if (d > 0.5) t = 4;
      else if (d > 0.38) t = (i + j) & 1 ? 4 : 3;
      else if (d > 0.25) t = 3;
      else if (d > 0.12) t = 2;
      else if (d > -0.05) t = 1;
      else t = 0;

      const lat = dot(nn, NORTH);
      if (t <= 4 && lat > 0.86 && lat < 0.92) t = Math.max(0, t - 1);
      const edge = !inside.has((i - 1) + ',' + j) || !inside.has((i + 1) + ',' + j) || !inside.has(i + ',' + (j - 1)) || !inside.has(i + ',' + (j + 1));
      f.x[q] = i; f.y[q] = j; f.shade[q] = t;
      f.edge[q] = edge ? (d < 0.2 ? 2 : 1) : 0;
      f.z[q] = nz * c;
      f.p[q * 3] = nx * a; f.p[q * 3 + 1] = ny * b; f.p[q * 3 + 2] = nz * c;
    });
    shapes.set(k, f);
    return f;
  }
  const REST_BOUNDS = [-R, R, -R, R];

  const rings = new Map();
  function ringMap(tilt, rb) {
    tilt = tilt == null ? TILT : tilt; rb = rb == null ? RB : rb;
    const key = tilt.toFixed(3) + ' ' + rb.toFixed(2);
    let A = rings.get(key);
    if (A) return A;
    const ct = Math.cos(tilt), st = Math.sin(tilt);
    const edgeOn = Math.abs(rb) < 0.9;
    const rbv = edgeOn ? 0.9 : Math.abs(rb);
    const ic = (edgeOn ? 0.9 : rb) / RA, is = Math.sqrt(1 - ic * ic);
    const E = new Float32Array(W * H), F = new Float32Array(W * H), V = new Float32Array(W * H);
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const dx = x + 0.5 - CX, dy = y + 0.5 - (CY + RING_DY);
      const u = dx * ct + dy * st, v = -dx * st + dy * ct;
      E[y * W + x] = Math.hypot(u / RA, v / rbv);
      F[y * W + x] = Math.atan2(v / rbv * Math.sign(ic), u / RA);
      V[y * W + x] = v;
    }
    const e = (x, y) => (x < 0 || y < 0 || x >= W || y >= H) ? 9 : E[y * W + x];
    const items = [];
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const i = y * W + x, ee = E[i];
      if (ee < (edgeOn ? 0 : RIN) || ee > 1) continue;
      const outside = e(x - 1, y) > 1 || e(x + 1, y) > 1 || e(x, y - 1) > 1 || e(x, y + 1) > 1;
      const hole = !edgeOn && (e(x - 1, y) < RIN || e(x + 1, y) < RIN || e(x, y - 1) < RIN || e(x, y + 1) < RIN);
      const phi = F[i];

      const thickness = (1 - RIN) * Math.hypot(RA * Math.cos(phi), rbv * Math.sin(phi));
      let zone = 2;
      if (edgeOn) zone = 2;
      else if (outside) zone = 1;
      else if (hole) zone = 4;
      else if (thickness >= 5.5 && ee >= GAP[0] && ee < GAP[1]) zone = 0;
      else if (thickness >= 5.5 && ee < GAP[0]) zone = 3;
      items.push({ x, y, zone, phi, dx: x + 0.5 - CX, dy: y + 0.5 - (CY + RING_DY), z: edgeOn ? 40 : (V[i] / ic) * is });
    }
    const n = items.length;
    A = {
      k: key, n, x: new Int8Array(n), y: new Int8Array(n), zone: new Uint8Array(n), loop: new Float32Array(n),
      phi: new Float32Array(n), z: new Float32Array(n), dx: new Float32Array(n), dy: new Float32Array(n),
      north: [is * st, -is * ct, ic], edgeOn
    };
    A.ln = dot(LIGHT, A.north);
    items.forEach((p, k) => {
      A.x[k] = p.x; A.y[k] = p.y; A.zone[k] = p.zone; A.z[k] = p.z; A.phi[k] = p.phi;
      A.dx[k] = p.dx; A.dy[k] = p.dy;

      A.loop[k] = (((p.phi - Math.PI) % TAU) + 2 * TAU) % TAU / TAU;
    });
    rings.set(key, A);
    return A;
  }

  const shadows = new Map();
  function shadowMap(f, A, ax, ay) {
    const k = f.k + '|' + A.k + '|' + ax + ',' + ay;
    let o = shadows.get(k);
    if (o) return o;

    const ox = ax - f.ox, oy = ay + RING_DY - f.oy;
    const p = new Uint8Array(f.n), a = new Uint8Array(A.n);

    if (!A.edgeOn && A.north[2] > REST_INCLINATION * 0.9) {
      const N = A.north;
      for (let q = 0; q < f.n; q++) {
        const sx = f.p[q * 3] - ox, sy = f.p[q * 3 + 1] - oy, sz = f.p[q * 3 + 2];
        const t = -(sx * N[0] + sy * N[1] + sz * N[2]) / A.ln;
        if (t <= 0) continue;
        const rho = Math.hypot(sx + t * LIGHT[0], sy + t * LIGHT[1], sz + t * LIGHT[2]) / RA;

        if (rho >= SHADOW_START && rho <= 1) p[q] = 1;
      }
      const rr = f.radius * f.radius;
      for (let j = 0; j < A.n; j++) {
        const px = A.dx[j] + ox, py = A.dy[j] + oy, pz = A.z[j];
        const b = px * LIGHT[0] + py * LIGHT[1] + pz * LIGHT[2], c = px * px + py * py + pz * pz - rr;
        const disc = b * b - c;
        if (disc > 0 && -b + Math.sqrt(disc) > 0) a[j] = 1;
      }
    }
    o = { p, a };
    shadows.set(k, o);
    return o;
  }

  const MOON_R = 24, MOON_T = -0.06, MOON_C = 0.3;
  function moon3d(ang, radius) {
    const r = radius || MOON_R;
    const ct = Math.cos(MOON_T), st = Math.sin(MOON_T), s = Math.sqrt(1 - MOON_C * MOON_C);
    const ca = Math.cos(ang), sa = Math.sin(ang);
    return [r * (ca * ct - sa * st * MOON_C), r * (ca * st + sa * ct * MOON_C), r * sa * s];
  }

  function sp(rows, dx, dy) {
    const px = [];
    rows.forEach((r, y) => { for (let x = 0; x < r.length; x++) if (r[x] !== '.') px.push(x, y, r[x]); });
    return { w: rows[0].length, h: rows.length, px, dx: dx || 0, dy: dy || 0, rows };
  }
  const mirror = s => ({ w: s.w, h: s.h, dx: s.dx, dy: s.dy, px: s.px.map((v, i) => i % 3 === 0 ? s.w - 1 - v : v) });

  const EYES = {
    open: sp(['.oo.', 'oboo', 'oooo', 'oooo', '.oo.']),
    half: sp(['....', '....', 'oooo', 'oooo', '.oo.']),
    closed: sp(['....', '....', '....', 'oooo', '....']),
    closedHigh: sp(['....', '....', 'oooo', '....', '....']),
    calm: sp(['....', '....', 'o..o', '.oo.', '....']),
    happy: sp(['....', '.oo.', 'o..o', '....', '....']),
    sleepy: sp(['....', '....', 'oooo', 'oboo', '.oo.'], 0, 1),
    large: sp(['.ooo.', 'obboo', 'obooo', 'ooooo', 'ooobo', '.ooo.'], -1, -1),
    squeezed: Object.assign(sp(['....', 'oo..', '..oo', 'oo..', '....']), { symmetric: true }),
    angry: Object.assign(sp(['....', 'o...', 'ooo.', 'oboo', '.oo.']), { symmetric: true }),
    annoyed: Object.assign(sp(['....', '....', 'oooo', 'oboo', '.oo.']), { symmetric: true }),
    empty: sp(['....'])
  };

  const LOOP_PERIOD = [[1, 0], [2, 0], [3, 0], [4, 1], [4, 2], [4, 3], [3, 4], [2, 4], [1, 4], [0, 3], [0, 2], [0, 1]];
  for (let k = 0; k < 12; k++) {
    const r = ['.....', '.....', '..o..', '.....', '.....'].map(x => x.split(''));
    LOOP_PERIOD.forEach(([x, y], i) => { if (i !== k && i !== (k + 1) % 12) r[y][x] = 'o'; });
    EYES['spiral' + k] = sp(r.map(x => x.join('')));
  }
  EYES.spiral = EYES.spiral0;

  const CLOSED = new Set(['closed', 'closedHigh', 'calm', 'happy', 'squeezed', 'half']);

  const MOUTHS = {
    smile: sp(['m..m', '.mm.']),
    wideSmile: sp(['m....m', '.mmmm.']),
    small: sp(['.mm.']),
    grin: sp(['mmmmmm', '.mrrm.', '..mm..']),
    o: sp(['.mm.', 'm..m', '.mm.']),
    smallO: sp(['.m.', 'm.m', '.m.']),
    whistle: sp(['.m.', 'm.m', '.m.'], 2, 0),
    yawn: sp(['.mm.', 'mrrm', 'mrrm', 'mggm', '.mm.']),
    asleep: sp(['.mm.']),
    snoring: sp(['.m.', 'm.m', '.m.']),
    wavy: sp(['.m...', 'm.m.m', '...m.']),
    shout: sp(['.mm.', 'mrrm', '.mm.']),
    flatThree: sp(['mmm'], 0, 1),
    flat: sp(['mmmm'])
  };
  const MOUTH_TRANSITIONS = { 'smile>grin': 'wideSmile', 'grin>smile': 'wideSmile' };
  const CHEEKS = { 1: sp(['gg']), 2: sp(['ggg', 'ggg']) };
  const MARKS = {
    rage: sp(['.x.x.', 'xx.xx', '.....', 'xx.xx', '.x.x.'])
  };
  const MOONS = {
    moon: sp(['.lll.', 'lllll', 'lllls', 'lllss', '.lss.']),

    pumpkin: sp(['..n..', '.aaa.', 'anana', 'aaaaa', 'annna', '.aaa.'], 0, -1)
  };

  const PART = {
    zMark: sp(['iii', '..i', '.i.', 'iii']),
    largeZMark: sp(['iiii', '...i', '..i.', '.i..', 'iiii']),
    note: sp(['.ii', '.i.', 'ii.', 'ii.']),
    star: sp(['.a.', 'aba', '.a.']),
    spark: sp(['..a..', '..a..', 'aabaa', '..a..', '..a..']),
    smallSpark: sp(['.a.', 'aba', '.a.']),
    flash: sp(['b']),
    dust: sp(['.i.', 'i.i', '.i.']),
    dotMark: sp(['i']),
    bubble: sp(['.i.', 'i.i', '.i.']),
    largeBubble: sp(['.ii.', 'i..i', 'i..i', '.ii.']),
    exclamation: sp(['i', 'i', 'i', '.', 'i']),
    heart: sp(['.g.g.', 'ggggg', '.ggg.', '..g..']),
    dream: sp(['.ii.ii.', 'i..a..i', 'i.aba.i', 'i..a..i', '.iiiii.'])
  };

  const EXPRESSIONS = {
    neutral: { eyes: ['open', 'open'], mouth: 'smile', cheeks: 1 },
    entrance: { eyes: ['closed', 'closed'], mouth: 'small', cheeks: 1 },
    happy: { eyes: ['happy', 'happy'], mouth: 'grin', cheeks: 1 },
    shy: { eyes: ['happy', 'happy'], mouth: 'smile', cheeks: 2 },
    pleased: { eyes: ['happy', 'happy'], mouth: 'smile', cheeks: 1 },
    wink: { eyes: ['open', 'happy'], mouth: 'grin', cheeks: 1 },
    wow: { eyes: ['large', 'large'], mouth: 'o', cheeks: 1 },
    surprised: { eyes: ['large', 'large'], mouth: 'smallO', cheeks: 0 },
    curious: { eyes: ['open', 'open'], mouth: 'smallO', cheeks: 1 },
    oh: { eyes: ['open', 'open'], mouth: 'o', cheeks: 1 },
    whistle: { eyes: ['calm', 'calm'], mouth: 'whistle', cheeks: 1 },
    sigh: { eyes: ['calm', 'calm'], mouth: 'smile', cheeks: 1 },
    yawn: { eyes: ['squeezed', 'squeezed'], mouth: 'yawn', cheeks: 1 },
    dazzled: { eyes: ['squeezed', 'squeezed'], mouth: 'flatThree', cheeks: 1 },
    sleepy: { eyes: ['sleepy', 'sleepy'], mouth: 'smile', cheeks: 1 },
    asleep: { eyes: ['calm', 'calm'], mouth: 'asleep', cheeks: 1 },
    dizzy: { eyes: ['spiral', 'spiral'], mouth: 'wavy', cheeks: 0 },
    angry: { eyes: ['angry', 'angry'], mouth: 'shout', cheeks: 2, marks: ['rage'] },
    annoyed: { eyes: ['annoyed', 'annoyed'], mouth: 'flatThree', cheeks: 1 },
    pout: { eyes: ['closedHigh', 'closedHigh'], mouth: 'flatThree', cheeks: 2 },
    peek: { eyes: ['closedHigh', 'half'], mouth: 'flatThree', cheeks: 2 }
  };

  const ALIAS = { normal: 'neutral', large: 'surprised', blink: 'neutral' };

  const EYE_Y = -6, LEFT_EYE_X = -7, RIGHT_EYE_X = 3, MOUTH_Y = -1, CHEEK_Y = -1;

  const MASK = new Uint8Array(W * H);
  const SPOKES = 3;
  function renderPixels(buf, zb, P, T) {
    buf.fill(0); zb.fill(-1e9); MASK.fill(0);
    const only = P.only;
    const bx = P.body.x, by = P.body.y;
    const an = P.ring;
    const A = ringMap(an.tilt, an.rb);
    let om = null;
    if (P.planet !== false) {
      const f = shape(...(P.body.shape || REST_BOUNDS));
      om = shadowMap(f, A, an.x - bx, an.y - by);
      for (let q = 0; q < f.n; q++) {
        const x = CX + bx + f.x[q], y = CY + by + f.y[q];
        if (x < 0 || y < 0 || x >= W || y >= H) continue;
        let tn = f.shade[q];
        if (om.p[q]) tn = Math.max(0, tn - 2);
        if (f.edge[q]) {

          if (f.edge[q] === 2 && tn < 2) tn = 2;

          if (T.light && f.edge[q] === 1 && tn > 3) tn = 3;
        }
        const i = y * W + x;
        if (!only || only === 'body') buf[i] = SHADES[tn];
        zb[i] = f.z[q]; MASK[i] = 1;
      }
      if (!only) renderFace(buf, P, f, T);
      else if (only === 'body') renderFace(buf, Object.assign({}, P, { eyes: P.eyes ? ['empty', 'empty'] : null }), f, T);
      else if (only === 'eyes') renderFace(buf, Object.assign({}, P, { mouth: null, cheeks: 0, marks: [], bubble: null }), f, T);
    }
    if (only === 'body' || only === 'eyes') return;

    const ap = an.opening == null ? 1 : an.opening;
    const phase = an.phase || 0, sector = TAU / SPOKES;
    for (let k = 0; k < A.n; k++) {
      const zone = A.zone[k];
      if (!zone || A.loop[k] > ap) continue;
      const x = A.x[k] + an.x, y = A.y[k] + an.y;
      if (x < 0 || y < 0 || x >= W || y >= H) continue;
      const i = y * W + x, z = A.z[k];
      if (only === 'moon' || (only === 'back' && z >= 0) || (only === 'front' && z < 0)) continue;
      if (!only && z <= zb[i]) continue;
      const dim = om && om.a[k];
      let col = T.ring[zone][dim ? 1 : 0];

      if ((zone === 2 || zone === 3) && !dim) {
        const s = (((A.phi[k] + phase) % sector) + sector) % sector;
        if (s < 0.07) col = zone === 2 ? T.radius : T.ring[3][1];
      }
      if (an.shine != null) {
        let d = Math.abs(A.phi[k] - an.shine) % TAU;
        if (d > Math.PI) d = TAU - d;
        if (d < 0.14) col = T.shine;
      }
      buf[i] = col; zb[i] = z;
    }
    if (only === 'moon') { zb.fill(-1e9); buf.fill(0); }
    if (P.moon && (!only || only === 'moon')) renderMoon(buf, zb, P, T);
    if (!only) for (const p of P.particles || []) renderParticle(buf, zb, p, T);
  }

  function stamp(buf, s, x0, y0, paletteMap, planetOnly) {
    for (let k = 0; k < s.px.length; k += 3) {
      const x = x0 + s.px[k], y = y0 + s.px[k + 1];
      if (x < 0 || y < 0 || x >= W || y >= H) continue;
      const i = y * W + x;
      if (planetOnly && !MASK[i]) continue;
      const c = paletteMap[s.px[k + 2]];
      if (c) buf[i] = c;
    }
  }

  function renderFace(buf, P, f, T) {
    if (!P.eyes) return;
    const fx = CX + P.body.x + (P.faceOffset ? P.faceOffset.x : 0) + Math.round(f.ox);
    const fy = CY + P.body.y + (P.faceOffset ? P.faceOffset.y : 0) + Math.round(f.oy);
    const paletteMap = { o: T.eye, b: T.highlight, m: T.mouth, r: T.inside, g: T.language, x: T.mark, i: T.ink };
    const g = P.gaze || [0, 0];
    const [resizeObserver, od] = P.eyes;
    const s1 = typeof resizeObserver === 'string' ? EYES[resizeObserver] : resizeObserver, s2 = typeof od === 'string' ? EYES[od] : od;
    stamp(buf, s1, fx + LEFT_EYE_X + g[0] + s1.dx, fy + EYE_Y + g[1] + s1.dy, paletteMap, true);
    stamp(buf, s2.symmetric ? mirror(s2) : s2, fx + RIGHT_EYE_X + g[0], fy + EYE_Y + g[1] + s2.dy, paletteMap, true);
    if (P.cheeks) {
      const gs = typeof P.cheeks === 'object' ? P.cheeks : CHEEKS[P.cheeks];
      stamp(buf, gs, fx - 8 - gs.w, fy + CHEEK_Y + gs.dy, { g: T.cheek }, true);
      stamp(buf, mirror(gs), fx + 8, fy + CHEEK_Y + gs.dy, { g: T.cheek }, true);
    }
    const b = typeof P.mouth === 'string' ? MOUTHS[P.mouth] : P.mouth;
    if (b) stamp(buf, b, fx - Math.floor(b.w / 2) + b.dx, fy + MOUTH_Y + b.dy, paletteMap, true);
    for (const s of P.marks || []) { const z = typeof s === 'string' ? MARKS[s] : s; stamp(buf, z, fx + 5 + z.dx, fy - 12 + z.dy, paletteMap, true); }

    if (P.bubble) stamp(buf, PART[P.bubble], fx + 3, fy - 1 - (P.bubble === 'largeBubble' ? 1 : 0), paletteMap, false);
  }

  function renderMoon(buf, zb, P, T) {
    const L = P.moon;
    let px, py, z;
    if (L.x != null) { px = L.x; py = L.y; z = L.z; }
    else { const p = moon3d(L.a, L.r); px = CX + (L.cx || 0) + p[0]; py = CY + (L.cy || 0) + p[1]; z = p[2]; }
    const S = MOONS[L.costume || 'moon'];
    const cx = Math.round(px) - 3 + S.dx, cy = Math.round(py) - 2 + S.dy;
    const paletteMap = { l: T.moon, s: T.moonShadow, a: C.orange, n: C.night };
    const ownedPixels = [];
    for (let k = 0; k < S.px.length; k += 3) {
      const x = cx + S.px[k], y = cy + S.px[k + 1];
      if (x < 0 || y < 0 || x >= W || y >= H) continue;
      const i = y * W + x;
      if (z <= zb[i]) continue;
      buf[i] = paletteMap[S.px[k + 2]]; zb[i] = z; ownedPixels.push(i);
    }

    const occupiedPixels = new Set(ownedPixels), clearPixels = [];
    for (const i of ownedPixels) {
      const x = i % W, y = (i / W) | 0;
      for (const [ddx, ddy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
        const xx = x + ddx, yy = y + ddy;
        if (xx < 0 || yy < 0 || xx >= W || yy >= H) continue;
        const j = yy * W + xx;
        if (occupiedPixels.has(j) || !buf[j]) continue;
        if (zb[j] < z) clearPixels.push(j);
        else clearPixels.push(i);
      }
    }
    for (const i of clearPixels) { buf[i] = 0; zb[i] = -1e9; }
  }

  function renderParticle(buf, zb, p, T) {
    const put = (x, y, c, z) => {
      x = Math.round(x); y = Math.round(y);
      if (x < 0 || y < 0 || x >= W || y >= H) return;
      const i = y * W + x;
      if (z != null && z <= zb[i]) return;
      buf[i] = c;
    };
    if (p.kind === 'shootingStar') {

      const lx = p.dx || 1, ly = p.dy || 0, l = Math.hypot(lx, ly);
      for (let i = 4; i >= 0; i--) put(p.x - lx / l * i * 1.3, p.y - ly / l * i * 1.3, T.shootingStar[i]);
      return;
    }
    if (p.kind === 'confettiItem') { put(p.x, p.y, p.col); put(p.x + (p.side ? 1 : 0), p.y + (p.side ? 0 : 1), p.col); return; }
    const s = PART[p.kind];
    if (!s) return;
    const paletteMap = { i: T.ink, a: C.orange, b: T.tip, r: C.rust, g: C.cheek, n: C.night };
    const x0 = Math.round(p.x) - (s.w >> 1), y0 = Math.round(p.y) - (s.h >> 1);
    for (let k = 0; k < s.px.length; k += 3) put(x0 + s.px[k], y0 + s.px[k + 1], paletteMap[s.px[k + 2]], p.z);
  }

  const FLOAT_PERIOD = 4, BREATH_PERIOD = 6, MOON_PERIOD = 12, RING_PERIOD = 18;
  const floatOffset = phase => Math.round(Math.sin(phase) * 1.2);
  const breathOffset = phase => Math.sin(phase) > 0.55 ? [-R, R, -R - 1, R] : REST_BOUNDS;

  const phasesAt = t => ({ g: t / FLOAT_PERIOD * TAU, r: t / BREATH_PERIOD * TAU + 1.3, l: 3.2 + t / MOON_PERIOD * TAU, a: t / RING_PERIOD * TAU });

  function stillPose(t, name) {
    const e = EXPRESSIONS[ALIAS[name] || name] || EXPRESSIONS.neutral;
    const f = phasesAt(t || 0), f1 = phasesAt((t || 0) - 1 / FPS);
    const P = {
      body: { x: 0, y: floatOffset(f.g), shape: breathOffset(f.r) }, faceOffset: { x: 0, y: 0 },
      eyes: e.eyes.slice(), gaze: [0, 0], mouth: e.mouth, cheeks: e.cheeks, marks: (e.marks || []).slice(),
      ring: { x: 0, y: floatOffset(f1.g), opening: 1, phase: f.a },
      moon: { a: f.l },
      particles: []
    };
    if (name === 'blink') P.eyes = ['closed', 'closed'];
    if (name === 'dizzy') P.eyes = ['spiral0', 'spiral5'];
    return P;
  }

  const IDLE_PERIOD = 144;
  const IDLE_BLINKS = [26, 70, 75, 118];
  const IDLE_GLANCES = [[40, 54, [1, 0]], [96, 108, [-1, -1]]];
  function idlePose(t) {
    const P = stillPose(t, 'neutral');
    const k = ((Math.round(t * FPS) % IDLE_PERIOD) + IDLE_PERIOD) % IDLE_PERIOD;
    for (const b of IDLE_BLINKS) { const j = k - b; if (j >= 0 && j < 3) { const o = ['half', 'closed', 'half'][j]; P.eyes = [o, o]; } }
    for (const [a, z, d] of IDLE_GLANCES) if (k >= a && k < z) P.gaze = d.slice();
    return P;
  }

  function draw(cv, targetCanvas, options) {
    options = options || {};
    const g = cv.getContext('2d');
    const img = g.createImageData(W, H), buf = new Uint32Array(img.data.buffer), zb = new Float32Array(W * H);
    const P = targetCanvas && targetCanvas.body ? targetCanvas : stillPose((targetCanvas && targetCanvas.t) || 0, (targetCanvas && targetCanvas.face) || 'neutral');
    const light = options.theme ? options.theme === 'light' : lightTheme();
    renderPixels(buf, zb, P, palette(light));
    g.putImageData(img, 0, 0);
    return P;
  }

  function lightTheme() {
    const t = document.documentElement.dataset.theme;
    if (t === 'light') return true;
    if (t === 'dark') return false;
    return !!(window.matchMedia && matchMedia('(prefers-color-scheme: light)').matches);
  }

  let VISIT = null;
  function visit() {
    if (VISIT) return VISIT;
    VISIT = { n: 0, lastVisit: 0 };
    try {
      const m = JSON.parse(localStorage.getItem('orbi.visits') || 'null');
      if (m && typeof m.n === 'number') VISIT = { n: m.n, lastVisit: m.lastVisit || 0 };
      localStorage.setItem('orbi.visits', JSON.stringify({ n: VISIT.n + 1, lastVisit: Date.now() }));
    } catch (e) {                                    }
    return VISIT;
  }
  function timeOfDay(d) {
    const h = d.getHours();
    return h >= 22 || h < 6 ? 'night' : h < 11 ? 'morning' : 'day';
  }
  function celebration(d) {
    const m = d.getMonth() + 1, g = d.getDate(), h = d.getHours();
    if (m === 10 && g === 31) return 'halloween';
    if ((m === 12 && g === 31 && h >= 23) || (m === 1 && g === 1)) return 'newYear';
    if (m === 8 && g >= 10 && g <= 13 && (h >= 21 || h < 5)) return 'perseids';
    return null;
  }

  const instances = [];
  let count = 0;

  const SQ = [-15, 15, -12, 14], SQ1 = [-14, 14, -13, 14], ST = [-13, 13, -16, 14], ST1 = [-13, 13, -15, 14];
  const REACTIONS = {
    jump: { dy: [0, -2, -4, -5, -5, -4, -2, 0, 0, 0], fo: [SQ, ST, null, null, null, null, ST1, SQ, SQ1, null] },
    bigJump: { dy: [0, 0, -3, -6, -8, -9, -9, -8, -6, -3, 0, 0, 0], fo: [SQ1, SQ, ST, ST, null, null, null, null, ST1, ST, SQ, SQ1, null] },
    smallJump: { dy: [0, -1, -2, -2, -1, 0, 0], fo: [SQ1, null, null, null, null, SQ1, null] },
    tada: { dy: [0, -1, -3, -3, -2, 0, 0, 0], fo: [SQ, ST1, null, null, null, SQ, SQ1, null] },
    shake: { dx: [1, -1, 1, -1, 1, 0, -1, 0] },
    startle: { dy: [-2, -1, 0] },
    bonk: { dy: [1, 1, 0, 0], fo: [SQ, SQ1, null, null] },
    nods: { dy: [-1, -1, 0] },
    impactX: { fo: [[-12, 12, -15, 15], [-13, 13, -14, 14], null] },
    impactY: { fo: [[-15, 15, -12, 12], [-14, 14, -13, 13], null] }
  };

  function create(cv, options) {
    options = options || {};
    const g = cv.getContext('2d');
    const img = g.createImageData(W, H), buf = new Uint32Array(img.data.buffer), zb = new Float32Array(W * H);
    const say = (text, s) => { try { if (options.say) options.say(text, s); } catch (e) {                                 } };
    const discover = n => { try { if (options.secret) options.secret(n); } catch (e) {            } };
    const random = rng(options.seed != null ? options.seed : ((Date.now() ^ (count++ * 0x9e3779b9)) >>> 0));
    const between = (a, b) => a + random() * (b - a);
    const mqRidotto = window.matchMedia ? matchMedia('(prefers-reduced-motion: reduce)') : null;
    const mqChiaro = window.matchMedia ? matchMedia('(prefers-color-scheme: light)') : null;
    const reducedMotion = () => !!(mqRidotto && mqRidotto.matches);
    const foundSecrets = new Set();
    const secret = n => { if (!foundSecrets.has(n)) { foundSecrets.add(n); discover(n); } };
    const movable = options.moveElement || cv;
    const remember = options.remember !== false;
    const today = () => options.data ? new Date(options.data) : new Date();

    const S = {
      n: 0,

      fG: 0, fR: 1.3, fL: 0, fA: 0,
      rhythm: 1, timeOfDay: 'day', celebration: null,

      last: 0, mouse: null, mouseFrame: -1e9, previousMouse: null, velocity: 0, dist: 99, previousDistance: 99, approach: 0,
      hovered: false, hoverSince: 0, outsideSince: -1e9, touch: null, pressed: null, ignoreClick: false,
      turns: 0, previousAngle: null, turnsSince: 0, messages: new Set(), startledSince: -1e9,

      mood: 'entrance', since: 0, until: 46, aside: null, nextAside: seconds(9), lastAside: null, pending: null,
      series: 0, lastClick: -1e9, reactions: [], side: 1, yawned: false,

      bodyX: 0, historyY: [0, 0, 0], historyX: [0, 0], moonCenter: [0, 0],
      pos: [0, 0], frozenPosition: [0, 0], previousVelocity: [0, 0], maxVelocity: 0, grip: null, bounds: null,

      gaze: [0, 0], goal: [0, 0], goalSince: 0, faceOffset: 0,
      blink: null, nextBlink: seconds(5), glance: null, nextGlance: seconds(7),
      expression: 'entrance', transition: null,

      ringVelocity: 1, moonImpulse: 1, tilt: 0, shine: null, shiny: false,
      particles: [], keys: [], word: '',
      light: lightTheme(), dreamSince: 0
    };

    S.fL = -0.75 - 26 * (TAU / MOON_PERIOD / FPS);
    const queue = [];

    function updateTime() {
      const d = today();
      S.timeOfDay = options.time || timeOfDay(d);
      S.celebration = options.time ? null : celebration(d);
      S.rhythm = S.timeOfDay === 'night' ? 0.8 : 1;
    }
    updateTime();

    const threshold = s => s * (S.timeOfDay === 'night' ? 0.7 : S.timeOfDay === 'morning' ? 1.4 : 1);

    function addParticle(kind, x, y, o) { S.particles.push(Object.assign({ kind, x, y, vx: 0, vy: 0, g: 0, bornAt: S.n, lifetime: seconds(1) }, o || {})); }
    function registerReaction(name) { S.reactions = S.reactions.filter(c => c.name !== name); S.reactions.push({ name, since: S.n }); }
    function center() { return [CX + S.bodyX, CY + floatOffset(S.fG)]; }
    function sparks(n, r0, v) {
      for (let i = 0; i < n; i++) {
        const a = i / n * TAU + random() * 0.5;
        addParticle('spark', CX + Math.cos(a) * r0 * 1.3, CY + Math.sin(a) * r0, { vx: Math.cos(a) * v * 1.3, vy: Math.sin(a) * v, lifetime: seconds(between(0.5, 0.75)), animate: 1 });
      }
    }
    function dust(sides) {
      for (const l of sides || [-1, 1]) addParticle('dust', CX + l * 11, CY + 14, { vx: l * 7, vy: -2, lifetime: seconds(0.35) });
    }

    function scene(name, duration) {

      if (S.mood !== 'awake' && name === 'awake') S.nextAside = Math.max(S.nextAside, S.n + seconds(4));
      S.mood = name; S.since = S.n; S.until = duration == null ? (SCENES[name] && SCENES[name].dur) : duration;
      if (S.until == null) S.until = Infinity; else S.until += S.n;
      S.aside = null;
      const sc = SCENES[name];
      if (sc && sc.enter) sc.enter();
    }
    const available = () => S.mood === 'awake' || S.mood === 'attentive' || S.mood === 'curious';

    function justNow(name) { if (available()) scene(name); else S.pending = name; }

    const SCENES = {
      entrance: { dur: 46 },
      awake: {},
      attentive: { enter: () => secret('hello') },
      curious: { enter: () => secret('curious') },
      happy: { dur: seconds(0.9), enter: () => { registerReaction('jump'); } },
      wow: { dur: seconds(1.4), enter: () => { registerReaction('bigJump'); S.ringVelocity = 8; S.moonImpulse = 3; sparks(8, 15, 22); } },
      dizzy: { dur: seconds(2.8) },
      angry: { dur: seconds(1.5), enter: () => { registerReaction('shake'); S.side = S.mouse && S.mouse[0] > CX ? 1 : -1; } },
      pout: { dur: seconds(3.6) },
      forgive: { dur: seconds(1.5), enter: () => { say('all right, then', 1.4); } },
      yawn: { dur: seconds(1.9), enter: () => { S.yawned = true; } },
      sleepy: {},
      asleep: { enter: () => { secret('asleep'); S.dreamSince = S.n + seconds(60); } },
      wakeUp: {
        dur: seconds(1.3), enter: () => {
          registerReaction('startle'); say('eh?!', 1.1);
          const [x, y] = center(); addParticle('exclamation', x + 11, y - 15, { lifetime: seconds(0.6) });
          S.particles = S.particles.map(p => (p.kind === 'zMark' || p.kind === 'largeZMark' || p.kind === 'dream') ? Object.assign(p, { kind: 'dust', bornAt: S.n, lifetime: seconds(0.3), vx: 0, vy: 0 }) : p);
        }
      },
      startle: { dur: 4, enter: () => { registerReaction('startle'); secret('startle'); S.startledSince = S.n; } },
      called: {
        dur: seconds(1.6), enter: () => {
          registerReaction('smallJump'); secret('name');
          const r = ['here I am!', 'did you call me?', 'yes?', 'present!'];
          say(r[(S.calls = (S.calls || 0) + 1) % r.length], 1.4);
        }
      },
      returned: { dur: seconds(1.6), enter: () => { registerReaction('smallJump'); secret('returned'); } },
      dazzled: { dur: seconds(1.3), enter: () => { say('so bright!', 1.1); secret('light'); } },
      relief: { dur: seconds(1.4), enter: () => { say('ahh', 1); secret('light'); } },
      secondMoon: { dur: seconds(2), enter: () => { say('I am the planet here!', 1.8); secret('moon'); } },
      equinox: { dur: seconds(4.8), enter: () => { S.moonImpulse = 1; secret('konami'); } },
      held: {}, thrown: {}, returning: {}
    };

    const ASIDE = {
      whistle: { weight: 3, dur: seconds(2.6) },
      around: { weight: 3, dur: seconds(2.8) },
      wink: { weight: 2, dur: seconds(1.1) },
      bonk: { weight: 1.4, dur: seconds(3.2) },
      chaseMoon: { weight: 1, dur: seconds(4.8) },
      shootingStar: { weight: 2, dur: seconds(2.6) },
      polish: { weight: 1.4, dur: seconds(2.8) },
      sigh: { weight: 2, dur: seconds(2.4) }
    };
    function asideWeight(name) {
      let p = ASIDE[name].weight;
      if (S.timeOfDay === 'morning' && name === 'whistle') p *= 2;
      if (S.timeOfDay === 'night' && (name === 'sigh' || name === 'shootingStar')) p *= 1.8;
      if (S.celebration === 'perseids' && name === 'shootingStar') p *= 6;
      return p;
    }
    function asideAction(name) {
      if (!name) {
        const names = Object.keys(ASIDE).filter(n => n !== S.lastAside && !(n === 'bonk' && moonPosition()[2] < 0));
        let total = 0; for (const n of names) total += asideWeight(n);
        let r = random() * total; name = names[names.length - 1];
        for (const n of names) { r -= asideWeight(n); if (r <= 0) { name = n; break; } }
      }
      S.aside = { name, since: S.n, dur: ASIDE[name].dur, data: {} };
      S.lastAside = name;
      const D = S.aside.data;
      if (name === 'shootingStar') {
        const since = random() < 0.6 ? 1 : -1;
        D.star = { x0: since > 0 ? W + 3 : -3, y0: between(1, 4), x1: since > 0 ? -4 : W + 4, y1: between(9, 14) };
      }
      if (name === 'bonk') { secret('bonk'); }
      S.nextAside = S.n + ASIDE[name].dur + seconds(S.timeOfDay === 'night' ? between(9, 16) : between(7, 13));
    }

    function insideCanvas(e) {
      const r = cv.getBoundingClientRect();

      if (!(r.width > 0 && r.height > 0)) return null;
      const p = [(e.clientX - r.left) / r.width * W, (e.clientY - r.top) / r.height * H];
      return p.every(Number.isFinite) ? p : null;
    }
    function hovering(p) {
      if (!p || !p.every(Number.isFinite)) return false;
      const x = Math.floor(p[0]), y = Math.floor(p[1]);

      if (x < -1 || y < -1 || x > W || y > H) return false;
      for (let yy = Math.max(0, y - 1); yy <= Math.min(H - 1, y + 1); yy++) {
        for (let xx = Math.max(0, x - 1); xx <= Math.min(W - 1, x + 1); xx++) {
          if (zb[yy * W + xx] > -1e8) return true;
        }
      }
      return false;
    }
    const handlers = {
      move: e => {
        const p = insideCanvas(e);
        if (!p) return;
        queue.push({ t: 'move', p, kind: e.pointerType, bottom: e.buttons > 0, cx: e.clientX, cy: e.clientY });
      },
      bottom: e => {
        if (e.button !== 0) return;
        const p = insideCanvas(e);
        if (!p) return;
        queue.push({ t: 'bottom', p, kind: e.pointerType, cx: e.clientX, cy: e.clientY, id: e.pointerId });
      },
      release: e => queue.push({ t: 'release', kind: e.pointerType, cx: e.clientX, cy: e.clientY }),
      cancel: () => queue.push({ t: 'cancel' }),
      click: () => { if (reducedMotion()) { say('hi!', 1.2); return; } queue.push({ t: 'click' }); },
      canvasKey: e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); queue.push({ t: 'click' }); } },
      button: e => {
        const el = e.target, tag = el && el.tagName;
        if (e.ctrlKey || e.metaKey || e.altKey) return;
        if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (el && el.isContentEditable)) return;
        if (reducedMotion()) {
          if (e.key.length === 1) { S.word = (S.word + e.key.toLowerCase()).slice(-4); if (S.word === 'orbi') { S.word = ''; say('here I am!', 1.4); discover('name'); } }
          return;
        }
        queue.push({ t: 'button', k: e.key });
      },
      menu: e => { if (S.touch || S.grip) e.preventDefault(); },
      touchMove: e => { if (S.grip || (S.touch && S.touch.long)) e.preventDefault(); }
    };

    function attention() {
      S.last = S.n;
      if (S.mood === 'asleep') scene('wakeUp');
      else if (S.mood === 'sleepy' || S.mood === 'yawn') { scene('awake'); registerReaction('startle'); }
    }

    function click() {
      S.last = S.n;
      if (reducedMotion()) { say('hi!', 1.2); return; }
      const u = S.mood;
      if (u === 'entrance' || u === 'equinox' || u === 'held' || u === 'thrown' || u === 'returning') return;
      if (u === 'asleep' || u === 'sleepy' || u === 'yawn') { attention(); return; }
      if (u === 'angry' || u === 'pout') { registerReaction('shake'); S.until += seconds(0.6); say('hmpf', 0.8); return; }
      const n = S.n - S.lastClick <= seconds(1.2) ? S.series + 1 : 1;
      S.series = n; S.lastClick = S.n;
      if (n >= 10) { S.series = 0; scene('angry'); say('hey! enough!', 2); secret('hey'); }
      else if (n >= 6) {
        if (u === 'dizzy') { registerReaction('shake'); S.until = Math.max(S.until, S.n + seconds(1.4)); }
        else { scene('dizzy'); say('ooh… everything is spinning', 2.2); secret('loop'); }
      }
      else if (n >= 3) {

        if (u === 'wow') { registerReaction('bigJump'); S.until = S.n + seconds(1.4); } else { scene('wow'); secret('wow'); }
      }
      else scene('happy');
    }

    const KONAMI = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'b', 'a'];
    function read(e) {
      if (e.t === 'move') {
        if (e.kind === 'touch') {
          if (S.touch && Math.hypot(e.cx - S.touch.cx, e.cy - S.touch.cy) > 8 && !S.touch.long) S.touch = null;
        } else { S.previousMouse = S.mouse; S.mouse = e.p; S.mouseFrame = S.n; S.forcedHover = false; }
        attention();
        if (S.pressed && !S.grip && Math.hypot(e.cx - S.pressed.cx, e.cy - S.pressed.cy) > 4) grab(S.pressed);
        if (S.grip) { S.grip.cx = e.cx; S.grip.cy = e.cy; }
        if (S.touch && S.touch.long && !S.grip && Math.hypot(e.cx - S.touch.cx, e.cy - S.touch.cy) > 6) grab(S.touch);
      } else if (e.t === 'bottom') {
        attention();
        S.ignoreClick = false;
        if (!hovering(e.p) || reducedMotion()) return;
        if (e.kind === 'touch') S.touch = { since: S.n, cx: e.cx, cy: e.cy, long: false };
        else S.pressed = { cx: e.cx, cy: e.cy, id: e.id };
      } else if (e.t === 'release' || e.t === 'cancel') {
        if (S.grip) { releaseGrip(e.t === 'cancel'); S.ignoreClick = true; }
        if (S.touch && S.touch.long) { S.ignoreClick = true; if (S.mood === 'attentive') S.outsideSince = S.n; }
        S.touch = null; S.pressed = null;
      } else if (e.t === 'click') { if (S.ignoreClick) S.ignoreClick = false; else click(); }
      else if (e.t === 'wake') attention();
      else if (e.t === 'button') {
        S.keys.push(e.k.length === 1 ? e.k.toLowerCase() : e.k); if (S.keys.length > 10) S.keys.shift();
        if (KONAMI.every((k, i) => S.keys[i] === k)) { S.keys = []; attention(); justNow('equinox'); }
        if (e.k.length === 1) {
          S.word = (S.word + e.k.toLowerCase()).slice(-4);
          if (S.word === 'orbi') { S.word = ''; if (S.mood === 'asleep') scene('wakeUp'); S.last = S.n; justNow('called'); }
        }
      } else if (e.t === 'returned') {
        if (e.s >= 4) {
          S.last = S.n;
          if (S.mood === 'asleep' || S.mood === 'sleepy') scene('awake');
          S.returnMessage = e.s < 60 ? 'there you are!' : e.s < 600 ? 'where have you been?' : 'I waited for you…';
          justNow('returned');
        }
      } else if (e.t === 'theme') {
        if (e.light !== S.light) { S.light = e.light; if (S.mood !== 'entrance') justNow(e.light ? 'dazzled' : 'relief'); }
      } else if (e.t === 'react') react(e.name);
    }

    function measureBounds() {
      const r = cv.getBoundingClientRect();
      if (!(r.width > 0 && r.height > 0)) return false;
      const u = r.width / W;
      const base = { l: r.left - S.pos[0] * u, t: r.top - S.pos[1] * u, r: r.right - S.pos[0] * u, b: r.bottom - S.pos[1] * u };
      const vw = document.documentElement.clientWidth, vh = window.innerHeight;

      S.bounds = { u, x0: (0 - base.l) / u - 14, x1: (vw - base.r) / u + 14, y0: (0 - base.t) / u - 8, y1: (vh - base.b) / u + 10 };
      return true;
    }
    function grab(since) {
      if (reducedMotion() || S.mood === 'entrance' || S.mood === 'equinox') return;
      if (!measureBounds()) return;
      S.grip = { cx0: since.cx, cy0: since.cy, cx: since.cx, cy: since.cy, pos0: S.pos.slice(), history: [] };
      try { cv.setPointerCapture && since.id != null && cv.setPointerCapture(since.id); } catch (e) {                           }
      S.maxVelocity = 0;
      scene('held');
    }
    function releaseGrip(cancelled) {
      const st = S.grip.history;
      let vx = 0, vy = 0;
      if (st.length >= 2 && !cancelled) { const a = st[Math.max(0, st.length - 4)], b = st[st.length - 1], n = Math.max(1, st.length - 1 - Math.max(0, st.length - 4)); vx = (b[0] - a[0]) / n; vy = (b[1] - a[1]) / n; }
      const v = Math.hypot(vx, vy), cap = 14;
      if (v > cap) { vx *= cap / v; vy *= cap / v; }
      S.previousVelocity = [vx, vy]; S.frozenPosition = S.pos.slice(); S.grip = null;
      S.maxVelocity = Math.hypot(vx, vy);
      if (S.maxVelocity > 3) secret('throwing');
      scene(S.maxVelocity > 1 ? 'thrown' : 'returning');
    }
    function moveElement() {
      const L = S.bounds;
      if (!L) return;
      const t = (S.pos[0] || S.pos[1]) ? `translate(${S.pos[0] * L.u}px, ${S.pos[1] * L.u}px)` : '';
      if (movable.style.transform !== t) movable.style.transform = t;
    }

    function step() {
      S.n++;
      if (S.n % 720 === 0) updateTime();
      for (const e of queue.splice(0)) read(e);
      observe();
      director();
      motion();

      S.pose = livePose();
      renderPixels(buf, zb, S.pose, palette(lightTheme()));
    }

    function observe() {
      const recent = S.mouse && S.n - S.mouseFrame < seconds(4);
      const hovered = S.forcedHover || (recent ? hovering(S.mouse) : (S.touch && S.touch.long) || false);
      if (hovered && !S.hovered) S.hoverSince = S.touch && S.touch.long ? S.n - seconds(0.6) : S.n;
      if (!hovered && S.hovered) S.outsideSince = S.n;
      S.hovered = hovered;
      if (!reducedMotion()) cv.style.cursor = S.grip ? 'grabbing' : hovered ? 'grab' : '';
      if (S.mouse) {
        const [x, y] = center();
        S.previousDistance = S.dist;
        S.dist = Math.hypot(S.mouse[0] - x, (S.mouse[1] - y) * 1.2);
        const moved = S.previousMouse && S.mouseFrame === S.n ? Math.hypot(S.mouse[0] - S.previousMouse[0], S.mouse[1] - S.previousMouse[1]) * FPS : 0;
        S.velocity = S.mouseFrame === S.n ? S.velocity * 0.4 + moved * 0.6 : S.velocity * 0.5;
        S.approach = S.mouseFrame === S.n ? S.approach * 0.5 + (S.previousDistance - S.dist) * 0.5 : S.approach * 0.6;

        if (S.dist > 10 && S.dist < 42 && S.mouseFrame === S.n) {
          const a = Math.atan2(S.mouse[1] - y, S.mouse[0] - x);
          if (S.previousAngle != null) { let d = a - S.previousAngle; if (d > Math.PI) d -= TAU; if (d < -Math.PI) d += TAU; S.turns += d; }
          S.previousAngle = a; S.turnsSince = S.n;
        } else if (S.n - S.turnsSince > seconds(1)) { S.turns = 0; S.previousAngle = null; }
      }

      if (S.touch && !S.touch.long && !S.grip && S.n - S.touch.since >= seconds(0.5)) S.touch.long = true;
    }

    function director() {
      const u = S.mood;
      const still = (S.n - S.last) / FPS;
      if (S.hovered) S.last = S.n;

      if (S.n >= S.until) {
        if (u === 'angry') scene('pout');
        else if (u === 'pout') scene('forgive');
        else if (u === 'forgive') { scene('awake'); registerReaction('smallJump'); }
        else if (u === 'dizzy' && S.maxVelocity > 0) { S.maxVelocity = 0; scene('returning'); }
        else if (u === 'entrance') { scene('awake'); }
        else { scene('awake'); if (u === 'dizzy') registerReaction('shake'); }
      }
      if (S.mood === 'awake' && S.pending) { const a = S.pending; S.pending = null; scene(a); }
      const v = S.mood;
      if (v === 'awake' || v === 'attentive' || v === 'curious') {

        if (S.hovered && S.n - S.hoverSince >= seconds(0.6)) { if (v !== 'attentive') scene('attentive'); }
        else if (v === 'attentive' && !S.hovered && S.n - S.outsideSince >= seconds(0.35)) scene('awake');

        else if (S.velocity > 420 && S.dist < 46 && S.n - S.startledSince > seconds(4) && !S.grip) scene('startle');

        else if (v === 'awake' && S.mouse && S.n - S.mouseFrame < 2 && S.dist < 36 && S.dist > 13 && S.approach > 0.25 && S.velocity < 140) {
          S.curiousCount = (S.curiousCount || 0) + 1;
          if (S.curiousCount >= 5) scene('curious');
        }
        else if (v === 'curious' && (S.dist > 40 || S.n - S.mouseFrame > seconds(1.6))) scene('awake');
        if (S.mood === 'awake' && S.approach <= 0.25) S.curiousCount = 0;

        if (Math.abs(S.turns) >= 3 * TAU) { S.turns = 0; scene('secondMoon'); }
      }
      if (S.mood === 'awake') {
        if (!S.yawned && still > threshold(10)) scene('yawn');
        else if (still > threshold(12.5)) scene('sleepy');
        else if (!S.aside && S.n >= S.nextAside && !S.hovered && S.n - S.lastClick > seconds(3) && !reducedMotion()) asideAction();
      }
      if (still < 1) S.yawned = false;
      if (S.mood === 'sleepy' && still > threshold(15)) scene('asleep');
      if (S.aside && S.n - S.aside.since >= S.aside.dur) S.aside = null;
    }

    function target() {
      const u = S.mood, k = S.n - S.since, A = S.aside;
      if (u === 'entrance') return k >= 23 && k < 26 ? [-1, 0] : k >= 26 && k < 29 ? [1, 0] : [0, 0];
      if (u === 'wakeUp') return k >= 2 && k < 5 ? [-1, 0] : k >= 5 && k < 8 ? [1, 0] : [0, 0];
      if (u === 'asleep' || u === 'dizzy' || u === 'pout' || u === 'equinox') return [0, 0];
      if (A) {
        const j = S.n - A.since;
        if (A.name === 'around') return j < 8 ? [-1, 0] : j < 16 ? [1, 0] : j < 22 ? [0, -1] : [0, 0];
        if (A.name === 'polish') return j < 22 ? [1, 1] : [0, 0];
        if (A.name === 'shootingStar' && A.data.here) return [Math.sign(A.data.here[0] - CX) || 0, -1];
        if ((A.name === 'chaseMoon' && j < 30) || (A.name === 'bonk' && j >= 12 && j < 30)) {
          const l = moonPosition(), [x, y] = center();
          return [Math.abs(l[0] - x) > 5 ? Math.sign(l[0] - x) : 0, Math.abs(l[1] - y + 3) > 6 ? Math.sign(l[1] - y + 3) : 0];
        }
      }
      if (S.mouse && S.n - S.mouseFrame < seconds(4)) {
        const [x, y] = center();
        const dx = S.mouse[0] - x, dy = S.mouse[1] - (y - 3);

        const gx = Math.abs(dx) > 7 ? Math.sign(dx) : Math.abs(dx) < 3 ? 0 : S.goal[0];
        const gy = Math.abs(dy) > 9 ? Math.sign(dy) : Math.abs(dy) < 4 ? 0 : S.goal[1];
        if (gx) S.messages.add(gx > 0 ? 'd' : 's');
        if (gy) S.messages.add(gy > 0 ? 'g' : 'u');
        if (S.messages.size === 4) secret('eyes');
        return [gx, gy];
      }
      if (S.glance && S.n < S.glance.until) return S.glance.dir;
      if (S.n >= S.nextGlance && u === 'awake' && !A) {
        const dirs = [[1, 0], [-1, 0], [1, -1], [-1, -1], [0, -1], [1, 0]];
        S.glance = { dir: dirs[Math.floor(random() * dirs.length)], until: S.n + seconds(between(0.5, 1.1)) };
        S.nextGlance = S.n + seconds(between(3, 7));
        return S.glance.dir;
      }
      return [0, 0];
    }

    function moonPosition() {
      const p = moon3d(S.fL);
      return [CX + S.moonCenter[0] + p[0], CY + S.moonCenter[1] + p[1], p[2]];
    }

    function motion() {
      const u = S.mood, A = S.aside;

      const slow = u === 'asleep' ? 0.8 : u === 'sleepy' ? 0.85 : 1;
      S.fG += TAU / FLOAT_PERIOD / FPS * S.rhythm * slow * (u === 'asleep' ? 4 / 5 : 1);
      S.fR += TAU / BREATH_PERIOD / FPS * S.rhythm * slow;
      let vL = 1;
      if (u === 'asleep') vL = 0.5;
      if (A && A.name === 'chaseMoon' && S.n - A.since < 30) vL = 4.8;
      if (u === 'equinox') vL = 5;
      S.moonImpulse += (1 - S.moonImpulse) * 0.06;
      S.fL += TAU / MOON_PERIOD / FPS * S.rhythm * vL * S.moonImpulse;
      const vA = u === 'asleep' ? 0.3 : u === 'dizzy' ? 3 : u === 'equinox' ? 6 : 1;
      S.ringVelocity += (vA - S.ringVelocity) * 0.1;
      S.fA += TAU / RING_PERIOD / FPS * S.rhythm * S.ringVelocity;

      const m = target();
      if (m[0] !== S.goal[0] || m[1] !== S.goal[1]) { S.goal = m; S.goalSince = S.n; }
      if (S.n - S.goalSince >= 2) S.gaze = [S.gaze[0] + Math.sign(S.goal[0] - S.gaze[0]), S.gaze[1] + Math.sign(S.goal[1] - S.gaze[1])];

      const rotate = u === 'attentive' || u === 'curious' || (A && (A.name === 'around' || A.name === 'chaseMoon'));
      let faceScale = rotate && S.n - S.goalSince >= 5 ? S.goal[0] : 0;
      let bodyScale = (u === 'attentive' || u === 'curious') && S.n - S.goalSince >= 7 ? S.goal[0] : 0;
      if (u === 'pout') { faceScale = -S.side; bodyScale = -S.side; }
      S.faceOffset += Math.sign(faceScale - S.faceOffset);
      S.bodyX += Math.sign(bodyScale - S.bodyX);

      if (S.blink) { S.blink.k++; if (S.blink.k >= S.blink.seq.length) S.blink = null; }
      else if (S.n >= S.nextBlink) {
        const slowly = u === 'sleepy';
        const seq = slowly ? ['half', 'half', 'closed', 'closed', 'closed', 'half', 'half'] : ['half', 'closed', 'half'];
        if (!slowly && random() < 0.22) seq.push(null, null, 'half', 'closed', 'half');
        S.blink = { seq, k: 0 };
        S.nextBlink = S.n + seconds(slowly ? between(1.8, 3) : between(2.6, 6));
      }

      const k = S.n - S.since;
      const [cx, cy] = center();
      if (u === 'asleep') {
        if (k % seconds(2.5) === seconds(0.8)) addParticle(((k / seconds(2.5)) | 0) % 2 ? 'largeZMark' : 'zMark', cx + 12, cy - 10, { vx: 2.2, vy: -3.4, lifetime: seconds(2.6), wave: 1 });
        if (S.n >= S.dreamSince) { addParticle('dream', 9, 8, { lifetime: seconds(4) }); S.dreamSince = S.n + seconds(25); secret('dream'); }
      }
      if (u === 'entrance') {
        if (k === 31) registerReaction('tada');
        if (k === 33) { addParticle('spark', CX - 24, CY + 6, { lifetime: seconds(0.5), animate: 1 }); addParticle('spark', CX + 24, CY - 6, { lifetime: seconds(0.5), animate: 1 }); }
        if (k === 34) greeting();
      }
      if (u === 'angry' && (k === 4 || k === 11)) { addParticle('dust', cx - 8, cy - 14, { vx: -3, vy: -7, lifetime: seconds(0.45) }); addParticle('dust', cx + 8, cy - 14, { vx: 3, vy: -7, lifetime: seconds(0.45) }); }
      if (u === 'equinox' && k === 26) sparks(12, 16, 26);
      if (u === 'equinox' && k === 44) { say('+1 life!', 1.6); S.shiny = true; }
      if (u === 'returned' && k === 3) say(S.returnMessage || 'there you are!', 1.5);
      if (u === 'secondMoon' && k === 0) registerReaction('shake');
      if (A) {
        const j = S.n - A.since;
        if (A.name === 'whistle' && (j === 6 || j === 15 || j === 23)) { addParticle('note', cx + 9, cy - 4, { vx: 4, vy: -8, lifetime: seconds(1.4), wave: 1 }); registerReaction('nods'); }
        if (A.name === 'wink' && j === 3) addParticle('smallSpark', cx + 9, cy - 9, { lifetime: seconds(0.35) });
        if (A.name === 'shootingStar') {
          const st = A.data.star, f = Math.min(1, j / seconds(1.4));
          A.data.here = j <= seconds(1.4) ? [st.x0 + (st.x1 - st.x0) * f, st.y0 + (st.y1 - st.y0) * f] : null;
          if (S.celebration === 'perseids' && j === seconds(1.9)) { addParticle('smallSpark', cx, cy - 16, { lifetime: seconds(0.4) }); secret('calendar'); }
        }
        if (A.name === 'bonk' && j === 10) { registerReaction('bonk'); addParticle('exclamation', cx + 12, cy - 16, { lifetime: seconds(0.5) }); S.tilt = 2; }
        if (A.name === 'chaseMoon' && j === 30) registerReaction('shake');
        if (A.name === 'polish' && j >= 2 && j < 28 && j % 3 === 0) {
          const fi = Math.PI - (j - 2) / 25 * Math.PI, u2 = RA * Math.cos(fi), v2 = RB * Math.sin(fi);
          addParticle('flash', CX + u2 * Math.cos(TILT) - v2 * Math.sin(TILT), CY + RING_DY + u2 * Math.sin(TILT) + v2 * Math.cos(TILT) + 1, { lifetime: 2 });
        }
        if (A.name === 'polish' && j === 27) addParticle('spark', CX + 24, CY - 5, { lifetime: seconds(0.5), animate: 1 });
      }

      if (S.tilt) S.tilt = S.tilt > 0 ? -(S.tilt - 1) : -(S.tilt + 1);

      if (u === 'held' && S.grip) {
        const L = S.bounds;
        const nx = S.grip.pos0[0] + (S.grip.cx - S.grip.cx0) / L.u, ny = S.grip.pos0[1] + (S.grip.cy - S.grip.cy0) / L.u;
        const px = Math.round(Math.max(L.x0, Math.min(L.x1, nx))), py = Math.round(Math.max(L.y0, Math.min(L.y1, ny)));
        S.previousVelocity = [px - S.pos[0], py - S.pos[1]];
        S.pos = [px, py];
        S.grip.history.push([px, py]); if (S.grip.history.length > 6) S.grip.history.shift();
        S.maxVelocity = Math.max(S.maxVelocity * 0.95, Math.hypot(S.previousVelocity[0], S.previousVelocity[1]));
      } else if (u === 'thrown') {
        const L = S.bounds;
        S.frozenPosition[0] += S.previousVelocity[0]; S.frozenPosition[1] += S.previousVelocity[1];
        for (const [i, a, b] of [[0, L.x0, L.x1], [1, L.y0, L.y1]]) {
          if (S.frozenPosition[i] < a || S.frozenPosition[i] > b) {
            S.frozenPosition[i] = Math.max(a, Math.min(b, S.frozenPosition[i])); S.previousVelocity[i] *= -0.55;
            registerReaction(i === 0 ? 'impactX' : 'impactY');
            const side = i === 0 ? [S.frozenPosition[i] <= a ? -1 : 1, 0] : [0, S.frozenPosition[i] <= a ? -1 : 1];
            addParticle('dust', CX + side[0] * 15, CY + side[1] * 15, { lifetime: seconds(0.3) });
          }
        }
        S.previousVelocity[0] *= 0.9; S.previousVelocity[1] *= 0.9;
        S.pos = [Math.round(S.frozenPosition[0]), Math.round(S.frozenPosition[1])];
        if (Math.hypot(S.previousVelocity[0], S.previousVelocity[1]) < 0.35) {
          if (S.maxVelocity > 7) { scene('dizzy', seconds(1.6)); say('wooo…', 1.2); S.maxVelocity = 1; }
          else { S.maxVelocity = 0; scene('returning'); }
        }
      } else if (u === 'returning') {

        for (const i of [0, 1]) { const d = -S.pos[i]; S.pos[i] += Math.abs(d) <= 1 ? d : Math.round(d * 0.2) || Math.sign(d); }
        if (!S.pos[0] && !S.pos[1]) { S.maxVelocity = 0; scene('awake'); }
      }
      if (S.bounds) moveElement();

      const lm = u === 'held' || u === 'thrown' ? [-Math.sign(S.previousVelocity[0]) * 2, -Math.sign(S.previousVelocity[1]) * 2] : [S.bodyX, 0];
      if (S.n % 3 === 0) { S.moonCenter[0] += Math.sign(lm[0] - S.moonCenter[0]); S.moonCenter[1] += Math.sign(lm[1] - S.moonCenter[1]); }
      S.particles = S.particles.filter(p => S.n - p.bornAt < p.lifetime);
      S.reactions = S.reactions.filter(c => S.n - c.since < 14);
    }

    function livePose() {
      const u = S.mood, k = S.n - S.since, A = S.aside, j = A ? S.n - A.since : 0;
      const P = {
        body: { x: 0, y: 0, shape: breathOffset(S.fR) }, faceOffset: { x: 0, y: 0 },
        eyes: null, gaze: [0, 0], mouth: 'smile', cheeks: 1, marks: [],
        ring: { x: 0, y: 0, phase: S.fA, opening: 1, tilt: TILT, rb: RB, shine: null },
        moon: { a: S.fL, cx: S.moonCenter[0], cy: S.moonCenter[1], costume: S.celebration === 'halloween' ? 'pumpkin' : null },
        particles: []
      };

      let y = floatOffset(S.fG), x = S.bodyX, shapeOne = P.body.shape;
      if (u === 'sleepy') { y += 1; const q = k % 30; if (q >= 20 && q < 25) y += 1; }
      if (u === 'asleep') y = Math.round(Math.sin(S.fG) * 0.8) + 1;
      if (u === 'held' || u === 'thrown') {
        y = 0;
        const [vx, vy] = S.previousVelocity;
        if (Math.abs(vx) > 3 && Math.abs(vx) > Math.abs(vy)) shapeOne = [-15, 15, -13, 13];
        else if (Math.abs(vy) > 3) shapeOne = [-13, 13, -15, 15];
      }
      if (u === 'dizzy') x += Math.round(Math.sin(k * 0.8) * 1.2);
      if (u === 'yawn' && k > 3 && k < 14) shapeOne = ST;
      if (A && A.name === 'sigh') { if (j < 6) shapeOne = [-R, R, -R - 1, R]; else if (j < 20) y += 1; }
      for (const c of S.reactions) {
        const q = S.n - c.since, d = REACTIONS[c.name];
        if (d.dy && q < d.dy.length) y += d.dy[q];
        if (d.dx && q < d.dx.length) x += d.dx[q];
        if (d.fo && q < d.fo.length && d.fo[q]) shapeOne = d.fo[q];
      }
      P.body = { x, y, shape: shapeOne };

      const previousY = S.historyY[S.historyY.length - 1];
      S.historyY.push(y); S.historyY.shift();
      let ay = previousY;
      if (S.historyY[0] - previousY <= -2 && y === previousY) ay += 1;
      const previousAx = S.historyX[S.historyX.length - 1];
      S.historyX.push(x); S.historyX.shift();
      let ax = previousAx;
      if (u === 'held' || u === 'thrown') { ax -= Math.sign(S.previousVelocity[0]); ay -= Math.sign(S.previousVelocity[1]); }
      P.ring.x = ax; P.ring.y = ay;
      if (S.tilt) P.ring.tilt = TILT + Math.sign(S.tilt) * 0.06;
      if (u === 'dizzy') P.ring.tilt = TILT + [-0.06, 0, 0.06, 0][((k / 3) | 0) % 4];
      if (u === 'equinox' && k >= 4 && k < 44) P.ring.rb = RB * Math.cos(TAU * (k - 4) / 40);
      if (A && A.name === 'polish' && j >= 2 && j < 28) P.ring.shine = Math.PI - (j - 2) / 25 * Math.PI;
      if (S.shiny && !A) P.ring.shine = ((S.n * 0.09) % (TAU * 2)) - Math.PI;

      if (A && A.name === 'bonk' && j < 22) {
        const l = moonPosition(), cx = CX + x, cy = CY + y;
        const head = [cx + 10, cy - 12, 20], clearPixels = [cx + 21, cy - 16, 20];
        const mix = (a, b, f) => [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f];

        const q = j < 10 ? mix(l, head, (j / 10) ** 2) : j < 15 ? mix(head, clearPixels, Math.sin((j - 10) / 5 * Math.PI / 2)) : mix(clearPixels, l, ((j - 15) / 7) ** 0.7);
        P.moon = { x: q[0], y: q[1], z: q[2], costume: P.moon.costume };
      }

      let e = 'neutral', direct = false;
      switch (u) {
        case 'entrance': e = k < 15 ? null : k < 21 ? 'entrance' : (k >= 31 && k < 41) ? 'happy' : 'neutral'; break;
        case 'attentive': e = 'shy'; break;
        case 'curious': e = 'curious'; break;
        case 'happy': e = 'happy'; break;
        case 'wow': e = 'wow'; break;
        case 'dizzy': case 'secondMoon': e = 'dizzy'; break;
        case 'angry': e = 'angry'; break;
        case 'pout': e = k >= seconds(2.2) && k < seconds(2.8) ? 'peek' : 'pout'; break;
        case 'forgive': e = k < 5 ? 'sigh' : 'happy'; break;
        case 'yawn': e = k < 3 ? 'sleepy' : k < 15 ? 'yawn' : 'sigh'; break;
        case 'sleepy': e = 'sleepy'; break;
        case 'asleep': e = 'asleep'; break;
        case 'wakeUp': e = k < 7 ? 'surprised' : 'neutral'; break;
        case 'startle': e = k < 1 ? 'surprised' : 'neutral'; direct = k < 1; break;
        case 'called': case 'returned': e = k < 10 ? 'happy' : 'neutral'; break;
        case 'dazzled': e = k < 10 ? 'dazzled' : 'neutral'; break;
        case 'relief': e = 'sigh'; break;
        case 'equinox': e = k < 3 ? 'surprised' : k < 44 ? 'wow' : 'happy'; break;
        case 'held': e = k < 3 ? 'surprised' : S.maxVelocity > 6 ? 'wow' : 'happy'; break;
        case 'thrown': e = 'wow'; break;
        case 'returning': e = 'sigh'; break;
      }
      if (u === 'awake' && A) {
        if (A.name === 'whistle') e = j < 2 ? 'neutral' : 'whistle';
        else if (A.name === 'wink') e = j >= 2 && j < 10 ? 'wink' : 'neutral';
        else if (A.name === 'bonk') { e = j < 10 ? 'neutral' : j < 13 ? 'surprised' : j < 30 ? 'annoyed' : 'neutral'; direct = j === 10; }
        else if (A.name === 'chaseMoon') e = j < 30 ? 'curious' : j < 46 ? 'dizzy' : 'neutral';
        else if (A.name === 'shootingStar') e = A.data.here && j > 4 ? 'oh' : (S.celebration === 'perseids' && j > seconds(1.5)) ? 'sigh' : 'neutral';
        else if (A.name === 'polish') e = j < 20 ? 'curious' : 'pleased';
        else if (A.name === 'sigh') e = j >= 6 && j < 22 ? 'sigh' : 'neutral';
      }
      if (e) show(P, e, direct); else P.eyes = null;
      if (P.eyes && P.eyes[0] === 'spiral') P.eyes = ['spiral' + (k % 12), 'spiral' + ((k + 5) % 12)];
      if (u === 'angry' && k % 6 >= 4) P.marks = [];
      if (u === 'asleep') {
        const fr = ((S.fR % TAU) + TAU) % TAU / TAU;
        if (fr > 0.5) P.mouth = 'snoring';
        P.bubble = fr < 0.18 ? null : fr < 0.32 ? 'bubble' : fr < 0.5 ? 'largeBubble' : null;
      }
      const fixedGaze = u === 'asleep' || u === 'dizzy' || u === 'secondMoon' || (P.eyes && CLOSED.has(P.eyes[0]) && P.eyes[0] !== 'half');
      P.gaze = fixedGaze ? [0, 0] : S.gaze.slice();
      if (e === 'peek') P.gaze = [S.side, 0];
      P.faceOffset = { x: S.faceOffset, y: u === 'pout' ? -1 : 0 };

      for (const p of S.particles) {
        const a = (S.n - p.bornAt) / FPS, f = (S.n - p.bornAt) / p.lifetime;
        let kind = p.kind;
        if (p.animate) kind = f < 0.5 ? 'spark' : f < 0.8 ? 'smallSpark' : 'flash';
        if (kind === 'dream') {

          const q = S.n - p.bornAt;
          if (q >= 2) P.particles.push({ kind: 'dotMark', x: CX - 8, y: CY - 13 });
          if (q >= 5) P.particles.push({ kind: 'bubble', x: CX - 12, y: CY - 16 });
          if (q >= 8) P.particles.push({ kind: 'dream', x: p.x, y: p.y });
          continue;
        }
        P.particles.push({
          kind, x: p.x + p.vx * a + (p.wave ? Math.sin(a * 2.4) : 0), y: p.y + p.vy * a + 0.5 * p.g * a * a,
          z: p.z, col: p.col, side: p.side
        });
      }
      if (A && A.name === 'shootingStar' && A.data.here) {
        const st = A.data.star;
        P.particles.push({ kind: 'shootingStar', x: A.data.here[0], y: A.data.here[1], dx: st.x1 - st.x0, dy: st.y1 - st.y0 });
      }
      if (u === 'dizzy' || u === 'secondMoon') {
        for (let i = 0; i < 3; i++) {
          const a = k * 0.45 + i * TAU / 3;
          P.particles.push({ kind: 'star', x: CX + x + Math.cos(a) * 11, y: CY + y - 15 + Math.sin(a) * 2.5, z: Math.sin(a) > 0 ? 50 : -50 });
        }
      }
      if (u === 'entrance') entrance(P, k);
      return P;
    }

    const ENTRANCE_SCALE = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0.25, 0.55, 0.85, 1.1, 0.96, 1.02];
    function entrance(P, k) {
      const u = Math.max(0, Math.min(1, (k - 4) / 8));
      P.ring.opening = 1 - (1 - u) * (1 - u);
      const s = k < ENTRANCE_SCALE.length ? ENTRANCE_SCALE[k] : 1;
      if (s === 0) P.planet = false;
      else if (s !== 1) { const r = Math.max(2, Math.round(R * s)); P.body.shape = [-r, r, -r, r]; P.body.y = 0; }
      if (k === 13) P.ring.y -= 1;
      if (k === 14) P.ring.y += 1;
      if (k < 14) P.moon = null;
      if (k === 1) P.particles.push({ kind: 'flash', x: CX, y: CY });
      if (k === 2) P.particles.push({ kind: 'smallSpark', x: CX, y: CY });
      if (k === 3 || k === 4) P.particles.push({ kind: 'spark', x: CX, y: CY });
    }

    function greeting() {
      const v = remember ? visit() : { n: 0, lastVisit: 0 };
      const hours = v.lastVisit ? (Date.now() - v.lastVisit) / 3600000 : 0;
      if (S.celebration === 'newYear') { say('happy new year!', 2); confetti(); secret('calendar'); }
      else if (S.celebration === 'halloween') { say('trick or treat?', 2); secret('calendar'); }
      else if (v.n >= 1 && hours > 24 * 30) { say('long time no see!', 1.8); secret('visit'); }
      else if (v.n >= 9 && hours > 1) { say('you again! lovely', 1.8); secret('visit'); addParticle('heart', CX + 14, CY - 12, { vy: -4, lifetime: seconds(1.2) }); }
      else if (v.n >= 1 && hours > 1) { say('welcome back!', 1.6); secret('visit'); addParticle('heart', CX + 14, CY - 12, { vy: -4, lifetime: seconds(1.2) }); }
      else if (S.timeOfDay === 'night') { say('it is late…', 1.6); secret('time'); }
      else if (S.timeOfDay === 'morning') { say('good morning!', 1.6); secret('time'); }
      if (S.celebration === 'perseids') secret('calendar');
    }
    function confetti() {
      const cols = [C.orange, C.rust, C.light, C.cheek, S.light ? C.blue : C.cream];
      for (let i = 0; i < 18; i++) addParticle('confettiItem', between(6, W - 6), between(-6, 4), { vx: between(-6, 6), vy: between(4, 10), g: 6, lifetime: seconds(between(2, 3)), col: cols[i % cols.length], side: i % 2 });
    }

    function show(P, name, direct) {
      const e = EXPRESSIONS[name] || EXPRESSIONS.neutral;
      if (S.expression !== name) {
        const previous = EXPRESSIONS[S.expression] || EXPRESSIONS.neutral;
        if (!direct) {
          S.transition = {
            eyes: previous.eyes.map((o, i) => {
              const n = e.eyes[i];
              if (o === n || o.startsWith('spiral') && n.startsWith('spiral')) return n;
              return (CLOSED.has(o) && CLOSED.has(n)) || o === 'half' || n === 'half' ? n : 'half';
            }),
            mouth: previous.mouth === e.mouth ? e.mouth : MOUTH_TRANSITIONS[previous.mouth + '>' + e.mouth] || (previous.mouth === 'small' || e.mouth === 'small' ? e.mouth : 'small'),
            cheeks: Math.round((previous.cheeks + e.cheeks) / 2)
          };
        }
        S.expression = name;
      }
      if (S.transition) {
        P.eyes = S.transition.eyes.slice(); P.mouth = S.transition.mouth; P.cheeks = S.transition.cheeks; P.marks = [];
        S.transition = null;
        return;
      }
      P.eyes = e.eyes.slice(); P.mouth = e.mouth; P.cheeks = e.cheeks; P.marks = (e.marks || []).slice();

      const b = S.blink && S.blink.seq[S.blink.k];
      if (b && (e.eyes[0] === 'open' || e.eyes[0] === 'large' || e.eyes[0] === 'sleepy' || e.eyes[0] === 'annoyed')) P.eyes = [b, b];
    }

    function react(name) {
      if (ASIDE[name]) { if (S.mood !== 'awake') scene('awake'); asideAction(name); return; }
      if (name === 'click') { click(); return; }
      if (name === 'konami') name = 'equinox';
      if (name === 'orbi') name = 'called';
      if (name === 'confetti') { confetti(); return; }

      if (name === 'attentive') { S.forcedHover = true; S.hoverSince = S.n - seconds(1); }

      if (name === 'curious') { S.mouse = [CX + 16, CY - 16]; S.mouseFrame = S.n + seconds(2); S.dist = 22; }
      if (SCENES[name]) scene(name);
    }

    let alive = true, rotate = false, previous = 0, remainder = 0, rafId = 0, visible = !document.hidden, inView = true, frozen = false, clearPixels = 0;
    let frozenPose = null;
    function drawNow() { g.putImageData(img, 0, 0); }
    function repaint() { renderPixels(buf, zb, frozenPose || S.pose, palette(lightTheme())); g.putImageData(img, 0, 0); }
    function cycle(time) {
      rafId = 0;
      if (!rotate) return;
      if (previous) remainder += Math.min(250, time - previous);
      previous = time;
      let stepFrames = 0;
      while (remainder >= 1000 / FPS - 0.01) { remainder -= 1000 / FPS; step(); stepFrames++; }
      if (stepFrames) drawNow();
      rafId = requestAnimationFrame(cycle);
    }
    function updateLoop() {
      const shouldRun = alive && !frozen && !options.manual && visible && inView && !reducedMotion();
      if (shouldRun && !rotate) { rotate = true; previous = 0; if (!rafId) rafId = requestAnimationFrame(cycle); }
      else if (!shouldRun && rotate) { rotate = false; if (rafId) cancelAnimationFrame(rafId); rafId = 0; }
      if (reducedMotion() && !frozen) staticMotion();
    }
    function staticMotion() {

      S.pos = [0, 0]; if (movable.style.transform) movable.style.transform = '';
      renderPixels(buf, zb, stillPose(0, 'neutral'), palette(lightTheme()));
      g.putImageData(img, 0, 0);
    }
    const onVisibility = () => {
      const time = Date.now();
      if (document.hidden) clearPixels = time;
      else if (clearPixels) { queue.push({ t: 'returned', s: (time - clearPixels) / 1000 }); clearPixels = 0; }
      visible = !document.hidden; updateLoop();
    };
    let visibilityObserver = null;
    if (window.IntersectionObserver) {
      visibilityObserver = new IntersectionObserver(v => { inView = v[v.length - 1].isIntersecting; updateLoop(); });
      visibilityObserver.observe(cv);
    }
    const onReducedMotion = () => updateLoop();
    const onTheme = () => {
      const c = lightTheme();
      queue.push({ t: 'theme', light: c });
      if (!rotate) { if (reducedMotion()) staticMotion(); else repaint(); }
    };
    const listen = (mq, f) => mq && (mq.addEventListener ? mq.addEventListener('change', f) : mq.addListener(f));
    const unlisten = (mq, f) => mq && (mq.removeEventListener ? mq.removeEventListener('change', f) : mq.removeListener(f));
    listen(mqRidotto, onReducedMotion);
    listen(mqChiaro, onTheme);
    const themeObserver = window.MutationObserver ? new MutationObserver(onTheme) : null;
    if (themeObserver) themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

    cv.style.touchAction = 'manipulation';
    cv.style.webkitUserSelect = 'none'; cv.style.userSelect = 'none'; cv.style.webkitTouchCallout = 'none';
    window.addEventListener('pointermove', handlers.move);
    cv.addEventListener('pointerdown', handlers.bottom);
    window.addEventListener('pointerup', handlers.release);
    window.addEventListener('pointercancel', handlers.cancel);
    cv.addEventListener('click', handlers.click);
    cv.addEventListener('keydown', handlers.canvasKey);
    cv.addEventListener('contextmenu', handlers.menu);
    cv.addEventListener('touchmove', handlers.touchMove, { passive: false });
    document.addEventListener('keydown', handlers.button);
    document.addEventListener('visibilitychange', onVisibility);
    let stopFitting = null;
    if (options.fit) stopFitting = fit(cv, typeof options.fit === 'object' ? options.fit : {});
    greetConsole();

    S.pose = livePose();
    repaint();
    updateLoop();

    const io = {
      click() { queue.push({ t: 'click' }); },
      wake() { queue.push({ t: 'wake' }); },

      frame(t, face) {
        frozen = true; updateLoop();
        frozenPose = stillPose(t || 0, face || 'neutral');
        repaint();
      },
      resume() { frozen = false; frozenPose = null; updateLoop(); },
      react(name) { queue.push({ t: 'react', name }); },

      stepFrames(n) { for (let i = 0; i < (n == null ? 1 : n); i++) step(); drawNow(); },
      state() { return { mood: S.mood, aside: S.aside && S.aside.name, step: S.n, gaze: S.gaze.slice(), faceOffset: S.faceOffset, bodyX: S.bodyX, expression: S.expression, hovered: S.hovered, rotate, pos: S.pos.slice(), timeOfDay: S.timeOfDay, celebration: S.celebration }; },
      hello() { secret('console'); say('you found me!', 1.6); queue.push({ t: 'react', name: 'called' }); },
      destroy() {
        alive = false; updateLoop();
        window.removeEventListener('pointermove', handlers.move);
        cv.removeEventListener('pointerdown', handlers.bottom);
        window.removeEventListener('pointerup', handlers.release);
        window.removeEventListener('pointercancel', handlers.cancel);
        cv.removeEventListener('click', handlers.click);
        cv.removeEventListener('keydown', handlers.canvasKey);
        cv.removeEventListener('contextmenu', handlers.menu);
        cv.removeEventListener('touchmove', handlers.touchMove);
        document.removeEventListener('keydown', handlers.button);
        document.removeEventListener('visibilitychange', onVisibility);
        if (visibilityObserver) visibilityObserver.disconnect();
        if (themeObserver) themeObserver.disconnect();
        unlisten(mqRidotto, onReducedMotion); unlisten(mqChiaro, onTheme);
        if (stopFitting) stopFitting();
        if (movable.style.transform) movable.style.transform = '';
        const i = instances.indexOf(io);
        if (i >= 0) instances.splice(i, 1);
      }
    };
    instances.push(io);
    return io;
  }

  function fit(el, o) {
    o = o || {};
    const w = o.width || W, h = o.height || H, max = o.max || 640, min = o.min || 1;
    const parent = o.container || el.parentElement;
    let mq = null;
    function measure() {
      const dpr = window.devicePixelRatio || 1;
      let available = max;
      if (parent) {
        const cs = getComputedStyle(parent);
        available = parent.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
      }
      const space = Math.min(max, available > 0 ? available : max);
      const k = Math.max(min, Math.floor(space * dpr / w + 1e-6));
      el.style.width = (k * w / dpr) + 'px';
      el.style.height = (k * h / dpr) + 'px';
      el.dataset.scale = String(k);
      if (mq) mq.removeEventListener('change', measure);
      if (window.matchMedia) { mq = matchMedia(`(resolution: ${dpr}dppx)`); mq.addEventListener('change', measure); }
    }
    const ro = window.ResizeObserver && parent ? new ResizeObserver(measure) : null;
    if (ro) ro.observe(parent); else window.addEventListener('resize', measure);
    measure();
    return () => { if (ro) ro.disconnect(); else window.removeEventListener('resize', measure); if (mq) mq.removeEventListener('change', measure); };
  }

  function crisp(elements, scale) {
    const items = elements && elements.length != null ? Array.from(elements) : [elements];
    function measure() {
      const dpr = window.devicePixelRatio || 1;
      for (const el of items) {
        const vb = el.viewBox && el.viewBox.baseVal;
        if (!vb || !vb.width) continue;
        const s = scale || Number(el.dataset.scale) || 2;
        const k = Math.max(1, Math.round(s * dpr));
        el.style.width = (vb.width * k / dpr) + 'px';
        el.style.height = (vb.height * k / dpr) + 'px';
        el.style.setProperty('--px', (k / dpr) + 'px');
      }
    }
    measure();
    if (window.matchMedia) {
      let mq = matchMedia(`(resolution: ${window.devicePixelRatio || 1}dppx)`);
      const change = () => { measure(); mq.removeEventListener('change', change); mq = matchMedia(`(resolution: ${window.devicePixelRatio || 1}dppx)`); mq.addEventListener('change', change); };
      mq.addEventListener('change', change);
    }
  }

  let greeted = false;
  function greetConsole() {
    if (greeted || !window.console) return;
    greeted = true;
    try {

      const cv = document.createElement('canvas'); cv.width = W; cv.height = H;
      const P = stillPose(0, 'neutral');
      const img = cv.getContext('2d').createImageData(W, H), buf = new Uint32Array(img.data.buffer), zb = new Float32Array(W * H);
      renderPixels(buf, zb, P, palette(false));
      const d = img.data, rows = [], styles = [];
      for (let y = 6; y < 40; y += 2) {
        let r = '';
        for (let x = 2; x < 54; x += 1) {
          const i = (y * W + x) * 4, j = ((y + 1) * W + x) * 4;
          const top = d[i + 3] ? `rgb(${d[i]},${d[i + 1]},${d[i + 2]})` : 'transparent';
          const bot = d[j + 3] ? `rgb(${d[j]},${d[j + 1]},${d[j + 2]})` : 'transparent';
          r += '%c▀'; styles.push(`color:${top};background:${bot};font-size:9px;line-height:9px`);
        }
        rows.push(r);
      }
      console.log(rows.join('\n'), ...styles);
      console.log('%cHi, I am Orbi.%c\nYou found me in the console. Type %cOrbi.hello()%c and press Enter.\nPsst: type “orbi” on the page, or try an old arrow-key code.',
        'font:600 15px sans-serif;color:#ffb162', 'font:13px sans-serif', 'font:13px monospace;color:#ffb162', 'font:13px sans-serif');
    } catch (e) {                                         }
  }

  window.Orbi = {
    create, draw, fit, crisp, instances,
    WIDTH: W, HEIGHT: H, FPS,
    COLORS: Object.assign({}, HEX),
    FACES: Object.keys(EXPRESSIONS),

    hello() { for (const o of instances) o.hello(); return 'hi!'; },

    _internals: { sp, shape, ringMap, shadowMap, stillPose, idlePose, moon3d, IDLE_PERIOD, EYES, MOUTHS, EXPRESSIONS, MOONS, PART, palette, renderPixels, W, H, CX, CY }
  };
})();
