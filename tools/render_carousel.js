// Render the first slides of a card-news carousel in the info-card style: a big cover and one slide per point.
//   node tools/render_carousel.js spec.json cards/20261027-01
// writes <prefix>-c1.jpg (cover), <prefix>-c2.jpg ... (points) and <prefix>-end.jpg (follow slide, styled like the
// reel's end card). The recap slide is the info card itself (tools/render_info_card.js -> <prefix>.jpg), so
// tools/publish.py --carousel posts c1..cN, then <prefix>.jpg, then <prefix>-end.jpg.
// spec: the info-card spec plus points: [[kicker, title, body], ...] (3 points: what happened, the detail,
//       what next / the other side). title up to ~16 chars per line, body up to ~70 chars.
const { chromium } = require('playwright');
const fs = require('fs');

const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

(async () => {
  const [specPath, prefix] = process.argv.slice(2);
  const spec = JSON.parse(fs.readFileSync(specPath, 'utf8'));
  const img = 'data:image/png;base64,' + fs.readFileSync(spec.image).toString('base64');
  const kst = new Date(Date.now() + 9 * 3600e3);
  const date = spec.date || `${kst.getUTCFullYear()}. ${kst.getUTCMonth() + 1}. ${kst.getUTCDate()}.`;
  const brand = spec.brand || 'PRIAMOS';
  const total = spec.points.length + 3;
  const headline = spec.headline.split('\n').map(line =>
    '<div class="hl">' + esc(line).replace(/\[([^\]]+)\]/g, '<span class="rib">$1</span>') + '</div>').join('');
  const star = Array.from({ length: 28 }, (_, i) => {
    const a = Math.PI * i / 14 - Math.PI / 2, r = i % 2 ? 68.8 : 86;
    return `${(86 + Math.cos(a) * r).toFixed(1)},${(86 + Math.sin(a) * r).toFixed(1)}`;
  }).join(' ');
  const [fx, fy] = (spec.focus || '50% 50%').split(' ');
  // Each point slide shows a different band of the same picture so the deck reads as one story.
  const strips = ['25%', '55%', '85%'];

  const chrome = n => `
  <canvas class="grain" width="1080" height="1350"></canvas>
  <div class="frame"></div><div class="frame2"></div>
  <div class="top"><span>${esc(brand.toUpperCase())} · DAILY ISSUE</span><span>${esc(date)}</span></div>
  <div class="foot"></div>
  <div class="logo">${esc(brand.charAt(0).toUpperCase() + brand.slice(1).toLowerCase())}</div>
  <div class="handle">${esc(spec.handle || '@priamos301')}</div>
  <div class="count">${n} / ${total}</div>
  ${spec.credit ? `<div class="credit">${esc(spec.credit)}</div>` : ''}`;

  const cover = `<section class="slide" id="s1">${chrome(1)}
  <div class="pic cover"><img src="${img}" style="object-position:${spec.focus || '50% 50%'}"></div>
  ${spec.label ? `<div class="badge"><svg width="172" height="172"><polygon points="${star}" fill="#C8352B"/></svg><span>${esc(spec.label)}</span></div>` : ''}
  ${spec.stamp ? `<div class="stamp">${esc(spec.stamp)}</div>` : ''}
  <div class="head">${headline}</div>
  <div class="next">옆으로 넘겨 보기 →</div>
  </section>`;

  const points = spec.points.map(([kicker, title, body], i) => `<section class="slide" id="s${i + 2}">${chrome(i + 2)}
  <div class="pic strip"><img src="${img}" style="object-position:${fx || '50%'} ${strips[i % 3]}"></div>
  <div class="no">0${i + 1}</div>
  <div class="kicker">${esc(kicker)}</div>
  <div class="ptitle">${esc(title).replace(/\n/g, '<br>')}</div>
  <div class="pbody">${esc(body)}</div>
  </section>`).join('');

  const end = `<section class="slide" id="end">${chrome(total)}
  <div class="kick">DAILY ISSUE CHECK</div>
  <div class="brand">${esc(brand.charAt(0).toUpperCase() + brand.slice(1).toLowerCase())}</div>
  <div class="rule"></div>
  <div class="lead">오늘의 이슈, 1분이면 끝</div>
  <div class="sub">아침 · 점심 · 퇴근길 · 저녁 · 밤<br>하루 5번, 화제 뉴스만 골라 정리합니다</div>
  <div class="btn">+ 팔로우하고 매일 체크</div>
  <div class="at">${esc(spec.handle || '@priamos301')}</div>
  </section>`;

  const html = `<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Hahmlet:wght@500;700;900&family=Noto+Sans+KR:wght@500;700;900&family=Yellowtail&display=swap">
<style>
  :root { --paper: #F2E6CB; --ink: #2B1D14; --red: #C8352B; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { width: 1080px; }
  .slide { position: relative; width: 1080px; height: 1350px; background: var(--paper); color: var(--ink); overflow: hidden; }
  .grain { position: absolute; inset: 0; }
  .frame { position: absolute; border: 4px solid var(--ink); inset: 34px; }
  .frame2 { position: absolute; border: 1.5px solid var(--ink); inset: 46px; }
  .top { position: absolute; left: 82px; right: 82px; top: 64px; display: flex; justify-content: space-between;
         font: 700 24px "Hahmlet", serif; letter-spacing: 4px; border-bottom: 3px solid var(--ink); padding-bottom: 12px; }
  .pic { position: absolute; left: 82px; right: 82px; top: 132px; border: 4px solid var(--ink); border-radius: 16px; overflow: hidden; }
  .pic.cover { height: 700px; }
  .pic.strip { height: 400px; }
  .pic img { width: 100%; height: 100%; object-fit: cover; filter: sepia(.12) saturate(1.04) contrast(1.03); display: block; }
  .pic::after { content: ""; position: absolute; inset: 0; opacity: .08;
                background: radial-gradient(#5A3A1E 1.5px, transparent 1.7px) 0 0 / 7px 7px; }
  .badge { position: absolute; ${spec.badge === 'left' ? 'left' : 'right'}: 64px; top: 104px; width: 172px; height: 172px; }
  .badge span { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
                transform: rotate(-10deg); color: var(--paper); font: 900 ${spec.label && spec.label.length > 2 ? 30 : 38}px "Hahmlet", serif; }
  .stamp { position: absolute; left: 108px; top: 738px; transform: rotate(-7deg); padding: 10px 30px;
           background: rgba(242,230,203,.88); color: var(--red); font: 900 54px/1.2 "Hahmlet", serif;
           border: 6px solid var(--red); outline: 2px solid var(--red); outline-offset: -14px; }
  .head { position: absolute; left: 110px; right: 110px; top: 868px; font: 900 84px/1.28 "Hahmlet", serif; }
  .hl { white-space: nowrap; }
  .rib { background: var(--red); color: var(--paper); padding: 0 26px; margin-left: -26px;
         clip-path: polygon(0 0, 100% 0, calc(100% - 18px) 50%, 100% 100%, 0 100%, 18px 50%); }
  .next { position: absolute; right: 96px; bottom: 176px; font: 700 26px "Noto Sans KR", sans-serif; color: var(--red); }
  .no { position: absolute; left: 92px; top: 580px; font: 900 120px/1 "Hahmlet", serif; color: var(--red); opacity: .9; }
  .kicker { position: absolute; left: 282px; top: 606px; font: 900 34px "Noto Sans KR", sans-serif; color: var(--red);
            border-bottom: 4px solid var(--red); padding-bottom: 6px; }
  .ptitle { position: absolute; left: 96px; right: 96px; top: 736px; font: 900 64px/1.3 "Hahmlet", serif; word-break: keep-all; }
  .pbody { position: absolute; left: 96px; right: 96px; font: 500 38px/1.6 "Noto Sans KR", sans-serif; word-break: keep-all; text-wrap: pretty; }
  .foot { position: absolute; left: 82px; right: 82px; bottom: 158px; border-top: 1.5px solid var(--ink); }
  .logo { position: absolute; left: 92px; bottom: 60px; font: 400 66px "Yellowtail", cursive; color: var(--red); }
  .handle { position: absolute; right: 96px; bottom: 110px; font: 700 24px "Hahmlet", serif; }
  .count { position: absolute; right: 96px; bottom: 60px; font: 700 26px "Hahmlet", serif; letter-spacing: 2px; }
  .credit { position: absolute; left: 96px; bottom: 172px; font: 500 15px "Noto Sans KR", sans-serif; opacity: .5; }
  #end .kick { position: absolute; left: 0; right: 0; top: 250px; text-align: center; font: 700 30px "Hahmlet", serif; letter-spacing: 10px; }
  #end .brand { position: absolute; left: 0; right: 0; top: 300px; text-align: center; font: 400 170px/1.1 "Yellowtail", cursive; color: var(--red); }
  #end .rule { position: absolute; left: 330px; right: 330px; top: 520px; border-top: 5px solid var(--ink); }
  #end .lead { position: absolute; left: 0; right: 0; top: 580px; text-align: center; font: 900 64px/1.3 "Hahmlet", serif; }
  #end .sub { position: absolute; left: 0; right: 0; top: 690px; text-align: center; font: 500 34px/1.6 "Noto Sans KR", sans-serif; opacity: .85; }
  #end .btn { position: absolute; left: 50%; top: 860px; transform: translateX(-50%); white-space: nowrap; padding: 26px 64px;
              background: var(--red); color: var(--paper); border-radius: 999px; font: 900 42px "Noto Sans KR", sans-serif;
              box-shadow: 0 6px 0 var(--ink); }
  #end .at { position: absolute; left: 0; right: 0; top: 1000px; text-align: center; font: 900 40px "Hahmlet", serif; }
  #end .credit, #end .logo, #end .handle { display: none; }
</style></head><body>${cover}${points}${end}</body></html>`;

  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1080, height: 1350 } });
  await p.setContent(html, { waitUntil: 'networkidle', timeout: 60000 });
  await p.evaluate(() => document.fonts.ready);
  const fit = await p.evaluate(() => {
    document.querySelectorAll('.grain').forEach(c => {
      const g = c.getContext('2d');
      let s = 7; const r = () => (s = (s * 16807) % 2147483647) / 2147483647;
      for (let i = 0; i < 9000; i++) { g.fillStyle = `rgba(90,60,30,${.03 + r() * .06})`; g.fillRect(r() * 1080, r() * 1350, 1 + r() * 2, 1 + r() * 2); }
    });
    const report = [];
    const head = document.querySelector('.head');
    let hs = 84;
    while (hs > 48 && [...head.children].some(l => l.scrollWidth > head.clientWidth)) head.style.fontSize = (hs -= 2) + 'px';
    report.push(`cover ${hs}px`);
    const bottom = 1350 - 158 - 70;
    document.querySelectorAll('.slide').forEach((s, i) => {
      const t = s.querySelector('.ptitle'), body = s.querySelector('.pbody');
      if (!t) return;
      let ts = 64, bs = 38;
      for (;;) {
        t.style.fontSize = ts + 'px'; body.style.fontSize = bs + 'px';
        body.style.top = (t.offsetTop + t.offsetHeight + 28) + 'px';
        if (body.offsetTop + body.offsetHeight <= bottom || bs <= 28) break;
        ts -= 2; bs -= 1;
      }
      const over = body.offsetTop + body.offsetHeight - bottom;
      report.push(`point ${i} ${ts}/${bs}px${over > 0 ? ` OVERFLOW ${over}px` : ''}`);
    });
    return report;
  });
  console.log(fit.join(', '));
  if (fit.some(r => r.includes('OVERFLOW'))) console.error('point text overflow - shorten it');
  const slides = await p.locator('.slide').all();
  for (let i = 0; i < slides.length; i++) {
    const name = i === slides.length - 1 ? `${prefix}-end.jpg` : `${prefix}-c${i + 1}.jpg`;
    await slides[i].screenshot({ path: name, type: 'jpeg', quality: 92 });
  }
  await b.close();
})();
