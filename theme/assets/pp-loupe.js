/* Peculiar People homepage: the loupe (sections/pp-loupe.liquid). Styles: pp-loupe.css.

   For each garment a macro "world" is built once, in the photo's own pixel frame:
   the photo, then the cloth (garment colour + weave at true scale, clipped to the
   garment's outline mask), zones with their own fabric (rib on hems, cuffs and
   collars, the brushed lining where a hem is rolled back), the full-size print
   where it sits, and the weave again over the ink, so the ink sits in the knit. The lens shows that world scaled about the point under it, so the print is
   drawn from the print file, not enlarged from the photo. Nothing appears in the
   lens until every layer has decoded. Mouse: the lens follows the pointer. Touch:
   tap a garment to put the lens there (it rides above the finger), tap outside to
   put it away. On first view the lens tours a print and the fabrics once.
   Re-initialises in the theme editor. */
(() => {
  if (window.PPLoupe) return;
  const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const P = 1400;  // photo frame, px
  const lerp = (a, b, t) => a + (b - a) * t;
  const decode = (src) => new Promise((res) => { const i = new Image(); i.onload = i.onerror = () => res(i); i.src = src; });

  function init(section) {
    const lens = section.querySelector('.pp-loupe__lens');
    const world = section.querySelector('.pp-loupe__world');
    const label = section.querySelector('.pp-loupe__label');
    const cards = [...section.querySelectorAll('[data-pp-loupe-g]')];
    const MAG = +section.dataset.mag || 24;
    const printSrc = section.dataset.print;
    const worlds = new Map();
    let building = null;
    let lastZ = 0;
    const box = (x, y, w, h) => `left:calc(${x}px * var(--z));top:calc(${y}px * var(--z));width:calc(${w}px * var(--z));height:calc(${h}px * var(--z))`;
    // `lift`: on touch the lens is drawn above the finger, while it still shows
    // what is under the finger.
    let ready = false, active = null, want = null, pos = null, raf = 0, last = 0, tour = null, toured = false, lift = 0;

    // Real scale: the print is PRINT_CM wide, so the photo's px per cm comes from
    // its print box, and each fabric tile covers its true width in cm (the number of
    // stitch columns in the tile over that fabric's columns per cm).
    const PRINT_CM = 30.5;
    const TILE_CM = { jersey: 1.0, fleece: 1.7, rib: 1.5, brushed: 2.0 };

    // A small readable copy of a mask, to know what is under the lens.
    async function sampler(src, w = 350) {
      const im = await decode(src);
      if (!im.naturalWidth) return () => 0;
      const c = document.createElement('canvas');
      c.width = w; c.height = Math.round(w * im.naturalHeight / im.naturalWidth);
      const x = c.getContext('2d', { willReadFrequently: true });
      x.drawImage(im, 0, 0, c.width, c.height);
      let data;
      try { data = x.getImageData(0, 0, c.width, c.height).data; } catch (e) { return () => 0; }
      return (fx, fy) => {
        const i = Math.round(Math.min(c.width - 1, Math.max(0, fx * c.width)));
        const j = Math.round(Math.min(c.height - 1, Math.max(0, fy * c.height)));
        return data[(j * c.width + i) * 4 + 3] / 255;
      };
    }

    async function build() {
      const print = await decode(printSrc);
      const ph = print.naturalWidth ? print.naturalHeight / print.naturalWidth : 1.24;
      const inkAt = await sampler(printSrc, 600);
      const texSize = {};
      const sizeOf = async (src) => { if (!texSize[src]) { const t = await decode(src); texSize[src] = t.naturalWidth ? t.naturalHeight / t.naturalWidth : 1; } return texSize[src]; };
      for (const c of cards) {
        const d = c.dataset;
        const px = (+d.printX / 100) * P, py = (+d.printY / 100) * P, pw = (+d.printW / 100) * P;
        const perCm = pw / PRINT_CM;
        const weave = async (src, kind, extra = '') => {
          const tw = TILE_CM[kind] * perCm, th = tw * (await sizeOf(src));
          const bg = `background-image:url(${src});background-size:calc(${tw}px * var(--z)) calc(${th}px * var(--z))`;
          return `<div class="pp-loupe__weave ${extra}" style="${bg}"></div><div class="pp-loupe__weave pp-loupe__weave--hi ${extra}" style="${bg}"></div>`;
        };
        const zones = JSON.parse(d.zones || '[]');
        let zoneHtml = '';
        for (const z of zones) {
          zoneHtml += `<div class="pp-loupe__zone" style="-webkit-mask-image:url(${z.mask});mask-image:url(${z.mask})">`
            + `<div class="pp-loupe__fill" style="background:${z.colour || d.colour}"></div>${await weave(z.tex, z.kind)}</div>`;
        }
        const el = document.createElement('div');
        el.className = 'pp-loupe__w';
        el.innerHTML = `<img class="pp-loupe__wphoto" src="${d.photo}" alt="">`
          + `<div class="pp-loupe__cloth" style="-webkit-mask-image:url(${d.mask});mask-image:url(${d.mask})">`
          + `<div class="pp-loupe__fill" style="background:${d.colour}"></div>`
          + await weave(d.tex, d.fabric)
          + zoneHtml
          + `<img class="pp-loupe__ink" src="${printSrc}" alt="" style="${box(px, py, pw, pw * ph)}">`
          // The weave over the ink only (masked by the print itself), darkening it in
          // the valleys of the knit.
          + `<div class="pp-loupe__over" style="background-image:url(${d.tex});background-size:calc(${TILE_CM[d.fabric] * perCm}px * var(--z)) auto;-webkit-mask-image:url(${printSrc});mask-image:url(${printSrc});${box(px, py, pw, pw * ph)}"></div>`
          + `</div>`;
        world.appendChild(el);
        const zoneAt = [];
        for (const z of zones) zoneAt.push({ at: await sampler(z.mask), label: z.label });
        worlds.set(c, { el, box: [px, py, pw, pw * ph], inkAt, zoneAt, fabric: d.fabricLabel, ink: d.inkLabel });
      }
      const srcs = new Set();
      cards.forEach((c) => { srcs.add(c.dataset.photo); srcs.add(c.dataset.mask); srcs.add(c.dataset.tex);
        JSON.parse(c.dataset.zones || '[]').forEach((z) => { srcs.add(z.mask); srcs.add(z.tex); }); });
      await Promise.all([...srcs].map(decode));
      ready = true;
      section.classList.add('is-armed');
    }

    // What the lens is over: ink, a zone (rib, lining), or the garment's fabric.
    function labelFor(w, u, v) {
      const [bx, by, bw, bh] = w.box;
      if (u > bx && u < bx + bw && v > by && v < by + bh && w.inkAt((u - bx) / bw, (v - by) / bh) > .3) return w.ink;
      for (const z of w.zoneAt) if (z.at(u / P, v / P) > .5) return z.label;
      return w.fabric;
    }

    function show(card) {
      if (active === card) return;
      if (active) worlds.get(active).el.style.display = 'none';
      active = card;
      if (card) worlds.get(card).el.style.display = 'block';
    }

    function place() {
      raf = 0;
      if (!want || !ready) return;
      const now = performance.now();
      const dt = last ? Math.min(64, now - last) : 16;
      last = now;
      if (!pos) pos = { ...want };
      const a = REDUCED ? 1 : 1 - Math.exp(-dt / 55);
      pos.x = lerp(pos.x, want.x, a);
      pos.y = lerp(pos.y, want.y, a);
      const sr = section.getBoundingClientRect();
      lens.style.transform = `translate3d(${pos.x - sr.left}px, ${pos.y - lift - sr.top}px, 0)`;
      const hit = cards.find((c) => { const r = c.getBoundingClientRect(); return pos.x >= r.left && pos.x <= r.right && pos.y >= r.top && pos.y <= r.bottom; });
      if (hit) {
        show(hit);
        const r = hit.getBoundingClientRect();
        const s = r.width / P;
        const z = s * MAG;
        const u = (pos.x - r.left) / s, v = (pos.y - r.top) / s;
        const d = lens.offsetWidth;
        // The world is laid out at this zoom (sizes are calc(... * var(--z))), so it
        // is only ever moved, never scaled: a scaled layer is painted small and
        // stretched, which blurs the print and loses the weave.
        if (z !== lastZ) { world.style.setProperty('--z', z); lastZ = z; }
        world.style.transform = `translate3d(${d / 2 - u * z}px, ${d / 2 - v * z}px, 0)`;
        label.textContent = labelFor(worlds.get(hit), u, v);
        // Bottom right of the lens, kept inside the section on narrow screens.
        const lx = Math.min(pos.x - sr.left + d / 2 - 12, sr.width - label.offsetWidth - 8);
        label.style.transform = `translate3d(${Math.max(8, lx)}px, ${pos.y - lift - sr.top + d / 2 - 26}px, 0)`;
      }
      section.classList.toggle('is-lens', !!hit);
      if (Math.abs(pos.x - want.x) > .3 || Math.abs(pos.y - want.y) > .3) raf = requestAnimationFrame(place);
      else last = 0;
    }
    const go = (x, y, up = 0) => { lift = up; want = { x, y }; if (!raf) raf = requestAnimationFrame(place); };
    const hide = () => { want = null; section.classList.remove('is-lens'); };

    // Any use of the lens by the shopper ends the tour, and stops it ever starting.
    function stopTour() { toured = true; if (tour) { tour.stop = true; tour = null; } }
    async function runTour() {
      const me = tour = { stop: false };
      const at = (i, fx, fy) => { const c = cards[Math.min(i, cards.length - 1)], r = c.getBoundingClientRect(); return [r.left + r.width * fx, r.top + r.height * fy]; };
      const path = [[0, .5, .45], [0, .5, .6], [0, .75, .78], [1, .3, .75], [1, .5, .5], [2, .45, .45], [2, .52, .72]];
      for (const [i, fx, fy] of path) {
        if (me.stop) return;
        go(...at(i, fx, fy));
        await new Promise((r) => setTimeout(r, 1300));
      }
      if (!me.stop) hide();
      tour = null;
    }

    section.addEventListener('pointermove', (e) => {
      if (e.pointerType !== 'mouse') return;
      stopTour();
      go(e.clientX, e.clientY);
    });
    section.addEventListener('pointerleave', (e) => { if (e.pointerType === 'mouse' && !tour) hide(); });
    // A tap (touch or pen) places the lens; a mouse click does nothing extra.
    let lastPointer = '';
    section.addEventListener('pointerdown', (e) => { lastPointer = e.pointerType; });
    section.addEventListener('click', (e) => {
      if (lastPointer === 'mouse') return;
      stopTour();
      if (e.target.closest('[data-pp-loupe-g]')) go(e.clientX, e.clientY, lens.offsetWidth * .6);
      else hide();
    });
    // The lens is placed in page terms; keep it on its spot while the page scrolls.
    const onScroll = () => { if (want) { pos = null; go(want.x, want.y, lift); } };

    const io = new IntersectionObserver(async ([e]) => {
      if (e.isIntersecting) {
        window.addEventListener('scroll', onScroll, { passive: true });
        building = building || build();  // once, however often the observer fires
        await building;
        if (!toured && !REDUCED && e.intersectionRatio > .5) { toured = true; runTour(); }
      } else {
        window.removeEventListener('scroll', onScroll);
        if (tour) { tour.stop = true; tour = null; }
        hide();
      }
    }, { threshold: [0, .55], rootMargin: '300px 0px 0px 0px' });
    io.observe(section.querySelector('.pp-loupe__row'));
  }

  function initAll(root = document) {
    if (!('IntersectionObserver' in window)) return;
    root.querySelectorAll('[data-pp-loupe]:not([data-pp-init])').forEach((s) => { s.dataset.ppInit = '1'; init(s); });
  }
  window.PPLoupe = { init: initAll };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => initAll());
  else initAll();
  document.addEventListener('shopify:section:load', (e) => initAll(e.target));
})();
