/* Peculiar People: pen-drawn temples.
   Drives sections/pp-temple-showcase.liquid (homepage) and
   sections/pp-temple-drawing.liquid (product page). Data files:
   pp-temple-<slug>.json (pen strokes in draw order, their lengths, pen width, art
   box, city line) and pp-temple-<slug>.webp (the finished art). Version 2 stroke
   files come from scripts/pen_strokes.py, which orders the strokes the way a
   person draws (outline, inner structure, openings, small marks) and gives each
   stroke its own pen width (`widths`); version 1 files used one width for all.
   The strokes are a MASK over the finished art, so a shopper always ends up
   looking at the stored drawing; the last 600 ms fades the unmasked art in to
   cover hairline edges the pen does not reach. The mask and the art are drawn on
   a canvas (see mount()). */
(() => {
  if (window.PPPen) return;

  const NS = 'http://www.w3.org/2000/svg';
  const DRAW_MS = 13000;  // pen down to pen up, one temple, at one steady speed
                          // (the homepage showcase sets its own: data-draw-ms)
  const HOLD_MS = 3000;   // finished drawing stays up once the city line is complete
  const FADE_MS = 700;    // showcase cross-fade between temples
  const EXACT_MS = 600;   // unmasked art fades in at the end
  const LETTER_MS = 45;
  const RETRY_MS = 4000;  // after a failed download that was not a missing file
  const MAX_TRIES = 3;    // then give up: a half-uploaded drawing must not retry forever
  const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const cache = new Map();

  // Element.replaceChildren is missing on iOS 13 and older; this does the same job.
  function setKids(el, kids) {
    el.textContent = '';
    kids.forEach((k) => el.appendChild(k));
  }

  // JSON and image together. A failure is not cached, so a dropped connection is retried
  // later; err.missing marks a 404, the only failure treated as "no drawing exists".
  function load(item) {
    if (!cache.has(item.json)) {
      const p = Promise.all([
        fetch(item.json).then((r) => {
          if (!r.ok) {
            const err = new Error(`pp-pen: ${r.status} ${item.json}`);
            err.missing = r.status === 404;
            throw err;
          }
          return r.json();
        }),
        new Promise((resolve, reject) => {
          const img = new Image();
          img.onload = () => resolve(img);
          img.onerror = () => reject(new Error(`pp-pen: image failed ${item.img}`));
          img.src = item.img;
        }),
      ]).then(([data, img]) => { data.__img = img; return data; });
      p.catch(() => cache.delete(item.json));
      cache.set(item.json, p);
    }
    return cache.get(item.json);
  }

  // Drop every cached drawing except these items (the showcase keeps only the one on
  // screen and the next, so a long visit does not keep all of them in memory).
  function forgetExcept(keep) {
    const urls = new Set(keep.filter(Boolean).map((k) => k.json));
    [...cache.keys()].forEach((url) => { if (!urls.has(url)) cache.delete(url); });
  }

  // The drawing is painted on a canvas (9 October 2026; it was an SVG mask, which
  // re-rendered every stroke on every frame and dropped to ~30 fps on the 11,800-line
  // Salt Lake City map). Each frame paints only the new length of pen line onto an
  // offscreen MASK canvas, then shows the finished art through that mask in one
  // composite, so the cost no longer grows with the number of strokes.
  function mount(artEl, data, img) {
    const [x, y, w, h] = data.box;
    const view = document.createElement('canvas');
    view.setAttribute('aria-hidden', 'true');
    const mask = document.createElement('canvas');
    const exact = new Image();
    exact.className = 'pp-pen__exact';
    exact.alt = '';
    exact.src = img.src;
    // A hidden path, used only to find the pen tip along the current stroke.
    const probeSvg = document.createElementNS(NS, 'svg');
    probeSvg.setAttribute('aria-hidden', 'true');
    probeSvg.setAttribute('class', 'pp-pen__probe');
    const probe = document.createElementNS(NS, 'path');
    probeSvg.appendChild(probe);
    setKids(artEl, [view, exact, probeSvg]);

    const strokes = data.strokes.map((d) => new Path2D(d));
    const widths = data.widths || [];
    const vctx = view.getContext('2d');
    const mctx = mask.getContext('2d');
    const m = { scale: 1, ox: 0, oy: 0, dpr: 1 };

    // Size both canvases to the box on screen (the art is fitted inside it, centred,
    // like an SVG's default preserveAspectRatio) and set the art-to-pixel transform.
    function size() {
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      const cw = Math.max(1, Math.round(artEl.clientWidth * dpr));
      const ch = Math.max(1, Math.round(artEl.clientHeight * dpr));
      const changed = view.width !== cw || view.height !== ch;
      if (changed) { view.width = mask.width = cw; view.height = mask.height = ch; }
      m.scale = Math.min(cw / w, ch / h);
      m.ox = (cw - w * m.scale) / 2 - x * m.scale;
      m.oy = (ch - h * m.scale) / 2 - y * m.scale;
      m.dpr = dpr;
      return changed;
    }
    function pen(ctx, i) {
      ctx.setTransform(m.scale, 0, 0, m.scale, m.ox, m.oy);
      ctx.lineWidth = widths[i] || data.penWidth;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.strokeStyle = '#fff';
    }
    // Stroke i from `from` to `to` along its length, onto the mask.
    function paint(i, from, to) {
      if (to <= from) return;
      pen(mctx, i);
      const L = data.lens[i];
      if (from <= 0 && to >= L) mctx.setLineDash([]);
      else { mctx.setLineDash([to - from, L + to]); mctx.lineDashOffset = -from; }
      mctx.stroke(strokes[i]);
    }
    function clearMask() {
      mctx.setTransform(1, 0, 0, 1, 0, 0);
      mctx.clearRect(0, 0, mask.width, mask.height);
    }
    // The art, shown only where the mask has ink, plus the pen tip.
    function compose(tipAt) {
      vctx.setTransform(1, 0, 0, 1, 0, 0);
      vctx.globalCompositeOperation = 'source-over';
      vctx.clearRect(0, 0, view.width, view.height);
      vctx.setTransform(m.scale, 0, 0, m.scale, m.ox, m.oy);
      vctx.drawImage(img, x, y, w, h);
      vctx.setTransform(1, 0, 0, 1, 0, 0);
      vctx.globalCompositeOperation = 'destination-in';
      vctx.drawImage(mask, 0, 0);
      vctx.globalCompositeOperation = 'source-over';
      if (tipAt) {
        const px = tipAt.x * m.scale + m.ox, py = tipAt.y * m.scale + m.oy;
        vctx.fillStyle = 'rgba(255, 255, 255, .2)';
        vctx.beginPath(); vctx.arc(px, py, data.penWidth * 1.6 * m.scale, 0, Math.PI * 2); vctx.fill();
        vctx.fillStyle = '#fff';
        vctx.beginPath(); vctx.arc(px, py, data.penWidth * 0.55 * m.scale, 0, Math.PI * 2); vctx.fill();
      }
    }
    function tipOf(i, along) {
      if (probe.dataset.i !== String(i)) { probe.setAttribute('d', data.strokes[i]); probe.dataset.i = String(i); }
      return probe.getPointAtLength(along);
    }
    return { size, paint, clearMask, compose, tipOf, exact };
  }

  // Resolves once the last letter has faded in.
  function typeCity(cityEl, text, live) {
    const letters = [...text].map((c) => {
      const s = document.createElement('span');
      s.textContent = c === ' ' ? ' ' : c;
      return s;
    });
    setKids(cityEl, letters);
    if (REDUCED) {
      letters.forEach((s) => s.classList.add('is-on'));
      return Promise.resolve();
    }
    letters.forEach((s, i) => setTimeout(() => live() && s.classList.add('is-on'), i * LETTER_MS));
    return wait(letters.length * LETTER_MS + 250);
  }

  async function draw(stage, data, imgUrl, live, drawMs = DRAW_MS) {
    const cityEl = stage.querySelector('.pp-pen__city');
    setKids(cityEl, []);
    const artEl = stage.querySelector('.pp-pen__art');
    const c = mount(artEl, data, data.__img);
    if (REDUCED) {
      c.exact.classList.add('is-instant', 'is-on');
      await typeCity(cityEl, data.city, live);
      return;
    }
    const lens = data.lens;
    const cum = [0];
    for (const l of lens) cum.push(cum[cum.length - 1] + l);
    const total = cum[cum.length - 1];
    c.size();
    // Pen state: strokes before i are whole on the mask, stroke i is painted up to
    // `done` along its length.
    let i = 0;
    let done = 0;
    // A resize clears the canvases: repaint what has been drawn so far.
    const ro = new ResizeObserver(() => {
      if (!c.size()) return;
      c.clearMask();
      for (let k = 0; k < i; k++) c.paint(k, 0, lens[k]);
      if (i < lens.length) c.paint(i, 0, done);
      c.compose(null);
    });
    ro.observe(artEl);
    const t0 = performance.now();
    await new Promise((finish) => {
      const frame = (now) => {
        if (!live()) return finish();
        const progress = Math.min(1, (now - t0) / drawMs);
        const target = progress * total;  // steady pen: no speeding up or slowing down
        while (i < lens.length && cum[i + 1] <= target) {
          c.paint(i, done, lens[i]);
          i++;
          done = 0;
        }
        let tip = null;
        if (i < lens.length) {
          const along = target - cum[i];
          if (along > done) {
            c.paint(i, done, along);
            done = along;
            tip = c.tipOf(i, along);
          }
        }
        c.compose(progress < 1 ? tip : null);
        if (progress < 1) requestAnimationFrame(frame); else finish();
      };
      requestAnimationFrame(frame);
    });
    ro.disconnect();
    if (!live()) return;
    c.exact.classList.add('is-on');
    await wait(EXACT_MS);
    if (live()) await typeCity(cityEl, data.city, live);
  }

  function whenVisible(target, onChange) {
    new IntersectionObserver((entries) => entries.forEach((e) => onChange(e.isIntersecting)),
      { rootMargin: '200px 0px' }).observe(target);
  }

  // Product band: draw, hold, redraw while on screen. No drawing file: remove the band.
  function initBand(section) {
    const stage = section.querySelector('.pp-pen');
    const item = { json: section.dataset.json, img: section.dataset.img };
    let visible = false;
    let run = 0;
    let running = false;
    let finished = false;
    let failures = 0;
    const start = async () => {
      if (running || finished) return;
      running = true;
      const mine = ++run;
      const live = () => visible && run === mine;
      try {
        let data;
        try {
          data = await load(item);
        } catch (err) {
          console.warn(err);
          if (err.missing || ++failures >= MAX_TRIES) {  // no usable drawing: remove the band
            finished = true;
            section.remove();
          } else {  // a bad connection: stay hidden and try again shortly
            await wait(RETRY_MS);
          }
          return;
        }
        section.classList.add('is-ready');
        while (live()) {
          await draw(stage, data, item.img, live);
          if (REDUCED) { finished = true; break; }
          if (live()) await wait(HOLD_MS);
        }
      } catch (err) {
        // The drawing itself would not draw: take the band away rather than retry it.
        finished = true;
        section.remove();
        console.warn(err);
      } finally {
        running = false;
        if (visible && !finished) start();
      }
    };
    whenVisible(section, (v) => { visible = v; if (v) start(); else run++; });
  }

  // Homepage showcase: each drawing in turn (temples and city maps). Entries whose
  // files are missing are dropped.
  function initShowcase(section) {
    const drawMs = (+section.dataset.drawSeconds || DRAW_MS / 1000) * 1000;
    const stage = section.querySelector('.pp-pen');
    const items = [...section.querySelectorAll('[data-pp-pen-item]')]
      .map((n) => ({ json: n.dataset.json, img: n.dataset.img }));
    // How many temples are still in the cycle (read by the harness self-test).
    const setCount = () => { section.dataset.ppTemples = String(items.length); };
    setCount();
    let idx = 0;
    let visible = false;
    let run = 0;
    let running = false;
    let broken = false;
    if (items.length) load(items[0]).catch(() => {});  // above the fold: fetch now
    const start = async () => {
      if (running || broken) return;
      running = true;
      const mine = ++run;
      const live = () => visible && run === mine;
      try {
        while (live() && items.length) {
          idx %= items.length;
          const item = items[idx];
          let data;
          try {
            data = await load(item);
          } catch (err) {
            console.warn(err);
            item.failures = (item.failures || 0) + 1;
            if (err.missing || item.failures >= MAX_TRIES) items.splice(idx, 1);  // drop it for good
            else { idx++; await wait(RETRY_MS); }  // bad connection: move on, retry next lap
            continue;
          }
          item.failures = 0;  // only failures in a row count toward giving up
          if (!live()) break;
          setCount();
          stage.classList.remove('is-faded');
          // Only the drawing on screen and the one after it are kept in memory.
          const next = items.length > 1 ? items[(idx + 1) % items.length] : null;
          forgetExcept([item, next]);
          await draw(stage, data, item.img, live, drawMs);
          // The next drawing downloads once this one is drawn, not alongside it, so
          // the first one has the connection to itself on a slow phone.
          if (next && live()) load(next).catch(() => {});
          if (!live()) break;
          await wait(HOLD_MS);
          if (!live() || items.length < 2) break;  // a single temple just stays drawn
          stage.classList.add('is-faded');
          await wait(FADE_MS);
          idx++;
        }
        if (!items.length) section.querySelector('.pp-showcase__stage').hidden = true;
      } catch (err) {
        // Anything unexpected: stop and hide the drawing rather than retrying at once,
        // which would spin without ever letting the page repaint.
        broken = true;
        section.querySelector('.pp-showcase__stage').hidden = true;
        console.warn(err);
      } finally {
        running = false;
        if (visible && !broken && items.length > 1) start();
      }
    };
    whenVisible(section, (v) => { visible = v; if (v) start(); else run++; });
  }

  function init(root = document) {
    root.querySelectorAll('[data-pp-pen-band]:not([data-pp-pen-init])').forEach((s) => {
      s.dataset.ppPenInit = '1';
      initBand(s);
    });
    root.querySelectorAll('[data-pp-pen-showcase]:not([data-pp-pen-init])').forEach((s) => {
      s.dataset.ppPenInit = '1';
      initShowcase(s);
    });
  }

  window.PPPen = { init };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => init());
  else init();
  document.addEventListener('shopify:section:load', (e) => init(e.target));
})();
