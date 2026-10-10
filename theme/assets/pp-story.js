/* Peculiar People homepage story sections. Styles: pp-story.css.
   - Conversation (sections/pp-conversation.liquid): scroll picks which moment is
     showing; the photo and line transitions run on CSS timing, so nothing trails
     the scrollbar.
   - Look closer (sections/pp-look-closer.liquid): a pinned zoom through a chain of
     close-ups, drawn with transforms on stacked photos.
   Work only happens while a section is on screen: a scroll listener is attached
   when it comes into view and removed when it leaves, and a frame is only drawn
   when the position has moved. Nothing is armed under reduced motion or without
   this script, so both sections fall back to a complete, still layout.
   Re-initialises in the theme editor. */
(() => {
  if (window.PPStory) return;

  const reducedQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const smooth = (a, b, t) => { const x = clamp((t - a) / (b - a), 0, 1); return x * x * (3 - 2 * x); };
  const cleanups = new WeakMap();

  /* Calls onFrame(progress 0..1 through the pinned stretch) whenever it changes,
     and only while the track is near the viewport. tau > 0 eases toward the scroll
     position over that many ms, to round off the steps of a mouse wheel. */
  function scrubber(track, sticky, onFrame, tau = 0) {
    let travel = 1, raf = 0, current = -1, lastT = 0, near = false;

    const read = () => clamp(-track.getBoundingClientRect().top / travel, 0, 1);
    function tick(now) {
      raf = 0;
      const target = read();
      const dt = lastT ? Math.min(64, now - lastT) : 16;
      lastT = now;
      let next = current < 0 || !tau ? target : lerp(current, target, 1 - Math.exp(-dt / tau));
      if (Math.abs(target - next) < 0.0004) next = target;
      if (next !== current) { current = next; onFrame(current); }
      if (current !== target) raf = requestAnimationFrame(tick);
      else lastT = 0;
    }
    const kick = () => { if (!raf) raf = requestAnimationFrame(tick); };
    const size = () => {
      travel = Math.max(1, track.offsetHeight - sticky.offsetHeight);
      current = -1;
      kick();
    };

    const io = new IntersectionObserver(([e]) => {
      near = e.isIntersecting;
      if (near) window.addEventListener('scroll', kick, { passive: true });
      else window.removeEventListener('scroll', kick);
      current = -1;  // settle exactly on wherever the scroll left it
      kick();
    }, { rootMargin: '50% 0px' });
    io.observe(track);
    const ro = new ResizeObserver(size);
    ro.observe(track);
    ro.observe(sticky);
    size();

    return {
      // Theme editor: bring a given point of the stretch on screen.
      jumpTo(p) {
        const top = track.getBoundingClientRect().top + window.scrollY;
        window.scrollTo({ top: top + clamp(p, 0, 1) * travel, behavior: 'instant' });
      },
      stop() {
        io.disconnect();
        ro.disconnect();
        window.removeEventListener('scroll', kick);
        if (raf) cancelAnimationFrame(raf);
      },
    };
  }

  /* ---------- Conversation ---------- */
  function initConversation(section) {
    const moments = [...section.querySelectorAll('[data-pp-moment]')];
    if (reducedQuery.matches || !moments.length) return;
    section.classList.add('is-armed');
    const n = moments.length;
    let active = -1;

    const show = (i) => {
      if (i === active) return;
      active = i;
      moments.forEach((m, j) => {
        m.classList.toggle('is-active', j === i);
        m.classList.toggle('is-shown', j <= i);
      });
    };

    const scrub = scrubber(
      section.querySelector('.pp-story__track'),
      section.querySelector('.pp-story__sticky'),
      (p) => show(Math.min(n - 1, Math.floor(p * n))),
    );
    show(0);

    const onSelect = (e) => {
      const i = moments.indexOf(e.target.closest('[data-pp-moment]'));
      if (i >= 0) scrub.jumpTo((i + 0.5) / n);
    };
    section.addEventListener('shopify:block:select', onSelect);
    cleanups.set(section, () => {
      scrub.stop();
      section.removeEventListener('shopify:block:select', onSelect);
    });
  }

  /* ---------- Look closer ---------- */
  function initCloser(section) {
    const steps = [...section.querySelectorAll('[data-pp-layer]')].map((el) => {
      const [x, y, size] = (el.dataset.next || '').split(',').map(parseFloat);
      return {
        el,
        photo: el.querySelector('.pp-closer__photo'),
        fx: (parseFloat(el.dataset.focusX) || 50) / 100,
        fy: (parseFloat(el.dataset.focusY) || 50) / 100,
        sq: size > 0 ? { x: x / 100, y: y / 100, s: size / 100 } : null,
      };
    });
    if (reducedQuery.matches || steps.length < 2 || steps.some((s) => !s.photo)) return;
    section.classList.add('is-armed');

    const stage = section.querySelector('.pp-story__sticky');
    const n = steps.length;
    let W = 1, H = 1, L = 1, caption = -1, lastD = 0;

    // Each photo is an L x L square covering the stage. Every square is a close-up
    // of one inside the photo before, so all of them are laid out in that first
    // photo's frame; offset() slides the frame so a photo's focus point stays on
    // screen where the stage crops it.
    const offset = (f, view) => clamp(view / 2 - f * L, view - L, 0);

    // The zoom from photo i into its square: scale k^t about the fixed point of the
    // map that carries the square onto the whole photo, so the square arrives
    // exactly where photo i+1 sits.
    steps.forEach((s) => {
      if (!s.sq) return;
      const k = 1 / s.sq.s;
      const fixed = (c) => (k * c - 0.5) / (k - 1);
      s.k = k;
      s.px = fixed(s.sq.x + s.sq.s / 2);
      s.py = fixed(s.sq.y + s.sq.s / 2);
    });

    const place = (el, tx, ty, sc, op) => {
      el.style.transform = `translate3d(${tx}px, ${ty}px, 0) scale(${sc})`;
      el.style.opacity = op;
      el.style.visibility = op > 0 ? 'visible' : 'hidden';
    };

    const setCaption = (i) => {
      if (i === caption) return;
      caption = i;
      steps.forEach((s, j) => s.el.classList.toggle('is-active', j === i));
    };

    function draw(d) {
      lastD = d;
      const i = Math.min(Math.floor(d), n - 2);
      const raw = clamp(d - i, 0, 1);
      // Mostly even zoom speed, with a little ease at each end for the words.
      const t = lerp(raw, smooth(0, 1, raw), 0.35);
      const a = steps[i], b = steps[i + 1];
      const ox = lerp(offset(a.fx, W), offset(b.fx, W), smooth(0, 1, raw));
      const oy = lerp(offset(a.fy, H), offset(b.fy, H), smooth(0, 1, raw));
      const sc = Math.pow(a.k, t);

      steps.forEach((s, j) => { if (j !== i && j !== i + 1) place(s.photo, 0, 0, 1, 0); });
      place(a.photo, ox + a.px * (1 - sc) * L, oy + a.py * (1 - sc) * L, sc, 1);
      place(
        b.photo,
        ox + (sc * a.sq.x + a.px * (1 - sc)) * L,
        oy + (sc * a.sq.y + a.py * (1 - sc)) * L,
        sc * a.sq.s,
        smooth(0.55, 0.92, raw),
      );
      setCaption(Math.min(n - 1, Math.floor(d + 0.15)));
    }

    // Short holds at each end so the first and last words have a moment.
    const toD = (p) => clamp((p - 0.06) / 0.8, 0, 1) * (n - 1);
    const size = () => {
      W = stage.clientWidth;
      H = stage.clientHeight;
      L = Math.max(W, H);
      section.style.setProperty('--pp-l', `${L}px`);
      draw(lastD);
    };
    const ro = new ResizeObserver(size);
    ro.observe(stage);
    size();

    const scrub = scrubber(section.querySelector('.pp-story__track'), stage, (p) => draw(toD(p)), 60);

    const onSelect = (e) => {
      const i = steps.findIndex((s) => s.el.contains(e.target));
      if (i >= 0) scrub.jumpTo(0.06 + (i / (n - 1)) * 0.8);
    };
    section.addEventListener('shopify:block:select', onSelect);
    cleanups.set(section, () => {
      scrub.stop();
      ro.disconnect();
      section.removeEventListener('shopify:block:select', onSelect);
    });
  }

  function init(root = document) {
    if (!('IntersectionObserver' in window) || !('ResizeObserver' in window)) return;
    root.querySelectorAll('[data-pp-convo]:not([data-pp-init])').forEach((s) => {
      s.dataset.ppInit = '1';
      initConversation(s);
    });
    root.querySelectorAll('[data-pp-closer]:not([data-pp-init])').forEach((s) => {
      s.dataset.ppInit = '1';
      initCloser(s);
    });
  }

  window.PPStory = { init };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => init());
  else init();
  document.addEventListener('shopify:section:load', (e) => init(e.target));
  document.addEventListener('shopify:section:unload', (e) => {
    e.target.querySelectorAll('[data-pp-convo], [data-pp-closer]').forEach((s) => {
      const off = cleanups.get(s);
      if (off) off();
    });
  });
})();
