/*
 * 쇼츠 공장 — 화면과 무관한 계산 (자막 읽기, 장면 다듬기, Claude에게 보낼 요청문).
 * shorts/index.html 이 쓰고, Node에서도 그대로 불러 시험할 수 있다.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.ShortsCore = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // "1:02:03", "02:03", "00:01:02,500", "75" → 초. 읽을 수 없으면 null.
  function parseTime(s) {
    if (typeof s === 'number') return isFinite(s) ? s : null;
    s = String(s == null ? '' : s).trim().replace(',', '.');
    if (!s) return null;
    if (/^\d+(\.\d+)?$/.test(s)) return parseFloat(s);
    var m = /^(?:(\d{1,3}):)?(\d{1,3}):(\d{1,2}(?:\.\d+)?)$/.exec(s);
    if (!m) return null;
    return (+m[1] || 0) * 3600 + (+m[2]) * 60 + parseFloat(m[3]);
  }
  function pad(n) { return n < 10 ? '0' + n : String(n); }
  function fmtTime(sec) {
    sec = Math.max(0, Math.round(sec || 0));
    var h = Math.floor(sec / 3600), m = Math.floor(sec % 3600 / 60), s = sec % 60;
    return h ? h + ':' + pad(m) + ':' + pad(s) : m + ':' + pad(s);
  }

  // 유튜브 주소에서 영상 ID와 시작 시각(t=5944s, t=1h2m3s)을 꺼낸다.
  function parseYoutubeLink(url) {
    var u;
    try { u = new URL(String(url).trim()); } catch (e) { return null; }
    var host = u.hostname.replace(/^www\.|^m\./, '');
    var id = null;
    if (host === 'youtu.be') id = u.pathname.slice(1).split('/')[0];
    else if (host === 'youtube.com' || host === 'music.youtube.com') {
      if (u.pathname === '/watch') id = u.searchParams.get('v');
      else { var m = /^\/(?:shorts|live|embed)\/([^/?]+)/.exec(u.pathname); if (m) id = m[1]; }
    }
    if (!id || !/^[\w-]{6,20}$/.test(id)) return null;
    var t = 0, raw = u.searchParams.get('t') || u.searchParams.get('start') || '';
    var hms = /^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s?)?$/.exec(raw);
    if (raw && hms) t = (+hms[1] || 0) * 3600 + (+hms[2] || 0) * 60 + (+hms[3] || 0);
    return { id: id, t: t };
  }

  // 한국어 말 속도로 어림한 한 줄의 길이(초). 유튜브에서 복사한 자막에는 끝 시각이 없다.
  function spokenSeconds(text) { return Math.max(1.2, String(text).replace(/\s+/g, '').length * 0.2); }

  // 자막 글 → [{start, end, text}]. SRT·VTT, 유튜브 '스크립트 표시'에서 복사한 글,
  // "[1:23] 말" / "1:23 말" 꼴을 읽는다. 끝 시각을 모르면 다음 줄 시작과 말 길이로 어림한다.
  function parseTranscript(input) {
    var text = String(input || '').replace(/\r\n?/g, '\n').replace(/​/g, '');
    var cues = [];
    var stamp = '((?:\\d{1,3}:)?\\d{1,3}:\\d{2}(?:[.,]\\d{1,3})?)';
    if (text.indexOf('-->') >= 0) {
      var arrow = new RegExp('^\\s*' + stamp + '\\s*-->\\s*' + stamp);
      var lines = text.split('\n'), cur = null;
      lines.forEach(function (line) {
        var m = arrow.exec(line);
        if (m) { cur = { start: parseTime(m[1]), end: parseTime(m[2]), text: '', known: true }; cues.push(cur); }
        else if (!line.trim()) cur = null;
        else if (cur) cur.text += (cur.text ? ' ' : '') + line.replace(/<[^>]+>/g, '').trim();
      });
    } else {
      var head = new RegExp('^\\s*\\[?' + stamp + '\\]?\\s*(.*)$');
      var c = null;
      text.split('\n').forEach(function (line) {
        var m = head.exec(line);
        if (m && parseTime(m[1]) != null) { c = { start: parseTime(m[1]), end: null, text: m[2].trim() }; cues.push(c); }
        else if (c && line.trim()) c.text += (c.text ? ' ' : '') + line.trim();
      });
    }
    cues = cues.filter(function (q) { return q.text && q.start != null; }).sort(function (a, b) { return a.start - b.start; });
    cues.forEach(function (q, i) {
      var next = cues[i + 1] ? cues[i + 1].start : Infinity;
      if (!q.known || q.end == null || q.end <= q.start) q.end = Math.min(next, q.start + spokenSeconds(q.text));
      q.show = Math.min(next, Math.max(q.end, q.start + 1.2) + 0.4);   // 화면에 자막을 띄워 둘 끝
      delete q.known;
    });
    return cues;
  }

  function cuesInRange(cues, a, b) { return cues.filter(function (q) { return q.start < b && q.end > a; }); }
  function cueAt(cues, t) {
    var lo = 0, hi = cues.length - 1, hit = null;
    while (lo <= hi) {
      var mid = (lo + hi) >> 1;
      if (cues[mid].start <= t) { hit = cues[mid]; lo = mid + 1; } else hi = mid - 1;
    }
    return hit && t < hit.show ? hit : null;
  }

  // 말하는 구간만 이어 붙인 목록. gap초 넘게 말이 없으면 끊는다.
  function speechSpans(cues, a, b, gap) {
    var inside = cuesInRange(cues, a, b), spans = [];
    inside.forEach(function (q) {
      var s = Math.max(a, q.start - 0.15), e = Math.min(b, q.end + 0.25);
      var last = spans[spans.length - 1];
      if (last && s - last[1] < gap) last[1] = Math.max(last[1], e);
      else spans.push([s, e]);
    });
    return spans.length ? spans : [[a, b]];
  }

  var LANG_NAME = { ko: '한국어', en: '영어', ja: '일본어' };

  // Claude에게 보낼 요청문. 자막에 없는 내용을 제목에 지어내지 않도록 못 박는다.
  function buildPrompt(o) {
    var lines = cuesInRange(o.cues, o.range[0], o.range[1]).map(function (q) { return '[' + fmtTime(q.start) + '] ' + q.text; });
    return [
      '너는 긴 영상을 숏폼으로 자르는 편집자다. 아래는 영상의 자막이고, 각 줄 앞의 [분:초]는 그 말이 시작되는 시각이다.',
      '이 가운데 따로 떼어 놓아도 이해되고 끝까지 보게 되는 장면을 ' + o.count + '개 골라라.',
      '규칙:',
      '- 장면 하나의 길이는 ' + o.minLen + '~' + o.maxLen + '초. 말이 시작되는 줄에서 시작하고, 말이 마무리되는 곳에서 끝낸다.',
      '- 장면끼리 겹치지 않게 한다. 좋은 장면이 모자라면 개수를 줄인다.',
      '- title: 그 장면에 실제로 나온 말과 사실만으로 쓴 ' + (LANG_NAME[o.lang] || '한국어') + ' 제목, 24자 이내. 자막에 없는 내용, 과장, 낚시성 표현은 쓰지 않는다.',
      '- reason: 왜 골랐는지 한 문장.',
      'JSON 배열만 답한다. start와 end는 영상 처음부터 센 초(숫자)다.',
      '예: [{"start": 754, "end": 801, "title": "제목", "reason": "이유"}]',
      '',
      '자막 (' + fmtTime(o.range[0]) + ' ~ ' + fmtTime(o.range[1]) + '):',
      lines.join('\n')
    ].join('\n');
  }

  function clean(v, max) { return String(v == null ? '' : v).replace(/\s+/g, ' ').trim().slice(0, max); }

  // 영상에서 장면 그림을 뽑을 시각들. 구간을 고르게 나누되 minGap초보다 촘촘하게는 뽑지 않는다.
  function sampleTimes(a, b, maxFrames, minGap) {
    var len = b - a;
    if (!(len > 0)) return [];
    var n = Math.max(1, Math.min(maxFrames, Math.floor(len / minGap)));
    var step = len / n, out = [];
    for (var i = 0; i < n; i++) out.push(Math.round((a + step * (i + 0.5)) * 10) / 10);
    return out;
  }

  // 장면 그림(시각이 찍힌 모음 그림)을 함께 보낼 때의 요청문. 자막 글이 있으면 같이 붙인다.
  function buildVisionPrompt(o) {
    var lines = cuesInRange(o.cues || [], o.range[0], o.range[1]).map(function (q) { return '[' + fmtTime(q.start) + '] ' + q.text; });
    var out = [
      '너는 예능·토크·정보 영상을 숏폼으로 자르는 편집자다.',
      '첨부한 그림 ' + o.sheets + '장은 영상 한 편의 장면을 시간순으로 뽑아 붙인 것이다. 장면마다 왼쪽 위에 그 장면의 시각(분:초)이 찍혀 있다. 장면 안에 보이는 자막과 글자도 읽어라.'
    ];
    if (o.info) out.push('영상 정보(올린 사람이 적어 준 것): ' + o.info);
    out.push(
      '이 영상의 ' + fmtTime(o.range[0]) + ' ~ ' + fmtTime(o.range[1]) + ' 가운데 따로 떼어 놓아도 이해되고 끝까지 보게 되는 장면을 ' + o.count + '개 골라라.',
      '규칙:',
      '- 장면 하나의 길이는 ' + o.minLen + '~' + o.maxLen + '초. 그림 사이의 시각을 써도 된다. 이야기가 시작되는 곳에서 시작하고 마무리되는 곳에서 끝낸다.',
      '- 장면끼리 겹치지 않게 한다. 영상이 짧아 그만큼 나오지 않으면 개수를 줄인다.',
      '- title: 누가 무엇을 하는지 한눈에 보이는 ' + (LANG_NAME[o.lang] || '한국어') + ' 제목, 24자 이내. 화면 자막, 영상 정보, 자막 글에 실제로 있는 내용만 쓴다.',
      '- 사람을 얼굴로 알아보려 하지 않는다. 이름은 화면에 글자로 나왔거나 영상 정보에 적힌 것만 쓴다.',
      '- tag: 제목 위에 붙일 한두 낱말. 마땅치 않으면 빈 문자열.',
      '- comment: 편집자가 덧붙이는 한 줄 평, 22자 이내. 사실을 지어내지 않고 누구도 비방하지 않는다.',
      '- focus: 그 장면에서 주로 보여야 할 대상이 화면의 어느 쪽에 있는지 "left", "center", "right" 가운데 하나.',
      '- reason: 왜 골랐는지 한 문장.',
      'JSON 배열만 답한다. start와 end는 영상 처음부터 센 초(숫자)다.',
      '예: [{"start": 12, "end": 58, "title": "제목", "tag": "", "comment": "한 줄 평", "focus": "center", "reason": "이유"}]'
    );
    if (lines.length) out.push('', '자막 글:', lines.join('\n'));
    return out.join('\n');
  }

  // Claude가 돌려준 장면 목록을 쓸 수 있게 다듬는다: 숫자로 바꾸고, 구간 안으로 넣고, 길이를 맞추고, 겹치면 버린다.
  function normalizeClips(raw, o) {
    var list = Array.isArray(raw) ? raw : (raw && Array.isArray(raw.clips) ? raw.clips : []);
    var out = [];
    list.forEach(function (r) {
      if (!r || typeof r !== 'object') return;
      var s = parseTime(r.start), e = parseTime(r.end);
      if (s == null || e == null) return;
      s = Math.max(o.range[0], s); e = Math.min(o.range[1], e);
      // 시작은 가까운 자막 줄의 시작에 맞춘다
      var near = null;
      (o.cues || []).forEach(function (q) { if (Math.abs(q.start - s) <= 2 && (!near || Math.abs(q.start - s) < Math.abs(near.start - s))) near = q; });
      if (near) s = near.start;
      if (e - s > o.maxLen + 10) e = s + o.maxLen;
      if (e - s < 8) return;
      var focus = String(r.focus || '').toLowerCase();
      out.push({ start: Math.round(s * 10) / 10, end: Math.round(e * 10) / 10,
        title: clean(r.title, 60), reason: clean(r.reason, 200), tag: clean(r.tag, 16), comment: clean(r.comment, 40),
        pan: focus === 'left' ? 18 : focus === 'right' ? 82 : 50 });
    });
    out.sort(function (a, b) { return a.start - b.start; });
    var kept = [];
    out.forEach(function (c) { if (!kept.length || c.start >= kept[kept.length - 1].end - 0.5) kept.push(c); });
    return kept;
  }

  // 파일 이름에 쓸 수 있게 제목을 다듬는다.
  function safeName(title) {
    var s = String(title || '').replace(/[\\/:*?"<>|\u0000-\u001f]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 40);
    return s || '쇼츠';
  }

  // 글자 폭을 재는 함수(measure)를 받아 maxWidth 안에 들어가게 줄을 나눈다. 띄어쓰기에서 먼저 끊고, 긴 낱말은 글자에서 끊는다.
  function wrapText(text, maxWidth, measure) {
    var lines = [], line = '';
    String(text).split(/\s+/).filter(Boolean).forEach(function (word) {
      var tryLine = line ? line + ' ' + word : word;
      if (measure(tryLine) <= maxWidth) { line = tryLine; return; }
      if (line) { lines.push(line); line = ''; }
      if (measure(word) <= maxWidth) { line = word; return; }
      Array.from(word).forEach(function (ch) {
        if (measure(line + ch) > maxWidth && line) { lines.push(line); line = ch; } else line += ch;
      });
    });
    if (line) lines.push(line);
    return lines;
  }

  return {
    parseTime: parseTime, fmtTime: fmtTime, parseYoutubeLink: parseYoutubeLink, parseTranscript: parseTranscript,
    cuesInRange: cuesInRange, cueAt: cueAt, speechSpans: speechSpans, buildPrompt: buildPrompt,
    buildVisionPrompt: buildVisionPrompt, sampleTimes: sampleTimes,
    normalizeClips: normalizeClips, safeName: safeName, wrapText: wrapText
  };
});
