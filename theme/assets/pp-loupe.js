/* Peculiar People homepage: the loupe (sections/pp-loupe.liquid). Styles: pp-loupe.css.

   For each garment a macro "world" is built once, in the photo's own pixel frame:
   the photo, then the cloth (garment colour + weave, clipped to the garment's
   outline mask), the full-size print where it sits, and the weave again over the
   ink. The lens shows that world scaled about the point under it, so the print is
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
    const MAG = +section.dataset.mag || 7;
    const printSrc = section.dataset.print;
    const worlds = new Map();
    let building = null;
    let ready = false, active = null, want = null, pos = null, raf = 0, last = 0, tour = null, toured = false;

    async function build() {
      const print = await decode(printSrc);
      const ph = print.naturalWidth ? print.naturalHeight / print.naturalWidth : 1.24;
      for (const c of cards) {
        const d = c.dataset;
        const px = (+d.printX / 100) * P, py = (+d.printY / 100) * P, pw = (+d.printW / 100) * P;
        const el = document.createElement('div');
        el.className = 'pp-loupe__w';
        el.innerHTML = `<img class="pp-loupe__wphoto" src="${d.photo}" alt="">`
          + `<div class="pp-loupe__cloth" style="-webkit-mask-image:url(${d.mask});mask-image:url(${d.mask})">`
          + `<div class="pp-loupe__fill" style="background:${d.colour}"></div>`
          + `<div class="pp-loupe__weave" style="background-image:url(${d.tex})"></div>`
          + `<img class="pp-loupe__ink" src="${printSrc}" alt="" style="left:${px}px;top:${py}px;width:${pw}px;height:${pw * ph}px">`
          + `<div class="pp-loupe__weave pp-loupe__weave--over" style="background-image:url(${d.tex})"></div>`
          + `</div>`;
        world.appendChild(el);
        worlds.set(c, { el, box: [px, py, pw, pw * ph], fabric: d.fabricLabel, ink: d.inkLabel });
      }
      await Promise.all([...cards.map((c) => decode(c.dataset.photo)), ...cards.map((c) => decode(c.dataset.mask)),
        ...new Set(cards.map((c) => c.dataset.tex))].map((p) => (typeof p === 'string' ? decode(p) : p)));
      ready = true;
      section.classList.add('is-armed');
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
      lens.style.transform = `translate3d(${pos.x - sr.left}px, ${pos.y - sr.top}px, 0)`;
      const hit = cards.find((c) => { const r = c.getBoundingClientRect(); return pos.x >= r.left && pos.x <= r.right && pos.y >= r.top && pos.y <= r.bottom; });
      if (hit) {
        show(hit);
        const r = hit.getBoundingClientRect();
        const s = r.width / P;
        const z = s * MAG;
        const u = (pos.x - r.left) / s, v = (pos.y - r.top) / s;
        const d = lens.offsetWidth;
        world.style.transform = `translate3d(${d / 2 - u * z}px, ${d / 2 - v * z}px, 0) scale(${z})`;
        const w = worlds.get(hit), [bx, by, bw, bh] = w.box;
        label.textContent = u > bx && u < bx + bw && v > by && v < by + bh ? w.ink : w.fabric;
        label.style.transform = `translate3d(${pos.x - sr.left + d / 2 - 12}px, ${pos.y - sr.top + d / 2 - 26}px, 0)`;
      }
      section.classList.toggle('is-lens', !!hit);
      if (Math.abs(pos.x - want.x) > .3 || Math.abs(pos.y - want.y) > .3) raf = requestAnimationFrame(place);
      else last = 0;
    }
    const go = (x, y) => { want = { x, y }; if (!raf) raf = requestAnimationFrame(place); };
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
    section.addEventListener('click', (e) => {
      if (matchMedia('(hover: hover)').matches) return;
      stopTour();
      if (e.target.closest('[data-pp-loupe-g]')) go(e.clientX, e.clientY - lens.offsetWidth * .6);
      else hide();
    });
    // The lens is placed in page terms; keep it on its spot while the page scrolls.
    const onScroll = () => { if (want) { pos = null; go(want.x, want.y); } };

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
