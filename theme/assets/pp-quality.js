/* Peculiar People homepage quality sections. Styles: pp-quality.css.
   - Scroll zoom (sections/pp-scroll-zoom.liquid): pins the band and maps scroll
     position to a zoom on the garment photo, stop by stop. Each stop names a point
     on the photo (percent across and down) and how far to zoom; the script keeps
     that point a little above centre so the words never cover it.
   - Spec overlay (sections/pp-spec-overlay.liquid): draws a line from each dot on
     the photo to its label on desktop, then draws them out when in view.
   - Why chain (sections/pp-why-chain.liquid): lights the lines one at a time, once.
   - Dive (sections/pp-zoom-dive.liquid) and film (sections/pp-zoom-film.liquid):
     the seamless zoom from the lifestyle shot down to the knit, as a photo chain
     drawn on a canvas, or as one scroll-scrubbed video.
   Nothing is armed under reduced motion or without this script, so every section
   falls back to a complete, still layout. Re-initialises in the theme editor. */
(() => {
  if (window.PPQuality) return;

  const reducedQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
  const reduced = () => reducedQuery.matches;
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const ease = (t) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
  const cleanups = new WeakMap();

  // The sticky header, when it is showing, covers the top of a pinned band.
  function headerBottom() {
    const h = document.querySelector('.shopify-section-header-sticky');
    if (!h) return 0;
    const r = h.getBoundingClientRect();
    return r.top <= 1 && r.bottom > 0 ? Math.round(r.bottom) : 0;
  }

  /* ---------- Scroll zoom ---------- */
  function initZoom(section) {
    const img = section.querySelector('img.pp-zoom__img');
    const stops = [...section.querySelectorAll('.pp-zoom__stop')].map((el) => ({
      el,
      z: parseFloat(el.dataset.zoom) || 1,
      x: (parseFloat(el.dataset.x) || 50) / 100,
      y: (parseFloat(el.dataset.y) || 50) / 100,
      m: el.dataset.macro === 'true' ? 1 : 0,
    }));
    if (reduced() || !img || !stops.length) return;

    section.classList.add('is-armed');
    const track = section.querySelector('.pp-zoom__track');
    const sticky = section.querySelector('.pp-zoom__sticky');
    const stage = section.querySelector('.pp-zoom__stage');
    const macro = section.querySelector('.pp-zoom__macro');
    const dotsEl = section.querySelector('[data-pp-zoom-dots]');
    const at = stops.map((_, i) => (stops.length === 1 ? 0 : (i / (stops.length - 1)) * 0.9));
    let active = -1;
    let queued = false;

    const dots = stops.map((_, i) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'pp-zoom__dot';
      b.setAttribute('aria-label', `Go to step ${i + 1} of ${stops.length}`);
      b.addEventListener('click', () => goTo(i));
      dotsEl.appendChild(b);
      return b;
    });

    function travel() {
      return Math.max(1, track.offsetHeight - sticky.offsetHeight);
    }
    function goTo(i) {
      const top = window.scrollY + track.getBoundingClientRect().top - headerBottom();
      window.scrollTo({ top: top + travel() * at[i] + 1, behavior: 'smooth' });
    }

    function place(z, px, py) {
      const W = stage.clientWidth;
      const H = stage.clientHeight;
      const nw = img.naturalWidth || img.width || 1;
      const nh = img.naturalHeight || img.height || 1;
      const k = Math.max(W / nw, H / nh);
      const bw = nw * k;
      const bh = nh * k;
      img.style.width = `${bw}px`;
      img.style.height = `${bh}px`;
      // Zoom is measured against the whole photo fitting the band (zoom 1 shows all of
      // it), so a stop frames the same on a wide desktop and a tall phone. The photo
      // never shrinks below covering the band.
      z = Math.max(1, (z * Math.min(W / nw, H / nh)) / k);
      // Bring the stop's point to just above centre, without showing past the photo's edges.
      let tx = W * 0.5 - z * px * bw;
      let ty = H * 0.42 - z * py * bh;
      const minX = W - z * bw;
      const minY = H - z * bh;
      tx = minX > 0 ? minX / 2 : clamp(tx, minX, 0);
      ty = minY > 0 ? minY / 2 : clamp(ty, minY, 0);
      img.style.transform = `translate3d(${tx.toFixed(1)}px, ${ty.toFixed(1)}px, 0) scale(${z.toFixed(3)})`;
    }

    function frame() {
      queued = false;
      section.style.setProperty('--pp-zoom-top', `${headerBottom()}px`);
      const r = track.getBoundingClientRect();
      const p = clamp((headerBottom() - r.top) / travel(), 0, 1);
      let i = 0;
      while (i < stops.length - 1 && p >= at[i + 1]) i++;
      const a = stops[i];
      const b = stops[Math.min(i + 1, stops.length - 1)];
      const span = at[Math.min(i + 1, stops.length - 1)] - at[i];
      const t = span > 0 ? ease(clamp((p - at[i]) / span, 0, 1)) : 0;
      place(lerp(a.z, b.z, t), lerp(a.x, b.x, t), lerp(a.y, b.y, t));
      if (macro) {
        const m = lerp(a.m, b.m, t);
        macro.style.opacity = m.toFixed(3);
        macro.style.transform = `scale(${(1.2 - m * 0.15).toFixed(3)})`;
      }
      let near = 0;
      at.forEach((v, k) => { if (Math.abs(v - p) < Math.abs(at[near] - p)) near = k; });
      if (near !== active) {
        active = near;
        stops.forEach((s, k) => s.el.classList.toggle('is-active', k === near));
        dots.forEach((d, k) => d.setAttribute('aria-current', k === near ? 'true' : 'false'));
      }
    }
    const request = () => { if (!queued) { queued = true; requestAnimationFrame(frame); } };

    window.addEventListener('scroll', request, { passive: true });
    window.addEventListener('resize', request);
    if (!img.complete) img.addEventListener('load', request, { once: true });

    // Theme editor: selecting a stop's block scrolls to that stop.
    const onSelect = (e) => {
      const i = stops.findIndex((s) => s.el === e.target);
      if (i > -1) goTo(i);
    };
    section.addEventListener('shopify:block:select', onSelect);

    frame();
    cleanups.set(section, () => {
      window.removeEventListener('scroll', request);
      window.removeEventListener('resize', request);
    });
  }

  /* ---------- Shared scroll smoothing for the dive and the film ----------
     The page's scroll position sets a target; what is drawn eases toward it every
     frame (time-based, so 60 Hz and 120 Hz screens move the same). Wheel steps and
     trackpad jitter turn into one continuous glide instead of jumps. */
  function scrollDriver(section, track, sticky, onFrame) {
    let target = 0;
    let current = -1;
    let last = 0;
    let raf = 0;
    const TAU = 110; // ms; how far behind the scroll the picture trails
    function travel() { return Math.max(1, track.offsetHeight - sticky.offsetHeight); }
    function measure() {
      section.style.setProperty('--pp-top', `${headerBottom()}px`);
      const r = track.getBoundingClientRect();
      target = clamp((headerBottom() - r.top) / travel(), 0, 1);
    }
    function tick(now) {
      raf = 0;
      const dt = last ? Math.min(64, now - last) : 16;
      last = now;
      if (current < 0) current = target;
      else current += (target - current) * (1 - Math.exp(-dt / TAU));
      if (Math.abs(target - current) < 0.00005) current = target;
      onFrame(current);
      if (current !== target) raf = requestAnimationFrame(tick);
      else last = 0;
    }
    const kick = () => { measure(); if (!raf) raf = requestAnimationFrame(tick); };
    const jump = () => { measure(); current = target; onFrame(current); };
    window.addEventListener('scroll', kick, { passive: true });
    window.addEventListener('resize', kick);
    function goTo(p) {
      const top = window.scrollY + track.getBoundingClientRect().top - headerBottom();
      window.scrollTo({ top: top + travel() * p + 1, behavior: 'smooth' });
    }
    return {
      kick, jump, goTo,
      stop() {
        window.removeEventListener('scroll', kick);
        window.removeEventListener('resize', kick);
        if (raf) cancelAnimationFrame(raf);
      },
    };
  }

  // Scroll progress to position along the steps: a short hold at each end, and the
  // motion slows (never stops) as it reaches each step so the words can be read.
  function stepPosition(p, n, holdStart = 0.05, holdEnd = 0.1) {
    const q = clamp((p - holdStart) / (1 - holdStart - holdEnd), 0, 1) * (n - 1);
    const k = Math.min(Math.floor(q), n - 2);
    const t = q - k;
    return k + t - (Math.sin(2 * Math.PI * t) / (2 * Math.PI)) * 0.7;
  }

  function showStep(steps, i, state) {
    if (i === state.active) return;
    state.active = i;
    steps.forEach((el, k) => el.classList.toggle('is-active', k === i));
    if (state.dots) state.dots.forEach((d, k) => d.setAttribute('aria-current', k === i ? 'true' : 'false'));
  }

  function makeDots(holder, n, onPick) {
    if (!holder) return null;
    return Array.from({ length: n }, (_, i) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'pp-dive__dot';
      b.setAttribute('aria-label', `Go to step ${i + 1} of ${n}`);
      b.addEventListener('click', () => onPick(i));
      holder.appendChild(b);
      return b;
    });
  }

  /* ---------- Dive (sections/pp-zoom-dive.liquid) ----------
     A chain of photos, each one a close-up of a square inside the one before. The
     camera zooms toward a fixed point so the view lands exactly on that square, at
     a constant felt speed (the zoom is exponential, not linear), while the next
     photo fades in over it with soft edges. At the hand-off the next photo already
     fills the frame, so the switch has nothing to show. Drawn on a canvas from the
     decoded photos: crisp at every zoom, and nothing in the page re-lays out. */
  function initDive(section) {
    const steps = [...section.querySelectorAll('[data-pp-dive-step]')];
    const canvas = section.querySelector('canvas.pp-dive__canvas');
    if (reduced() || !canvas || steps.length < 2 || !canvas.getContext) return;
    const frames = steps.map((el) => {
      const n = (el.dataset.next || '').split(',').map(parseFloat);
      return {
        big: el.dataset.src,
        small: el.dataset.srcSmall || el.dataset.src,
        next: n.length === 3 && n.every((v) => v >= 0) ? { x: n[0] / 100, y: n[1] / 100, w: n[2] / 100 } : null,
        // Where the screen-shaped window sits inside this square photo (0..1).
        fx: clamp((parseFloat(el.dataset.focusX) || 50) / 100, 0, 1),
        fy: clamp((parseFloat(el.dataset.focusY) || 50) / 100, 0, 1),
        img: null,
      };
    });
    // Every step but the last needs a photo and a square for the next one.
    if (frames.some((f, i) => !f.big || (i < frames.length - 1 && !(f.next && f.next.w > 0 && f.next.w < 1)))) return;

    section.classList.add('is-armed');
    const track = section.querySelector('.pp-dive__track');
    const sticky = section.querySelector('.pp-dive__sticky');
    const stage = section.querySelector('.pp-dive__stage');
    const bar = section.querySelector('.pp-dive__bar');
    const ctx = canvas.getContext('2d');
    const scratch = document.createElement('canvas');
    const sctx = scratch.getContext('2d');
    const state = { active: -1, dots: null };
    const last = frames.length - 1;
    let CW = 0;
    let CH = 0;
    let pos = 0;
    let want = 'big';

    function size() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const k = Math.min(1, 2560 / Math.max(1, stage.clientWidth * dpr, stage.clientHeight * dpr));
      CW = Math.max(1, Math.round(stage.clientWidth * dpr * k));
      CH = Math.max(1, Math.round(stage.clientHeight * dpr * k));
      if (canvas.width !== CW || canvas.height !== CH) {
        canvas.width = CW; canvas.height = CH; scratch.width = CW; scratch.height = CH;
      }
      want = Math.max(CW, CH) < 1000 ? 'small' : 'big';
    }

    function load(i) {
      const f = frames[i];
      if (f.loading) return f.loading;
      const im = new Image();
      im.decoding = 'async';
      im.src = f[want];
      f.loading = (im.decode ? im.decode() : new Promise((ok, no) => { im.onload = ok; im.onerror = no; }))
        .then(() => { f.img = im; draw(pos); })
        .catch(() => {});
      return f.loading;
    }

    function draw(d) {
      pos = d;
      if (!CW) return;
      const k = Math.min(Math.floor(d), last - 1);
      const t = clamp(d - k, 0, 1);
      const a = frames[k];
      const b = frames[k + 1];
      const r = a.next;
      // View square inside photo k: size w^t, shrinking toward the fixed point F,
      // the one point that sits at the same place in the view and in the target square.
      const sz = Math.pow(r.w, t);
      const fx = r.x / (1 - r.w);
      const fy = r.y / (1 - r.w);
      const ox = fx * (1 - sz);
      const oy = fy * (1 - sz);
      // The screen is rarely square, so it sees a screen-shaped window inside that
      // square: as wide as the square on a wide screen, as tall on a tall one. The
      // window is placed by a focus point that glides from this photo's focus to the
      // next photo's (in square-relative terms), so at the hand-off it is exactly
      // the window the next photo starts with.
      const aspect = CW / CH;
      const vw = aspect >= 1 ? sz : sz * aspect;
      const vh = aspect >= 1 ? sz / aspect : sz;
      const g = t * t * (3 - 2 * t);
      const qx = a.fx + (b.fx - a.fx) * g;
      const qy = a.fy + (b.fy - a.fy) * g;
      const vx = clamp(ox + qx * sz - vw / 2, ox, ox + sz - vw);
      const vy = clamp(oy + qy * sz - vh / 2, oy, oy + sz - vh);
      ctx.imageSmoothingQuality = 'high';
      ctx.globalAlpha = 1;
      if (a.img) {
        const nw = a.img.naturalWidth;
        const nh = a.img.naturalHeight;
        ctx.drawImage(a.img, vx * nw, vy * nh, vw * nw, vh * nh, 0, 0, CW, CH);
      } else {
        ctx.fillStyle = getComputedStyle(section).getPropertyValue('--pp-dive-bg') || '#000';
        ctx.fillRect(0, 0, CW, CH);
      }
      const alpha = clamp((t - 0.22) / 0.55, 0, 1);
      if (b.img && alpha > 0) {
        const u = CW / vw;
        const dx = (r.x - vx) * u;
        const dy = (r.y - vy) * u;
        const ds = r.w * u;
        // Soft edges while the close-up is still smaller than the frame; they
        // narrow to nothing as it grows to fill it, so the hand-off is exact.
        const f = Math.max(0, 0.14 * (1 - t)) * ds;
        sctx.globalCompositeOperation = 'source-over';
        sctx.clearRect(0, 0, CW, CH);
        sctx.imageSmoothingQuality = 'high';
        sctx.drawImage(b.img, dx, dy, ds, ds);
        if (f > 0.5) {
          sctx.globalCompositeOperation = 'destination-in';
          const fr = f / ds;
          const gx = sctx.createLinearGradient(dx, 0, dx + ds, 0);
          gx.addColorStop(0, 'rgba(0,0,0,0)'); gx.addColorStop(fr, '#000');
          gx.addColorStop(1 - fr, '#000'); gx.addColorStop(1, 'rgba(0,0,0,0)');
          sctx.fillStyle = gx; sctx.fillRect(dx, dy, ds, ds);
          const gy = sctx.createLinearGradient(0, dy, 0, dy + ds);
          gy.addColorStop(0, 'rgba(0,0,0,0)'); gy.addColorStop(fr, '#000');
          gy.addColorStop(1 - fr, '#000'); gy.addColorStop(1, 'rgba(0,0,0,0)');
          sctx.fillStyle = gy; sctx.fillRect(dx, dy, ds, ds);
        }
        ctx.globalAlpha = alpha;
        ctx.drawImage(scratch, 0, 0);
        ctx.globalAlpha = 1;
      }
      if (bar) bar.style.transform = `scaleX(${(d / last).toFixed(4)})`;
      showStep(steps, Math.round(d), state);
    }

    const drv = scrollDriver(section, track, sticky, (p) => draw(stepPosition(p, frames.length)));
    const at = (i) => { const h0 = 0.05; const h1 = 0.1; return h0 + (i / last) * (1 - h0 - h1); };
    state.dots = makeDots(section.querySelector('[data-pp-dive-dots]'), frames.length, (i) => drv.goTo(at(i)));

    size();
    drv.jump();
    // First photo now, the rest straight after, in order, so the next one is
    // always decoded before the zoom reaches it.
    load(0).then(() => frames.slice(1).reduce((p, _, i) => p.then(() => load(i + 1)), Promise.resolve()));

    let ro = null;
    if ('ResizeObserver' in window) {
      ro = new ResizeObserver(() => { size(); draw(pos); });
      ro.observe(stage);
    }
    section.addEventListener('shopify:block:select', (e) => {
      const i = steps.indexOf(e.target);
      if (i > -1) drv.goTo(at(i));
    });
    cleanups.set(section, () => { drv.stop(); if (ro) ro.disconnect(); });
  }

  /* ---------- Film (sections/pp-zoom-film.liquid) ----------
     The same dive as one video, scrubbed by scroll. The video is encoded with a
     keyframe every few frames so seeking stays quick in both directions. */
  function initFilm(section) {
    const steps = [...section.querySelectorAll('[data-pp-dive-step]')];
    const video = section.querySelector('video.pp-dive__video');
    if (reduced() || !video || steps.length < 1) return;
    // A browser that cannot decode the film keeps the still layout (poster and every
    // step's words) rather than a frozen picture with words changing beside it.
    const types = [...video.querySelectorAll('source')].map((el) => el.type || 'video/mp4');
    if (!types.some((t) => video.canPlayType(t.includes('codecs') ? t : `${t}; codecs="avc1.640028"`))) return;
    section.classList.add('is-armed');
    // Each source that fails fires its own error; only the last one means nothing played.
    const lastSource = video.querySelector('source:last-of-type');
    if (lastSource) lastSource.addEventListener('error', () => section.classList.remove('is-armed'));
    const track = section.querySelector('.pp-dive__track');
    const sticky = section.querySelector('.pp-dive__sticky');
    const bar = section.querySelector('.pp-dive__bar');
    const times = steps.map((el) => parseFloat(el.dataset.time) || 0);
    const state = { active: -1, dots: null };
    let want = 0;
    let seeking = false;
    video.muted = true;
    // iOS Safari only decodes frames for seeking once the video has started playing
    // at least once; a muted play-and-pause is allowed without a tap.
    const primed = video.play();
    if (primed && primed.then) primed.then(() => { video.pause(); seek(); }).catch(() => {});
    else video.pause();

    function seek() {
      const dur = video.duration;
      if (!dur || seeking) return;
      const tt = clamp(want, 0, 1) * (dur - 0.05);
      if (Math.abs(video.currentTime - tt) < 0.012) return;
      seeking = true;
      if (video.fastSeek && Math.abs(video.currentTime - tt) > 2) video.fastSeek(tt);
      else video.currentTime = tt;
    }
    video.addEventListener('seeked', () => { seeking = false; seek(); });
    video.addEventListener('loadedmetadata', () => seek());

    const drv = scrollDriver(section, track, sticky, (p) => {
      want = clamp((p - 0.05) / 0.85, 0, 1);
      seek();
      if (bar) bar.style.transform = `scaleX(${want.toFixed(4)})`;
      const dur = video.duration || times[times.length - 1] || 1;
      const now = want * dur;
      let i = 0;
      times.forEach((v, k) => { if (now >= v - 0.25) i = k; });
      showStep(steps, i, state);
    });
    const at = (i) => 0.05 + 0.85 * ((times[i] || 0) / (video.duration || times[times.length - 1] || 1));
    state.dots = makeDots(section.querySelector('[data-pp-dive-dots]'), steps.length, (i) => drv.goTo(at(i)));
    if (video.readyState < 1) video.load();
    drv.jump();
    section.addEventListener('shopify:block:select', (e) => {
      const i = steps.indexOf(e.target);
      if (i > -1) drv.goTo(at(i));
    });
    cleanups.set(section, () => drv.stop());
  }

  /* ---------- Spec overlay ---------- */
  function initSpec(section) {
    const stage = section.querySelector('[data-pp-spec-stage]');
    const svg = section.querySelector('[data-pp-spec-lines]');
    const NS = 'http://www.w3.org/2000/svg';

    function draw() {
      svg.textContent = '';
      if (window.getComputedStyle(svg).display === 'none') return;
      const s = stage.getBoundingClientRect();
      svg.setAttribute('viewBox', `0 0 ${s.width} ${s.height}`);
      section.querySelectorAll('[data-pp-spec-label]').forEach((label, k) => {
        const dot = section.querySelector(`[data-pp-spec-dot="${label.dataset.ppSpecLabel}"]`);
        if (!dot) return;
        const d = dot.getBoundingClientRect();
        const l = label.getBoundingClientRect();
        const left = label.classList.contains('pp-spec__label--left');
        const x1 = d.left + d.width / 2 - s.left;
        const y1 = d.top + d.height / 2 - s.top;
        const x2 = (left ? l.right + 10 : l.left - 10) - s.left;
        const y2 = l.top + 9 - s.top;
        const line = document.createElementNS(NS, 'line');
        line.setAttribute('x1', x1.toFixed(1));
        line.setAttribute('y1', y1.toFixed(1));
        line.setAttribute('x2', x2.toFixed(1));
        line.setAttribute('y2', y2.toFixed(1));
        line.style.setProperty('--len', Math.hypot(x2 - x1, y2 - y1).toFixed(1));
        line.style.setProperty('--i', k);
        svg.appendChild(line);
      });
    }

    draw();
    let ro = null;
    if ('ResizeObserver' in window) {
      ro = new ResizeObserver(() => draw());
      ro.observe(stage);
    }
    section.querySelectorAll('img').forEach((im) => { if (!im.complete) im.addEventListener('load', draw, { once: true }); });

    if (!reduced() && 'IntersectionObserver' in window) {
      section.classList.add('is-armed');
      const io = new IntersectionObserver((entries) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        section.classList.add('is-in');
        io.disconnect();
      }, { threshold: 0.3 });
      io.observe(stage);
    }
    cleanups.set(section, () => { if (ro) ro.disconnect(); });
  }

  /* ---------- Why chain ---------- */
  function initChain(section) {
    const lines = [...section.querySelectorAll('.pp-chain__line')];
    const video = section.querySelector('video');
    if (reduced()) {
      if (video) { video.removeAttribute('autoplay'); video.pause(); }
      return;
    }
    if (!lines.length || !('IntersectionObserver' in window)) return;
    section.classList.add('is-armed');
    let timer = null;
    const io = new IntersectionObserver((entries) => {
      if (!entries.some((e) => e.isIntersecting)) return;
      io.disconnect();
      section.classList.add('is-in');
      let i = 0;
      const step = () => {
        lines.forEach((l, k) => {
          l.classList.toggle('is-lit', k === i || (i >= lines.length - 1 && k === lines.length - 1));
          l.classList.toggle('is-past', k < i);
        });
        if (i < lines.length - 1) { i += 1; timer = setTimeout(step, 1500); }
      };
      step();
    }, { threshold: 0.35 });
    io.observe(section);
    cleanups.set(section, () => { clearTimeout(timer); io.disconnect(); });
  }

  function init(root = document) {
    const run = (sel, fn) => root.querySelectorAll(`${sel}:not([data-pp-init])`).forEach((s) => {
      s.dataset.ppInit = '1';
      fn(s);
    });
    run('[data-pp-zoom]', initZoom);
    run('[data-pp-dive]', initDive);
    run('[data-pp-film]', initFilm);
    run('[data-pp-spec]', initSpec);
    run('[data-pp-chain]', initChain);
  }

  window.PPQuality = { init };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => init());
  else init();
  document.addEventListener('shopify:section:load', (e) => init(e.target));
  document.addEventListener('shopify:section:unload', (e) => {
    e.target.querySelectorAll('[data-pp-init]').forEach((s) => {
      const fn = cleanups.get(s);
      if (fn) fn();
    });
  });
})();
