/* Peculiar People: pen-drawn temples.
   Drives sections/pp-temple-showcase.liquid (homepage) and
   sections/pp-temple-drawing.liquid (product page). Data files come from
   scripts/web_drawings.py: pp-temple-<slug>.json (pen strokes in draw order,
   their lengths, pen width, art box, city line) and pp-temple-<slug>.webp (the
   finished art). The strokes are a MASK over the finished art, so a shopper
   always ends up looking at the stored drawing; the last 600 ms fades the
   unmasked art in to cover hairline edges the pen does not reach. */
(() => {
  if (window.PPPen) return;

  const NS = 'http://www.w3.org/2000/svg';
  const DRAW_MS = 8500;   // pen down to pen up, one temple
  const HOLD_MS = 3000;   // finished drawing stays up once the city line is complete
  const FADE_MS = 700;    // showcase cross-fade between temples
  const EXACT_MS = 600;   // unmasked art fades in at the end
  const LETTER_MS = 45;
  const RETRY_MS = 4000;  // after a failed download that was not a missing file
  const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const ease = (t) => -(Math.cos(Math.PI * t) - 1) / 2;
  const cache = new Map();
  let uid = 0;

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
          img.onload = resolve;
          img.onerror = () => reject(new Error(`pp-pen: image failed ${item.img}`));
          img.src = item.img;
        }),
      ]).then(([data]) => data);
      p.catch(() => cache.delete(item.json));
      cache.set(item.json, p);
    }
    return cache.get(item.json);
  }

  function svgEl(name, attrs) {
    const node = document.createElementNS(NS, name);
    for (const k in attrs) node.setAttribute(k, attrs[k]);
    return node;
  }

  function mount(artEl, data, imgUrl) {
    const [x, y, w, h] = data.box;
    const id = `pp-pen-mask-${++uid}`;
    const svg = svgEl('svg', { viewBox: `${x} ${y} ${w} ${h}`, 'aria-hidden': 'true', focusable: 'false' });
    const mask = svgEl('mask', { id, maskUnits: 'userSpaceOnUse', x, y, width: w, height: h });
    const pen = svgEl('g', { fill: 'none', stroke: '#fff', 'stroke-width': data.penWidth,
      'stroke-linecap': 'round', 'stroke-linejoin': 'round' });
    const paths = data.strokes.map((d) => pen.appendChild(svgEl('path', { d })));
    mask.appendChild(pen);
    const defs = svgEl('defs', {});
    defs.appendChild(mask);
    const image = (extra) => svgEl('image', { href: imgUrl, x, y, width: w, height: h,
      preserveAspectRatio: 'none', ...extra });
    const drawn = image({ mask: `url(#${id})` });
    const exact = image({ class: 'pp-pen__exact' });
    const tip = svgEl('g', { class: 'pp-pen__tip' });
    tip.appendChild(svgEl('circle', { r: data.penWidth * 1.6, fill: '#F58000', opacity: '0.25' }));
    tip.appendChild(svgEl('circle', { r: data.penWidth * 0.55, fill: '#F58000' }));
    svg.append(defs, drawn, exact, tip);
    setKids(artEl, [svg]);
    return { paths, exact, tip };
  }

  // Resolves once the last letter has faded in.
  function typeCity(cityEl, text, live) {
    const letters = [...text].map((c) => {
      const s = document.createElement('span');
      s.textContent = c === ' ' ? '\u00a0' : c;
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

  async function draw(stage, data, imgUrl, live) {
    const cityEl = stage.querySelector('.pp-pen__city');
    setKids(cityEl, []);
    const { paths, exact, tip } = mount(stage.querySelector('.pp-pen__art'), data, imgUrl);
    if (REDUCED) {
      tip.remove();
      exact.classList.add('is-instant', 'is-on');
      await typeCity(cityEl, data.city, live);
      return;
    }
    const lens = data.lens;
    const cum = [0];
    for (const l of lens) cum.push(cum[cum.length - 1] + l);
    const total = cum[cum.length - 1];
    // Hidden until the pen reaches it: a zero-length stroke would otherwise show
    // its round cap as a stray dot from the first frame.
    paths.forEach((p, i) => {
      p.style.visibility = 'hidden';
      p.style.strokeDasharray = `${lens[i]} ${lens[i] + 1}`;
      p.style.strokeDashoffset = lens[i];
    });
    let i = 0;
    const t0 = performance.now();
    await new Promise((done) => {
      const frame = (now) => {
        if (!live()) return done();
        const progress = Math.min(1, (now - t0) / DRAW_MS);
        const target = ease(progress) * total;
        while (i < paths.length && cum[i + 1] <= target) {
          paths[i].style.visibility = 'visible';
          paths[i].style.strokeDashoffset = 0;
          i++;
        }
        if (i < paths.length) {
          const along = target - cum[i];
          if (along > 0) {
            paths[i].style.visibility = 'visible';
            paths[i].style.strokeDashoffset = lens[i] - along;
            const pt = paths[i].getPointAtLength(along);
            tip.setAttribute('transform', `translate(${pt.x} ${pt.y})`);
          }
        }
        if (progress < 1) requestAnimationFrame(frame); else done();
      };
      requestAnimationFrame(frame);
    });
    if (!live()) return;
    tip.classList.add('is-off');
    exact.classList.add('is-on');
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
          if (err.missing) {  // no drawing uploaded for this temple: remove the band
            finished = true;
            section.remove();
          } else {            // a bad connection: stay hidden and try again shortly
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

  // Homepage showcase: each temple in turn. Entries whose files are missing are dropped.
  function initShowcase(section) {
    const stage = section.querySelector('.pp-pen');
    const dotsEl = section.querySelector('.pp-showcase__dots');
    const items = [...section.querySelectorAll('[data-pp-pen-item]')]
      .map((n) => ({ json: n.dataset.json, img: n.dataset.img }));
    const renderDots = (active) => setKids(dotsEl, items.map((_, j) => {
      const dot = document.createElement('span');
      if (j === active) dot.className = 'is-on';
      return dot;
    }));
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
            if (err.missing) items.splice(idx, 1);  // no such drawing: drop it for good
            else { idx++; await wait(RETRY_MS); }   // bad connection: move on, retry next lap
            continue;
          }
          if (!live()) break;
          renderDots(idx);
          stage.classList.remove('is-faded');
          if (items.length > 1) load(items[(idx + 1) % items.length]).catch(() => {});
          await draw(stage, data, item.img, live);
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
