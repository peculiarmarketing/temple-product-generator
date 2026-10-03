/* Peculiar People homepage quality sections. Styles: pp-quality.css.
   - Scroll zoom (sections/pp-scroll-zoom.liquid): pins the band and maps scroll
     position to a zoom on the garment photo, stop by stop. Each stop names a point
     on the photo (percent across and down) and how far to zoom; the script keeps
     that point a little above centre so the words never cover it.
   - Spec overlay (sections/pp-spec-overlay.liquid): draws a line from each dot on
     the photo to its label on desktop, then draws them out when in view.
   - Why chain (sections/pp-why-chain.liquid): lights the lines one at a time, once.
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
