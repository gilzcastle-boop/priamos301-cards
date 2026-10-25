// Render a 1080x1350 news card from tools/card_factory.html and a JSON spec: node tools/render_card.js spec.json out.jpg
// spec: {template, label, headline ("line 1\n[red line 2]"), sub, handle, brand, source, credit, image}
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const [specPath, out] = process.argv.slice(2);
  const spec = JSON.parse(fs.readFileSync(specPath, 'utf8'));
  const page = fs.readFileSync(path.join(__dirname, 'card_factory.html'), 'utf8');
  const b = await chromium.launch();
  // The card prints today's date, so render in Korean time rather than the container's UTC.
  const p = await b.newPage({ viewport: { width: 1280, height: 1400 }, timezoneId: 'Asia/Seoul' });
  await p.setContent('<!doctype html><html><head><meta charset="utf-8"></head><body>' + page + '</body></html>', { waitUntil: 'networkidle', timeout: 60000 });
  if (spec.image) { await p.setInputFiles('#fileIn', spec.image); await p.waitForTimeout(800); }
  await p.evaluate(s => {
    const set = (id, v) => { const el = document.querySelector(id); el.value = v; el.dispatchEvent(new Event('input')); };
    set('#fLabel', s.label); set('#fHeadline', s.headline); set('#fSub', s.sub);
    set('#fHandle', s.handle); if (s.brand !== undefined) set('#fBrand', s.brand); set('#fSource', s.source || ''); set('#fCredit', s.credit || '');
    if (s.template) document.querySelector(`#tplSeg button[data-v="${s.template}"]`).click();
    if (s.bg) document.querySelector(`#swatches button[data-c="${s.bg}"]`).click();
  }, spec);
  await p.evaluate(() => document.fonts.ready);
  await p.waitForTimeout(2500);
  const data = await p.evaluate(() => document.querySelector('#cv').toDataURL('image/jpeg', 0.92));
  fs.writeFileSync(out, Buffer.from(data.split(',')[1], 'base64'));
  await b.close();
})();
