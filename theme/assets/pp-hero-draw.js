/* Peculiar People homepage hero: drawn, then printed (sections/pp-hero-draw.liquid).
   Styles: pp-hero-draw.css.

   The drawing uses the same data and method as pp-pen-draw.js: pen strokes in draw
   order are a mask over the finished art. Here the pen position comes from scroll
   instead of a clock (the outline draws by itself on arrival, so the hero never
   opens empty), and scrolling back un-draws it. After the drawing, the photo of the
   printed shirt fades in under it, the lines hand off to the print, and the camera
   pulls back. Work only happens while the hero is on screen.

   Not armed under reduced motion or without this script: the hero is then the photo
   with the headline over it. Re-initialises in the theme editor. */
(() => {
  if (window.PPHero) return;

  const NS = 'http://www.w3.org/2000/svg';
  const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const smooth = (a, b, t) => { const x = clamp((t - a) / (b - a), 0, 1); return x * x * (3 - 2 * x); };

  // Scroll timeline, 0..1 through the pinned stretch.
  const T = {
    draw: [0, 0.52],       // the pen follows the scroll
    fabric: [0.50, 0.64],  // the dark ground turns out to be the shirt
    handoff: [0.58, 0.70], // the crisp lines give way to the printed ones beneath
    pull: [0.64, 0.97],    // the camera pulls back to the whole photo
    copy: [0.28, 0.44],    // the headline steps aside while the drawing finishes
  };
  const INTRO = 0.10;      // share of the pen drawn by itself on arrival (the outline)
  const INTRO_MS = 2600;
  const TAU = 70;          // ms of easing on the pen, so it moves like a pen, not a jump

  const cleanups = new WeakMap();

  function init(section) {
    if (REDUCED || !('IntersectionObserver' in window) || !('ResizeObserver' in window)) return;
    const track = section.querySelector('.pp-hero__track');
    const stage = section.querySelector('.pp-hero__stage');
    const world = section.querySelector('.pp-hero__world');
    const photo = section.querySelector('.pp-hero__photo');
    const drawEl = section.querySelector('.pp-hero__draw');
    const copy = section.querySelector('.pp-hero__copy');
    const cue = section.querySelector('.pp-hero__cue');
    const PW = +section.dataset.photoW || 1400;
    const PH = +section.dataset.photoH || 1400;
    const AX = (+section.dataset.artX || 0) / 100 * PW;
    const AY = (+section.dataset.artY || 0) / 100 * PH;
    const AW = (+section.dataset.artW || 30) / 100 * PW;

    let paths = [], lens = [], cum = [0], total = 1, tip = null, exact = null, AH = AW;
    let ready = false, photoReady = false, drawn = 0, intro = 0;
    let W = 0, H = 0, zIn = 1, zOut = 1, cIn = [0, 0], cOut = [PW / 2, PH / 2];
    let cur = 0, raf = 0, lastT = 0, near = false, alive = true;

    function layout() {
      W = stage.clientWidth; H = stage.clientHeight;
      // The header sits above the hero at the top of the page, so on arrival the
      // stage's lower edge is below the fold by that much: lift the headline by it.
      section.style.setProperty('--pp-hero-off', clamp(section.getBoundingClientRect().top + window.scrollY, 0, 240) + 'px');
      const narrow = W < 750;
      world.style.width = PW + 'px';
      world.style.height = PH + 'px';
      Object.assign(drawEl.style, { left: AX + 'px', top: AY + 'px', width: AW + 'px', height: AH + 'px' });
      // Close: the drawing fills most of the height, right of the headline on wide
      // screens, above it on phones. Wide: the whole photo covers the stage.
      zIn = Math.min((H * (narrow ? .46 : .74)) / AH, (W * (narrow ? .8 : .5)) / AW);
      // phones: the drawing sits in the top half, clear of the headline below it
      cIn = [AX + AW / 2 - (narrow ? 0 : (W * .16) / zIn), AY + AH / 2 + (narrow ? (H * .17) / zIn : 0)];
      zOut = Math.max(W / PW, H / PH);
      cOut = [PW / 2, PH / 2];
      render(cur);
    }

    function setPen(frac) {
      const target = frac * total;
      let i = 0;
      while (i < paths.length && cum[i + 1] <= target) i++;
      const lo = Math.min(drawn, i), hi = Math.min(Math.max(drawn, i) + 1, paths.length);
      for (let k = lo; k < hi; k++) {
        if (k < i) { paths[k].style.visibility = 'visible'; paths[k].style.strokeDashoffset = 0; }
        else if (k > i) { paths[k].style.visibility = 'hidden'; paths[k].style.strokeDashoffset = lens[k]; }
      }
      if (i < paths.length) {
        const along = target - cum[i], p = paths[i];
        p.style.visibility = along > 0 ? 'visible' : 'hidden';
        p.style.strokeDashoffset = lens[i] - along;
        if (along > 0) {
          const pt = p.getPointAtLength(along);
          tip.setAttribute('transform', `translate(${pt.x} ${pt.y})`);
        }
      }
      drawn = i;
      tip.style.opacity = frac > 0 && frac < 1 ? 1 : 0;
      exact.style.opacity = smooth(0.97, 1, frac);
    }

    // Scale about a photo point held at the stage centre, in log space so the
    // pull-back reads as one steady move.
    function camera(t) {
      const e = smooth(0, 1, t);
      const z = Math.exp(lerp(Math.log(zIn), Math.log(zOut), e));
      const cx = lerp(cIn[0], cOut[0], e), cy = lerp(cIn[1], cOut[1], e);
      world.style.transform = `translate3d(${W / 2 - cx * z}px, ${H / 2 - cy * z}px, 0) scale(${z})`;
    }

    function render(p) {
      if (!ready) return;
      const span = (r) => clamp((p - r[0]) / (r[1] - r[0]), 0, 1);
      setPen(Math.max(intro * INTRO, span(T.draw)));
      photo.style.opacity = photoReady ? smooth(0, 1, span(T.fabric)) : 0;
      drawEl.style.opacity = photoReady ? 1 - smooth(0, 1, span(T.handoff)) : 1;
      camera(photoReady ? span(T.pull) : 0);
      const c = smooth(0, 1, span(T.copy));
      copy.style.opacity = 1 - c;
      copy.style.transform = `translate3d(0, ${-c * 24}px, 0)`;
      copy.style.visibility = c >= 1 ? 'hidden' : 'visible';
      cue.style.opacity = 1 - smooth(0, .04, p);
    }

    const read = () => clamp(-track.getBoundingClientRect().top / Math.max(1, track.offsetHeight - stage.offsetHeight), 0, 1);
    function tick(now) {
      raf = 0;
      const target = read();
      const dt = lastT ? Math.min(64, now - lastT) : 16;
      lastT = now;
      cur = lerp(cur, target, 1 - Math.exp(-dt / TAU));
      if (Math.abs(cur - target) < 0.0003) cur = target;
      render(cur);
      if (cur !== target) raf = requestAnimationFrame(tick); else lastT = 0;
    }
    const kick = () => { if (near && !raf) raf = requestAnimationFrame(tick); };

    const io = new IntersectionObserver(([e]) => {
      near = e.isIntersecting;
      if (near) { window.addEventListener('scroll', kick, { passive: true }); kick(); }
      else window.removeEventListener('scroll', kick);
    });
    const ro = new ResizeObserver(layout);

    async function load() {
      const data = await fetch(section.dataset.json).then((r) => { if (!r.ok) throw new Error(`pp-hero: ${r.status}`); return r.json(); });
      if (!alive) return;
      const [x, y, w, h] = data.box;
      AH = AW * h / w;
      const svg = document.createElementNS(NS, 'svg');
      svg.setAttribute('viewBox', `${x} ${y} ${w} ${h}`);
      svg.setAttribute('preserveAspectRatio', 'none');
      svg.setAttribute('aria-hidden', 'true');
      const id = `pp-hero-mask-${Math.random().toString(36).slice(2)}`;
      const img = section.dataset.img;
      svg.innerHTML = `<defs><mask id="${id}" maskUnits="userSpaceOnUse" x="${x}" y="${y}" width="${w}" height="${h}"><g fill="none" stroke="#fff" stroke-width="${data.penWidth}" stroke-linecap="round" stroke-linejoin="round"></g></mask></defs>`
        + `<image href="${img}" x="${x}" y="${y}" width="${w}" height="${h}" preserveAspectRatio="none" mask="url(#${id})"/>`
        + `<image class="pp-hero__exact" href="${img}" x="${x}" y="${y}" width="${w}" height="${h}" preserveAspectRatio="none"/>`
        + `<g class="pp-hero__tip"><circle r="${data.penWidth * 1.6}" fill="#fff" opacity=".2"/><circle r="${data.penWidth * .55}" fill="#fff"/></g>`;
      const pen = svg.querySelector('mask g');
      lens = data.lens;
      data.strokes.forEach((d, i) => {
        const p = document.createElementNS(NS, 'path');
        p.setAttribute('d', d);
        if (data.widths && data.widths[i]) p.setAttribute('stroke-width', data.widths[i]);
        p.style.strokeDasharray = `${lens[i]} ${lens[i] + 1}`;
        p.style.strokeDashoffset = lens[i];
        p.style.visibility = 'hidden';
        pen.appendChild(p);
        paths.push(p);
        cum.push(cum[cum.length - 1] + lens[i]);
      });
      total = cum[cum.length - 1];
      tip = svg.querySelector('.pp-hero__tip');
      exact = svg.querySelector('.pp-hero__exact');
      // The art must be decoded before the mask can show it.
      await new Promise((res) => { const im = new Image(); im.onload = im.onerror = res; im.src = img; });
      if (!alive) return;
      drawEl.appendChild(svg);
      section.classList.add('is-armed');
      ready = true;
      ro.observe(stage);
      io.observe(track);
      layout();
      // The photo decodes in the background; only the shirt stage waits for it.
      const pimg = photo.querySelector('img');
      if (pimg) (pimg.decode ? pimg.decode() : Promise.resolve()).catch(() => {}).then(() => { photoReady = true; render(cur); });
      const t0 = performance.now();
      const run = (now) => {
        if (!alive) return;
        intro = smooth(0, 1, (now - t0) / INTRO_MS);
        render(cur);
        if (intro < 1) requestAnimationFrame(run);
      };
      requestAnimationFrame(run);
    }

    load().catch((err) => {
      // No drawing: leave the still hero (photo and headline) in place.
      console.warn(err);
    });

    cleanups.set(section, () => {
      alive = false;
      io.disconnect();
      ro.disconnect();
      window.removeEventListener('scroll', kick);
      if (raf) cancelAnimationFrame(raf);
    });
  }

  function initAll(root = document) {
    root.querySelectorAll('[data-pp-hero]:not([data-pp-init])').forEach((s) => {
      s.dataset.ppInit = '1';
      init(s);
    });
  }

  window.PPHero = { init: initAll };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => initAll());
  else initAll();
  document.addEventListener('shopify:section:load', (e) => initAll(e.target));
  document.addEventListener('shopify:section:unload', (e) => {
    e.target.querySelectorAll('[data-pp-hero]').forEach((s) => { const off = cleanups.get(s); if (off) off(); });
  });
})();
