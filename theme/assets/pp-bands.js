/* Peculiar People: the temple and map bands in sections/pp-spec-overlay.liquid.
   Each band is a plain horizontal scroll area holding its list twice. This script
   drifts it slowly (temples to the right, maps to the left) by setting scrollLeft,
   and wraps by one list width so the loop never ends. A real scroll area rather than
   a CSS transform: phones drop parts of a very wide moving layer, which made
   drawings half vanish, and a scroll area gives swiping and flinging for free.
   The drift stops while a finger, mouse or keyboard focus is on the band and starts
   again a few seconds after. Under reduced motion nothing moves and the band is a
   single list to swipe by hand. On desktop a mouse can drag the band too (a scroll
   area only scrolls by touch, trackpad or keys); a drag never counts as a click. */
(() => {
  const IDLE_MS = 2500;
  const reduced = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function initBand(band) {
    const view = band.querySelector('[data-pp-band-view]');
    const first = band.querySelector('[data-pp-band-list]');
    const copy = band.querySelector('[data-pp-band-copy]');
    if (!view || !first || !copy) return;
    initDrag(view);
    if (reduced()) return;

    band.classList.add('is-looping');
    copy.querySelectorAll('a').forEach((a) => { a.tabIndex = -1; });

    const dir = band.dataset.dir === 'right' ? -1 : 1; // right: content moves right, scrollLeft falls
    const seconds = parseFloat(band.dataset.seconds) || 3;
    const count = first.children.length || 1;

    let half = 0;
    let speed = 0;
    let pos = 0;
    let set = -1; // the scrollLeft this script last wrote
    let last = 0;
    let hold = 0;
    let touching = false;
    let visible = false;

    const measure = () => {
      half = copy.offsetLeft - first.offsetLeft;
      speed = half / (count * seconds);
    };
    const wrap = (x) => {
      if (half <= 0) return x;
      while (x >= half) x -= half;
      while (x < 0) x += half;
      return x;
    };
    const write = (x) => {
      view.scrollLeft = x;
      set = view.scrollLeft;
    };
    const rest = () => { hold = performance.now() + IDLE_MS; };

    measure();
    pos = half > 0 ? half / 2 : 0;
    write(pos);

    view.addEventListener('touchstart', () => { touching = true; }, { passive: true });
    view.addEventListener('touchend', () => { touching = false; rest(); }, { passive: true });
    view.addEventListener('touchcancel', () => { touching = false; rest(); }, { passive: true });
    view.addEventListener('pointerenter', (e) => { if (e.pointerType === 'mouse') touching = true; });
    view.addEventListener('pointerleave', (e) => { if (e.pointerType === 'mouse') { touching = false; rest(); } });
    view.addEventListener('wheel', rest, { passive: true });
    view.addEventListener('focusin', () => { touching = true; });
    view.addEventListener('focusout', () => { touching = false; rest(); });

    // A scroll this script did not write is the visitor (a swipe or its fling).
    view.addEventListener('scroll', () => {
      const x = view.scrollLeft;
      if (Math.abs(x - set) <= 1) return;
      rest();
      if (half > 0 && !touching) {
        if (x < 2) write(x + half);
        else if (x > half * 2 - view.clientWidth - 2) write(x - half);
      }
      pos = view.scrollLeft;
      set = pos;
    }, { passive: true });

    if ('IntersectionObserver' in window) {
      new IntersectionObserver((entries) => {
        visible = entries.some((e) => e.isIntersecting);
      }).observe(view);
    } else {
      visible = true;
    }
    if ('ResizeObserver' in window) {
      new ResizeObserver(() => {
        measure();
        pos = wrap(view.scrollLeft);
      }).observe(first);
    }

    const frame = (t) => {
      requestAnimationFrame(frame);
      const dt = last ? Math.min((t - last) / 1000, 0.05) : 0;
      last = t;
      if (!visible || touching || t < hold || document.hidden || half <= 0) return;
      pos = wrap(pos + dir * speed * dt);
      write(pos);
    };
    requestAnimationFrame(frame);
  }

  function initDrag(view) {
    let startX = 0;
    let startLeft = 0;
    let down = false;
    let dragged = false;
    view.addEventListener('pointerdown', (e) => {
      if (e.pointerType !== 'mouse' || e.button !== 0) return;
      down = true;
      dragged = false;
      startX = e.clientX;
      startLeft = view.scrollLeft;
    });
    view.addEventListener('pointermove', (e) => {
      if (!down) return;
      const dx = e.clientX - startX;
      if (!dragged && Math.abs(dx) < 5) return;
      if (!dragged) {
        dragged = true;
        view.classList.add('is-dragging');
        view.setPointerCapture(e.pointerId);
      }
      view.scrollLeft = startLeft - dx;
    });
    const up = () => {
      down = false;
      view.classList.remove('is-dragging');
    };
    view.addEventListener('pointerup', up);
    view.addEventListener('pointercancel', up);
    view.addEventListener('click', (e) => {
      if (dragged) { e.preventDefault(); e.stopPropagation(); dragged = false; }
    }, true);
    view.addEventListener('dragstart', (e) => e.preventDefault());
  }

  function init(root = document) {
    root.querySelectorAll('[data-pp-band]:not([data-pp-band-init])').forEach((band) => {
      band.dataset.ppBandInit = '1';
      initBand(band);
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => init());
  else init();
  document.addEventListener('shopify:section:load', (e) => init(e.target));
})();
