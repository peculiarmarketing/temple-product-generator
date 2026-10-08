const { chromium } = require('playwright');
(async () => {
  const P = process.argv[2];
  const b = await chromium.launch({ proxy: { server: process.env.HTTPS_PROXY }, args: ['--disable-http2', '--disable-quic'], executablePath: '/opt/pw-browsers/chromium' });
  for (const [name, vp] of [['desk', { width: 1440, height: 900 }], ['mob', { width: 390, height: 844 }]]) {
    const ctx = await b.newContext({ viewport: vp }); const pg = await ctx.newPage(); const errs = [];
    await pg.route('**/*', async (r) => { try { const x = await r.fetch(); await r.fulfill({ response: x }); } catch (e) { await r.abort(); } });
    pg.on('pageerror', (e) => errs.push(e.message));
    await pg.goto('https://agv44k-jr.myshopify.com/?preview_theme_id=194273870196', { waitUntil: 'networkidle', timeout: 120000 });
    const el = await pg.$('[data-pp-spec]'); await el.scrollIntoViewIfNeeded(); await pg.waitForTimeout(4000);
    const bb = await el.boundingBox(); await pg.evaluate((y) => scrollTo(0, scrollY + y), bb.y - 40); await pg.waitForTimeout(800);
    await el.screenshot({ path: `${P}/${name}.jpg`, quality: 75 });
    const sideways = await pg.evaluate(() => document.documentElement.scrollWidth - innerWidth);
    console.log(name, JSON.stringify(await el.boundingBox()), 'sideways', sideways, errs);
    await ctx.close();
  }
  await b.close();
})();
