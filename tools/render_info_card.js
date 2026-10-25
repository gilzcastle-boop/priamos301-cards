// Render a 1080x1350 vintage "info card": smaller illustration, ribbon headline and 3-4 numbered key facts.
//   node tools/render_info_card.js spec.json out.jpg
// spec: {label, headline ("line 1\n[red line 2]"), facts: [[key, text], ...], image, focus ("50% 45%"),
//        badge ("right" | "left", keep the label off the main subject), stamp (short red hook word
//        stamped on the picture, e.g. "국회 청원"), handle, brand, credit,
//        date (optional, defaults to today in Korean time)}
const { chromium } = require('playwright');
const fs = require('fs');

const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

(async () => {
  const [specPath, out] = process.argv.slice(2);
  const spec = JSON.parse(fs.readFileSync(specPath, 'utf8'));
  const img = 'data:image/png;base64,' + fs.readFileSync(spec.image).toString('base64');
  const kst = new Date(Date.now() + 9 * 3600e3);
  const date = spec.date || `${kst.getUTCFullYear()}. ${kst.getUTCMonth() + 1}. ${kst.getUTCDate()}.`;
  const brand = spec.brand || 'PRIAMOS';
  // "[red part]" marks the ribbon highlight, same convention as the card factory.
  const headline = spec.headline.split('\n').map(line =>
    '<div class="hl">' + esc(line).replace(/\[([^\]]+)\]/g, '<span class="rib">$1</span>') + '</div>').join('');
  const facts = spec.facts.map(([k, t], i) =>
    `<li><span class="num">${i + 1}</span><p><b>${esc(k)}</b>${esc(t)}</p></li>`).join('');
  const star = Array.from({ length: 28 }, (_, i) => {
    const a = Math.PI * i / 14 - Math.PI / 2, r = i % 2 ? 68.8 : 86;
    return `${(86 + Math.cos(a) * r).toFixed(1)},${(86 + Math.sin(a) * r).toFixed(1)}`;
  }).join(' ');

  const html = `<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Hahmlet:wght@500;700;900&family=Noto+Sans+KR:wght@500;700;900&family=Yellowtail&display=swap">
<style>
  :root { --paper: #F2E6CB; --ink: #2B1D14; --red: #C8352B; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { width: 1080px; height: 1350px; }
  #card { position: relative; width: 1080px; height: 1350px; background: var(--paper); color: var(--ink); overflow: hidden; }
  #grain { position: absolute; inset: 0; }
  .frame { position: absolute; border: 4px solid var(--ink); inset: 34px; }
  .frame2 { position: absolute; border: 1.5px solid var(--ink); inset: 46px; }
  .top { position: absolute; left: 82px; right: 82px; top: 64px; display: flex; justify-content: space-between;
         font: 700 24px "Hahmlet", serif; letter-spacing: 4px; border-bottom: 3px solid var(--ink); padding-bottom: 12px; }
  .pic { position: absolute; left: 82px; right: 82px; top: 132px; height: 420px; border: 4px solid var(--ink); border-radius: 16px; overflow: hidden; }
  .pic img { width: 100%; height: 100%; object-fit: cover; object-position: ${spec.focus || '50% 50%'};
             filter: sepia(.12) saturate(1.04) contrast(1.03); display: block; }
  .pic::after { content: ""; position: absolute; inset: 0; opacity: .08;
                background: radial-gradient(#5A3A1E 1.5px, transparent 1.7px) 0 0 / 7px 7px; }
  .badge { position: absolute; ${spec.badge === 'left' ? 'left' : 'right'}: 64px; top: 104px; width: 172px; height: 172px; }
  .badge span { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
                transform: rotate(-10deg); color: var(--paper); font: 900 ${spec.label && spec.label.length > 2 ? 30 : 38}px "Hahmlet", serif; }
  #head { position: absolute; left: 110px; right: 110px; top: 584px; font: 900 78px/1.28 "Hahmlet", serif; }
  .stamp { position: absolute; left: 108px; top: 456px; transform: rotate(-7deg); padding: 10px 30px;
           background: rgba(242,230,203,.88); color: var(--red); font: 900 50px/1.2 "Hahmlet", serif;
           border: 6px solid var(--red); outline: 2px solid var(--red); outline-offset: -14px; }
  .hl { white-space: nowrap; }
  .rib { background: var(--red); color: var(--paper); padding: 0 26px; margin-left: -26px;
         clip-path: polygon(0 0, 100% 0, calc(100% - 18px) 50%, 100% 100%, 0 100%, 18px 50%); }
  #facts { position: absolute; left: 96px; right: 96px; list-style: none; }
  #facts li { display: flex; gap: 18px; align-items: flex-start; padding: 14px 0; border-top: 1.5px dashed rgba(43,29,20,.35); }
  #facts li:first-child { border-top: 0; }
  .num { flex: none; width: 44px; height: 44px; border-radius: 50%; background: var(--red); color: var(--paper);
         font: 900 26px/44px "Hahmlet", serif; text-align: center; margin-top: 2px; }
  #facts p { font: 500 30px/1.42 "Noto Sans KR", sans-serif; word-break: keep-all; text-wrap: pretty; }
  #facts b { font-weight: 900; color: var(--red); margin-right: 12px; }
  .foot { position: absolute; left: 82px; right: 82px; bottom: 158px; border-top: 1.5px solid var(--ink); }
  .logo { position: absolute; left: 92px; bottom: 60px; font: 400 66px "Yellowtail", cursive; color: var(--red); }
  .handle { position: absolute; right: 96px; bottom: 110px; font: 700 24px "Hahmlet", serif; }
  .credit { position: absolute; right: 96px; bottom: 56px; font: 500 20px "Hahmlet", serif; opacity: .75; }
</style></head><body><div id="card">
  <canvas id="grain" width="1080" height="1350"></canvas>
  <div class="frame"></div><div class="frame2"></div>
  <div class="top"><span>${esc(brand.toUpperCase())} · DAILY ISSUE</span><span>${esc(date)}</span></div>
  <div class="pic"><img src="${img}"></div>
  ${spec.label ? `<div class="badge"><svg width="172" height="172"><polygon points="${star}" fill="#C8352B"/></svg><span>${esc(spec.label)}</span></div>` : ''}
  ${spec.stamp ? `<div class="stamp">${esc(spec.stamp)}</div>` : ''}
  <div id="head">${headline}</div>
  <ol id="facts">${facts}</ol>
  <div class="foot"></div>
  <div class="logo">${esc(brand.charAt(0).toUpperCase() + brand.slice(1).toLowerCase())}</div>
  <div class="handle">${esc(spec.handle || '@priamos301')}</div>
  <div class="credit">${esc(spec.credit || '그림: AI 생성 연출 이미지')}</div>
</div></body></html>`;

  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1080, height: 1350 } });
  await p.setContent(html, { waitUntil: 'networkidle', timeout: 60000 });
  await p.evaluate(() => document.fonts.ready);
  const fit = await p.evaluate(() => {
    // Paper grain, same recipe as the card factory.
    const g = document.getElementById('grain').getContext('2d');
    let s = 7; const r = () => (s = (s * 16807) % 2147483647) / 2147483647;
    for (let i = 0; i < 9000; i++) { g.fillStyle = `rgba(90,60,30,${.03 + r() * .06})`; g.fillRect(r() * 1080, r() * 1350, 1 + r() * 2, 1 + r() * 2); }
    // Shrink the headline until every line fits, then the facts until they clear the footer.
    const head = document.getElementById('head'), facts = document.getElementById('facts');
    let hs = 78;
    while (hs > 44 && [...head.children].some(l => l.scrollWidth > head.clientWidth)) head.style.fontSize = (hs -= 2) + 'px';
    const bottom = 1350 - 158 - 18;
    let fs = 30;
    for (;;) {
      facts.style.top = (head.offsetTop + head.offsetHeight + 22) + 'px';
      facts.querySelectorAll('p').forEach(el => el.style.fontSize = fs + 'px');
      if (facts.offsetTop + facts.offsetHeight <= bottom || fs <= 22) break;
      fs -= 1;
    }
    return { headline: hs, facts: fs, overflow: facts.offsetTop + facts.offsetHeight - bottom };
  });
  if (fit.overflow > 0) console.error(`facts overflow by ${fit.overflow}px at ${fit.facts}px - shorten them`);
  console.log(`headline ${fit.headline}px, facts ${fit.facts}px`);
  await p.locator('#card').screenshot({ path: out, type: 'jpeg', quality: 92 });
  await b.close();
})();
