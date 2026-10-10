/* Peculiar People: temple → drawing → garments. Drives sections/pp-temple-process.liquid.
   One value p (0 to 1) runs the whole section; the stops are evenly spaced along it:
   photo, drawing, then one stop per garment. Between the first two a pen line wipes the
   drawing across the photo. Between the drawing and the first garment the paper drops
   away, the lines turn to white ink on the fabric and the first garment zooms out from
   its back print (which lines up with the drawing at the print zoom) to the whole
   garment, while the other garments take their places on the ring. After that each
   stop turns the ring one place; past the last garment it keeps turning to the first. */
(() => {
  if (window.PPTempleProcess) return;
  const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const smooth = (x) => x * x * (3 - 2 * x);

  // The drawing's lines on a transparent ground (alpha = how dark the pixel is), in one
  // colour. Blend modes cannot reach the garments under the frame, which has its own
  // stacking context, so these cut-outs stand in for the paper drawing off the photo.
  function cutout(img, v) {
    const c = document.createElement('canvas');
    c.width = img.naturalWidth; c.height = img.naturalHeight;
    const g = c.getContext('2d');
    g.drawImage(img, 0, 0);
    const d = g.getImageData(0, 0, c.width, c.height), px = d.data;
    for (let i = 0; i < px.length; i += 4) {
      const dark = 255 - (px[i] + px[i + 1] + px[i + 2]) / 3;
      px[i] = px[i + 1] = px[i + 2] = v;
      px[i + 3] = Math.min(255, dark * 1.25);
    }
    g.putImageData(d, 0, 0);
    return c.toDataURL('image/png');
  }

  function tween(from, to, ms, fn, done) {
    if (REDUCED) { fn(to); if (done) done(); return () => {}; }
    const t0 = performance.now();
    let stop = false;
    const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
    const frame = (now) => {
      if (stop) return;
      const t = clamp((now - t0) / ms, 0, 1);
      fn(lerp(from, to, ease(t)));
      if (t < 1) requestAnimationFrame(frame); else if (done) done();
    };
    requestAnimationFrame(frame);
    return () => { stop = true; };
  }

  function mount(root) {
    if (root.dataset.ppTpReady) return;
    const stage = root.querySelector('.pp-tp__stage');
    const items = [...root.querySelectorAll('.pp-tp__garment')];
    const photo = root.querySelector('.pp-tp__photo');
    const draw = root.querySelector('.pp-tp__draw');
    const ink = root.querySelector('.pp-tp__ink');
    const range = root.querySelector('.pp-tp__range');
    const stopBtns = [...root.querySelectorAll('.pp-tp__stops button')];
    const nameEl = root.querySelector('.pp-tp__name');
    const pick = root.querySelector('.pp-tp__pick');
    if (!stage || !draw || !items.length || !range) return;
    root.dataset.ppTpReady = '1';

    const n = items.length;
    const hood = items[0].querySelector('img');
    const PRINT = parseFloat(root.dataset.printZoom) || 4.375;
    const SEG = 1 / (n + 1);          // slider distance between stops
    const STEP = 360 / n;             // ring angle between garments
    // Garment i starts at angle i·STEP: 0 is the front, +STEP back-right, -STEP back-left.
    const BASE = items.map((_, i) => { const a = i * STEP; return a > 180 ? a - 360 : a; });
    stopBtns.forEach((b, i) => { b.style.left = `${i * SEG * 100}%`; });

    const lines = { paper: draw.currentSrc || draw.src, black: null };
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.src = lines.paper;
    img.decode().then(() => {
      try {
        lines.black = cutout(img, 18);
        ink.src = cutout(img, 255);
        ink.hidden = false;
      } catch (e) { /* image not readable: the drawing simply fades */ }
      render(p);
    }).catch(() => {});

    function placeRing(R, appear) {
      const wide = stage.clientWidth / stage.clientHeight > 1.2;
      const RX = wide ? 54.8 : 52;  // % of a garment's own width; back slots sit at the stage edges
      let front = 0, best = -2;
      items.forEach((el, i) => {
        const th = (BASE[i] - STEP * R) * Math.PI / 180, c = Math.cos(th), s = Math.sin(th);
        const k = (c + 0.5) / 1.5;  // 1 at the front, 0 at a back slot
        const sc = 0.52 + 0.48 * Math.max(k, -0.2);
        el.style.setProperty('--x', `${(s * RX).toFixed(2)}%`);
        el.style.setProperty('--y', `${(-(1 - sc) * 14).toFixed(2)}%`);
        el.style.setProperty('--s', sc.toFixed(4));
        el.style.setProperty('--z', Math.round(10 + c * 9));
        const vis = i === 0 ? appear.first : appear.rest;
        el.style.setProperty('--o', ((0.72 + 0.28 * clamp(k, 0, 1)) * vis).toFixed(3));
        el.style.pointerEvents = vis > 0.5 ? '' : 'none';
        if (c > best) { best = c; front = i; }
      });
      items.forEach((el, i) => {
        el.setAttribute('aria-current', String(i === front));
        el.tabIndex = i === front || appear.rest < 0.5 ? -1 : 0;
      });
      return front;
    }

    let p = 0;
    function render(v, extra = 0) {
      p = clamp(v, 0, 1);
      const q = clamp(p / SEG, 0, 1);                              // photo → drawing wipe
      const t = clamp((p - SEG) / SEG, 0, 1);                      // drawing → first garment
      const R = clamp((p - 2 * SEG) / SEG, 0, n - 1) + extra;      // ring turns
      root.style.setProperty('--pp-tp-q', q);
      root.style.setProperty('--pp-tp-penop', q > 0 && q < 1 ? 1 : 0);
      const a = smooth(clamp(t / 0.3, 0, 1));
      const hs = Math.exp(lerp(Math.log(PRINT), 0, t));
      if (hood) hood.style.transform = `scale(${hs})`;
      if (photo) photo.style.opacity = t > 0 ? 0 : 1;
      draw.style.opacity = 1 - a;
      // off the photo the paper drops away: the same lines on a transparent ground
      const want = t > 0 && lines.black ? lines.black : lines.paper;
      if (draw.getAttribute('src') !== want) draw.src = want;
      draw.style.transform = ink.style.transform = `scale(${hs / PRINT})`;
      ink.style.opacity = Math.min(a, 1 - smooth(clamp((t - 0.4) / 0.45, 0, 1)));
      const rest = clamp((t - 0.7) / 0.3, 0, 1);  // the other garments take their places as the first lands
      const front = placeRing(R, { first: a, rest });
      const ready = t >= 1;
      const g = items[front].dataset;
      nameEl.textContent = ready ? g.name : '';
      pick.href = g.url || '#';
      pick.classList.toggle('is-off', !ready || !g.url);
      pick.tabIndex = ready && g.url ? 0 : -1;
      pick.setAttribute('aria-hidden', String(!(ready && g.url)));
      const idx = ready ? 2 + front : Math.round(p / SEG);
      stopBtns.forEach((b, i) => b.classList.toggle('is-on', i === idx && Math.abs(p - i * SEG) < 0.01));
      range.value = Math.round(p * 1000);
      range.style.setProperty('--fill', `${p * 100}%`);
    }

    let cancel = () => {};
    const goTo = (target, ms = 500) => {
      cancel();
      cancel = tween(p, target, ms * Math.min(1, Math.abs(target - p) / SEG + 0.3), render);
    };
    const snap = () => goTo(Math.round(p / SEG) * SEG, 420);
    // Past the last garment the ring turns one more place and the slider quietly jumps to the
    // matching stop (the ring repeats every n places); the same backwards from the first garment.
    function step(dir) {
      if (p < 2 * SEG - 0.001) return goTo(Math.min(1, Math.round(p / SEG) * SEG + dir * SEG));
      if (dir > 0 && p > 1 - 0.001) {
        cancel(); cancel = tween(0, 1, 650, (e) => render(1, e), () => render(2 * SEG)); return;
      }
      if (dir < 0 && p < 2 * SEG + 0.001) {
        cancel(); cancel = tween(0, 1, 650, (e) => render(2 * SEG, -e), () => render(1)); return;
      }
      goTo(Math.round(p / SEG) * SEG + dir * SEG, 650);
    }

    range.addEventListener('input', () => { cancel(); render(range.value / 1000); });
    range.addEventListener('change', snap);
    range.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowRight' || e.key === 'ArrowUp') { e.preventDefault(); step(1); }
      if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
        e.preventDefault();
        if (Math.abs(p - 2 * SEG) < 0.001) goTo(SEG); else step(-1);
      }
    });
    stopBtns.forEach((b, i) => b.addEventListener('click', () => goTo(i * SEG, 700)));

    // Dragging the picture works like the slider; a tap on a garment at the back brings it forward.
    let x0 = null, p0 = 0, moved = false;
    stage.addEventListener('pointerdown', (e) => { x0 = e.clientX; p0 = p; moved = false; });
    stage.addEventListener('pointermove', (e) => {
      if (x0 == null) return;
      const dx = e.clientX - x0;
      if (!moved && Math.abs(dx) < 6) return;
      if (!moved) { moved = true; cancel(); stage.classList.add('is-drag'); stage.setPointerCapture(e.pointerId); }
      render(p0 + (dx / stage.clientWidth) * SEG * 1.6);
    });
    const end = () => {
      if (x0 == null) return;
      x0 = null; stage.classList.remove('is-drag');
      if (moved) snap();
      setTimeout(() => { moved = false; });
    };
    stage.addEventListener('pointerup', end);
    stage.addEventListener('pointercancel', end);
    items.forEach((el, i) => el.addEventListener('click', () => {
      if (moved || el.getAttribute('aria-current') === 'true') return;
      const R = clamp((p - 2 * SEG) / SEG, 0, n - 1);
      const th = (((BASE[i] - STEP * R) % 360) + 360) % 360;
      step(th < 180 ? 1 : -1);  // back-right comes forward with a forward turn, back-left with a backward one
    }));

    new ResizeObserver(() => render(p)).observe(stage);
    root.classList.add('is-ready');
    render(SEG * 0.36);  // at rest partway into the wipe, so the first frame shows both
  }

  function init(scope = document) {
    if (scope.matches && scope.matches('[data-pp-tp]')) mount(scope);
    scope.querySelectorAll('[data-pp-tp]').forEach(mount);
  }
  window.PPTempleProcess = { init };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => init());
  else init();
  document.addEventListener('shopify:section:load', (e) => init(e.target));
})();
