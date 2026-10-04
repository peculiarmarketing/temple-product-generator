const { chromium } = require('playwright');
(async () => {
  const P = process.argv[2];
  const b = await chromium.launch({ proxy: { server: process.env.HTTPS_PROXY || process.env.https_proxy }, args: ['--disable-http2', '--disable-quic'], executablePath: '/opt/pw-browsers/chromium' });
  const out = {};
  for (const [name, vp] of [['desk', { width: 1440, height: 900 }], ['mob', { width: 390, height: 844 }]]) {
    const ctx = await b.newContext({ viewport: vp });
    const pg = await ctx.newPage(); const errs = [];
    await pg.route('**/*', async (route) => { try { const resp = await route.fetch(); await route.fulfill({ response: resp }); } catch (e) { await route.abort(); } });
    pg.on('pageerror', (e) => errs.push(e.message));
    await pg.goto('https://agv44k-jr.myshopify.com/?preview_theme_id=194273870196', { waitUntil: 'networkidle', timeout: 120000 });
    await pg.waitForTimeout(1500);
    out[name] = await pg.evaluate(() => ({
      dive: !!document.querySelector('[data-pp-dive].is-armed'),
      filmOnPage: !!document.querySelector('[data-pp-film]'),
      oldZoomOnPage: !!document.querySelector('[data-pp-zoom]'),
      srcs: [...document.querySelectorAll('[data-pp-dive-step]')].map((e) => (e.dataset.src || '').split('?')[0].split('/').pop()),
      canvas: (() => { const c = document.querySelector('canvas.pp-dive__canvas'); const r = c.getBoundingClientRect(); return [c.width, c.height, Math.round(r.width), Math.round(r.height)]; })(),
      scrollW: document.documentElement.scrollWidth,
    }));
    out[name].errs = errs;
    for (const f of [0, 0.08, 0.14, 0.22, 0.29, 0.37, 0.44, 0.5, 0.56, 0.62, 0.7, 0.8, 0.97]) {
      await pg.evaluate((f) => { const s = document.querySelector('[data-pp-dive]'); const t = s.querySelector('.pp-dive__track'); const st = s.querySelector('.pp-dive__sticky'); scrollTo(0, scrollY + t.getBoundingClientRect().top + (t.offsetHeight - st.offsetHeight) * f + 1); }, f);
      await pg.waitForTimeout(1400);
      await pg.screenshot({ path: `${P}/${name}-${String(Math.round(f * 100)).padStart(3, '0')}.jpg`, quality: 62 });
    }
    await ctx.close();
  }
  console.log(JSON.stringify(out, null, 1)); await b.close();
})();
