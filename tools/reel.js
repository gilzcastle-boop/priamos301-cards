// Render a vertical news reel (1080x1920, 30fps JPEG frames) from a card illustration: node reel.js spec.json outDir
const { chromium } = require('playwright'); const fs = require('fs'); const path = require('path');
(async () => {
  const [specPath, outDir] = process.argv.slice(2);
  const spec = JSON.parse(fs.readFileSync(specPath, 'utf8'));
  fs.mkdirSync(outDir, { recursive: true });
  const img = 'data:image/png;base64,' + fs.readFileSync(spec.image).toString('base64');
  const b = await chromium.launch(); const p = await b.newPage();
  p.on('pageerror', e => console.error('pageerror', e.message));
  await p.setContent(`<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Hahmlet:wght@500;700;900&family=Noto+Sans+KR:wght@700;800;900&family=Yellowtail&display=swap"></head>
<body style="margin:0"><canvas id="c" width="1080" height="1920"></canvas></body></html>`, { waitUntil: 'networkidle' });
  await p.evaluate(async ({ img, spec }) => {
    const all = [spec.label, spec.line1, spec.line2, ...spec.subs.map(s => s[2]), spec.handle, 'PRIAMOS DAILY ISSUE 0123456789. 그림: AI 생성 연출 이미지 자세한 내용은 캡션에서'].join(' ');
    await Promise.all([document.fonts.load('900 80px "Hahmlet"', all), document.fonts.load('700 40px "Hahmlet"', all), document.fonts.load('800 50px "Noto Sans KR"', all), document.fonts.load('900 50px "Noto Sans KR"', all), document.fonts.load('400 120px "Yellowtail"', 'Priamos')]);
    const im = new Image(); im.src = img; await im.decode(); window.IMG = im;
  }, { img, spec });
  await p.evaluate(spec => {
    const W = 1080, H = 1920, x = document.getElementById('c').getContext('2d');
    const V = { paper: '#F2E6CB', ink: '#2B1D14', red: '#C8352B', mustard: '#E3A72F' };
    const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
    const ease = t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
    const prog = (t, a, b) => clamp((t - a) / (b - a), 0, 1);
    const back = t => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); };
    // paper grain, built once
    const grain = document.createElement('canvas'); grain.width = W; grain.height = H; { const g = grain.getContext('2d'); let s = 7; const r = () => (s = (s * 16807) % 2147483647) / 2147483647; for(let i = 0; i < 9000; i++){ g.fillStyle = `rgba(90,60,30,${.03 + r() * .06})`; g.fillRect(r() * W, r() * H, 1 + r() * 2, 1 + r() * 2); } }
    const dots = document.createElement('canvas'); dots.width = dots.height = 8; { const g = dots.getContext('2d'); g.fillStyle = '#5A3A1E'; g.beginPath(); g.arc(4, 4, 1.4, 0, 7); g.fill(); }
    const dotPat = x.createPattern(dots, 'repeat');
    // camera keyframes: [t, centerX (image px), centerY, zoom]
    function cam(t){
      const k = spec.pan; let i = 0; while(i < k.length - 2 && t > k[i + 1][0]) i++;
      const [t0, x0, y0, z0] = k[i], [t1, x1, y1, z1] = k[i + 1], u = ease(prog(t, t0, t1));
      return [x0 + (x1 - x0) * u, y0 + (y1 - y0) * u, z0 + (z1 - z0) * u];
    }
    function drawImage(t){
      const im = window.IMG, [cx, cy, z] = cam(t), s = H / im.height * z;
      let ox = W / 2 - cx * s, oy = H / 2 - cy * s;
      ox = clamp(ox, W - im.width * s, 0); oy = clamp(oy, H - im.height * s, 0);
      x.filter = 'sepia(.12) saturate(1.05) contrast(1.03)'; x.drawImage(im, ox, oy, im.width * s, im.height * s); x.filter = 'none';
      x.save(); x.globalAlpha = .07; x.fillStyle = dotPat; x.fillRect(0, 0, W, H); x.restore();
      const g = x.createLinearGradient(0, H * .5, 0, H); g.addColorStop(0, 'rgba(30,18,10,0)'); g.addColorStop(1, 'rgba(30,18,10,.55)'); x.fillStyle = g; x.fillRect(0, H * .5, W, H * .5);
    }
    function starburst(cx, cy, r, n, rot){ x.beginPath(); for(let i = 0; i < n * 2; i++){ const a = Math.PI * i / n - Math.PI / 2 + rot, rad = i % 2 ? r * .8 : r; x.lineTo(cx + Math.cos(a) * rad, cy + Math.sin(a) * rad); } x.closePath(); x.fill(); }
    function ribbon(x0, y, w, h){ const n = h * .32; x.beginPath(); x.moveTo(x0 - n, y); x.lineTo(x0 + w + n, y); x.lineTo(x0 + w, y + h / 2); x.lineTo(x0 + w + n, y + h); x.lineTo(x0 - n, y + h); x.lineTo(x0, y + h / 2); x.closePath(); x.fill(); }
    function frame(){
      x.strokeStyle = V.paper; x.lineWidth = 26; x.strokeRect(13, 13, W - 26, H - 26);
      x.strokeStyle = V.ink; x.lineWidth = 3; x.strokeRect(30, 30, W - 60, H - 60);
    }
    function header(t){
      const a = prog(t, 0, .4);
      x.save(); x.globalAlpha = a;
      x.fillStyle = V.paper; x.fillRect(30, 30, W - 60, 150); x.drawImage(grain, 0, 0, W, 180, 0, 0, W, 180);
      x.fillStyle = V.ink; x.font = '700 30px "Hahmlet"'; try{ x.letterSpacing = '5px'; }catch(e){}
      x.textBaseline = 'alphabetic'; x.fillText('PRIAMOS · DAILY ISSUE', 74, 118); x.textAlign = 'right'; x.fillText(spec.date, W - 74, 118); x.textAlign = 'left';
      try{ x.letterSpacing = '0px'; }catch(e){}
      x.fillRect(74, 140, W - 148, 3); x.fillRect(74, 148, W - 148, 1);
      x.restore();
    }
    function label(t){
      const u = prog(t, .3, .8); if(u <= 0) return;
      const sc = back(u), cx = W - 170, cy = 300;
      x.save(); x.translate(cx, cy); x.scale(sc, sc); x.rotate(-.18 + Math.sin(t * 1.5) * .02);
      x.fillStyle = V.red; starburst(0, 0, 100, 14, 0);
      x.fillStyle = V.paper; x.font = '900 46px "Hahmlet"'; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText(spec.label, 0, 4); x.restore();
      x.textAlign = 'left'; x.textBaseline = 'alphabetic';
    }
    function wrap(text, font, maxW){ x.font = font; const out = []; text.split('\n').forEach(par => { let line = ''; for(const ch of par){ if(x.measureText(line + ch).width > maxW && line){ out.push(line); line = ch; } else line += ch; } out.push(line); }); return out; }
    function headline(t){
      const outA = 1 - prog(t, spec.headOut, spec.headOut + .4); if(outA <= 0) return;
      const y0 = 1240;
      // line 1: ink on paper card, slides up
      const u1 = ease(prog(t, .4, 1.1));
      if(u1 > 0){
        x.save(); x.globalAlpha = u1 * outA; x.translate(0, (1 - u1) * 60);
        let f1 = 78; x.font = `900 ${f1}px "Hahmlet"`; { const m = x.measureText(spec.line1).width; if(m > 860){ f1 = Math.floor(78 * 860 / m); x.font = `900 ${f1}px "Hahmlet"`; } } const w1 = x.measureText(spec.line1).width;
        x.fillStyle = V.paper; x.fillRect(64, y0 - 20, w1 + 64, 120); x.strokeStyle = V.ink; x.lineWidth = 3; x.strokeRect(64, y0 - 20, w1 + 64, 120);
        x.fillStyle = V.ink; x.fillText(spec.line1, 96, y0 + 72, 880); x.restore();
      }
      // line 2: red ribbon wipes in
      const u2 = ease(prog(t, spec.line2At, spec.line2At + .6));
      if(u2 > 0){
        let f2 = 74; x.save(); x.globalAlpha = outA; x.font = `900 ${f2}px "Hahmlet"`; { const m = x.measureText(spec.line2).width; if(m > 840){ f2 = Math.floor(74 * 840 / m); x.font = `900 ${f2}px "Hahmlet"`; } } const w2 = x.measureText(spec.line2).width;
        x.beginPath(); x.rect(0, y0 + 110, 64 + (w2 + 120) * u2, 160); x.clip();
        x.fillStyle = V.red; ribbon(84, y0 + 128, w2 + 40, 112);
        x.fillStyle = V.paper; x.fillText(spec.line2, 104, y0 + 210, 860); x.restore();
      }
      // sub line
      const u3 = prog(t, spec.line2At + .5, spec.line2At + 1);
      if(u3 > 0 && spec.sub){ x.save(); x.globalAlpha = u3 * outA; x.font = '700 40px "Noto Sans KR"'; x.fillStyle = V.paper; x.shadowColor = 'rgba(0,0,0,.6)'; x.shadowBlur = 10; x.fillText(spec.sub, 80, y0 + 320, 880); x.restore(); }
    }
    function subtitle(t){
      spec.subs.forEach(([a, b, text]) => {
        if(t < a || t > b) return;
        const fin = prog(t, a, a + .3), fout = 1 - prog(t, b - .3, b), al = Math.min(fin, fout);
        const lines = wrap(text, '800 54px "Noto Sans KR"', 860), lh = 76, h = lines.length * lh + 56, y = 1300;
        x.save(); x.globalAlpha = al; x.translate(0, (1 - fin) * 30);
        x.fillStyle = V.paper; x.fillRect(60, y, 960, h); x.strokeStyle = V.ink; x.lineWidth = 3; x.strokeRect(60, y, 960, h);
        x.fillStyle = V.red; x.fillRect(60, y, 14, h);
        x.fillStyle = V.ink; x.font = '800 54px "Noto Sans KR"'; lines.forEach((l, i) => x.fillText(l, 104, y + 28 + 56 + i * lh, 880));
        x.restore();
      });
    }
    function credit(t){ if(t > spec.endAt) return; x.font = '700 24px "Noto Sans KR"'; x.fillStyle = 'rgba(255,245,230,.75)'; x.fillText('그림: AI 생성 연출 이미지', 64, H - 64); }
    function endCard(t){
      const u = ease(prog(t, spec.endAt, spec.endAt + .6)); if(u <= 0) return;
      x.save(); x.globalAlpha = u;
      x.fillStyle = V.paper; x.fillRect(0, 0, W, H); x.drawImage(grain, 0, 0);
      x.strokeStyle = V.ink; x.lineWidth = 4; x.strokeRect(60, 60, W - 120, H - 120); x.lineWidth = 1.5; x.strokeRect(76, 76, W - 152, H - 152);
      x.textAlign = 'center';
      x.fillStyle = V.ink; x.font = '700 34px "Hahmlet"'; try{ x.letterSpacing = '8px'; }catch(e){} x.fillText('DAILY ISSUE', W / 2 + 4, 760); try{ x.letterSpacing = '0px'; }catch(e){}
      x.fillStyle = V.red; x.font = '400 190px "Yellowtail"'; x.fillText('Priamos', W / 2, 960);
      x.fillStyle = V.ink; x.fillRect(W / 2 - 230, 1010, 460, 5);
      x.font = '900 52px "Hahmlet"'; x.fillText(spec.handle, W / 2, 1110);
      x.font = '700 40px "Noto Sans KR"'; x.fillStyle = 'rgba(43,29,20,.8)'; x.fillText('자세한 내용은 캡션에서', W / 2, 1190);
      x.font = '700 26px "Noto Sans KR"'; x.fillStyle = 'rgba(43,29,20,.6)'; x.fillText('그림: AI 생성 연출 이미지', W / 2, 1700);
      x.fillStyle = V.red; starburst(W / 2, 470, 70, 14, Math.sin(t) * .05); x.fillStyle = V.paper; x.font = '900 34px "Hahmlet"'; x.textBaseline = 'middle'; x.fillText(spec.label, W / 2, 474); x.textBaseline = 'alphabetic';
      x.textAlign = 'left'; x.restore();
    }
    window.renderFrame = t => {
      x.clearRect(0, 0, W, H);
      drawImage(t); header(t); label(t); headline(t); subtitle(t); credit(t); frame(); endCard(t);
      return document.getElementById('c').toDataURL('image/jpeg', .9);
    };
  }, spec);
  const N = Math.round(spec.duration * 30);
  for(let f = 0; f < N; f++){
    const d = await p.evaluate(t => window.renderFrame(t), f / 30);
    fs.writeFileSync(path.join(outDir, `f${String(f).padStart(4, '0')}.jpg`), Buffer.from(d.split(',')[1], 'base64'));
  }
  await b.close(); console.log('frames', N);
})();
