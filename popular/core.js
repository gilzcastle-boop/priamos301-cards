/*
 * 유튜브 실시간 인기 — 공용 로직.
 * 화면(popular/index.html)과 수집기(tools/fetch_popular.js)가 같은 파일을 쓴다.
 * 수집 결과를 한 형식으로 맞추고, 이전 수집분과 합치고, 순위를 매긴다.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.PopularCore = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // 유튜브 카테고리 번호를 화면의 일곱 묶음으로 줄인다. 표에 없는 번호는 엔터테인먼트.
  var CATEGORIES = [
    { value: 'entertainment', label: '엔터테인먼트' },
    { value: 'gaming', label: '게임' },
    { value: 'sports', label: '스포츠' },
    { value: 'music', label: '음악' },
    { value: 'news', label: '뉴스·정치' },
    { value: 'science', label: '과학·기술' },
    { value: 'howto', label: '노하우·스타일' }
  ];
  var CATEGORY_OF = { '10': 'music', '20': 'gaming', '17': 'sports', '25': 'news', '28': 'science', '27': 'science', '26': 'howto' };
  var LANGS = [
    { value: 'ko', label: '한국어' },
    { value: 'ja', label: '일본어' },
    { value: 'en', label: '영어' }
  ];

  // 수집 계획. 2025-07-21부터 mostPopular 기본 차트는 음악·영화·게임 차트만 담으므로
  // 나머지 묶음은 카테고리 번호를 지정해 따로 받는다.
  var PLAN = { regions: ['KR', 'US', 'JP'], categories: ['24', '17', '25', '28', '26'] };

  var LONG_FORM_SECONDS = 180;            // 쇼츠는 최대 3분. 그보다 길면 롱폼으로 본다.
  var MIN_DELTA_MS = 5 * 60 * 1000;       // 이보다 가까운 두 수집은 증가 속도 계산에 쓰지 않는다.
  var CURRENT_WINDOW_MS = 60 * 60 * 1000; // 마지막 수집 1시간 안에 차트에 있었으면 "지금 급상승".
  var TRENDING_WINDOW_MS = 24 * 3600 * 1000;
  var HOUR = 3600000, DAY = 86400000, KST = 9 * HOUR;

  function categoryOf(id) { return CATEGORY_OF[String(id)] || 'entertainment'; }
  function num(v) { return v == null || v === '' || isNaN(Number(v)) ? null : Number(v); }

  // "PT4H37M30S" → 16650
  function parseDuration(iso) {
    var m = /^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$/.exec(iso || '');
    if (!m) return 0;
    return (+m[1] || 0) * 86400 + (+m[2] || 0) * 3600 + (+m[3] || 0) * 60 + (+m[4] || 0);
  }

  // 언어: API가 알려 주면 그 값, 없으면 제목·채널명의 글자로 판단한다.
  // 로마자뿐인 제목은 영어로 보되, 한 나라 음악 차트에만 오른 곡은 그 나라 말로 추정한다(영어 제목 K팝 등).
  function detectLang(title, channel, regions, hint, category) {
    if (hint) {
      var h = String(hint).toLowerCase().slice(0, 2);
      return h === 'ko' || h === 'ja' || h === 'en' ? h : 'other';
    }
    var text = (title || '') + ' ' + (channel || '');
    var r = regions || [];
    if (/[぀-ヿ]/.test(text)) return 'ja';
    if (/[가-힯㄰-㆏]/.test(text)) return 'ko';
    if (/[一-鿿]/.test(text)) return r.indexOf('JP') >= 0 ? 'ja' : 'other';
    if (/[Ѐ-ӿ؀-ۿऀ-ॿ฀-๿]/.test(text)) return 'other';
    if (category === 'music' && r.length === 1 && r[0] === 'KR') return 'ko';
    if (category === 'music' && r.length === 1 && r[0] === 'JP') return 'ja';
    return 'en';
  }

  // YouTube Data API v3의 video 리소스 한 건 → 공통 형식
  function fromApi(v, region, rank) {
    var sn = v.snippet || {}, st = v.statistics || {}, cd = v.contentDetails || {}, status = v.status || {};
    return {
      videoId: v.id, title: sn.title || '', channelName: sn.channelTitle || '', channelId: sn.channelId || '',
      publishedAt: sn.publishedAt || null, durationSeconds: parseDuration(cd.duration),
      viewCount: num(st.viewCount), likeCount: num(st.likeCount), commentCount: num(st.commentCount),
      categoryId: String(sn.categoryId || ''), license: status.license || null,
      langHint: sn.defaultAudioLanguage || sn.defaultLanguage || null, region: region, rank: rank
    };
  }

  // PlayMCP YouTubeData 커넥터의 영상 한 건 → 공통 형식 (라이선스·언어 정보는 오지 않는다)
  function fromTool(v, region, rank) {
    return {
      videoId: v.videoId, title: v.title || '', channelName: v.channelTitle || '', channelId: v.channelId || '',
      publishedAt: v.publishedAt || null, durationSeconds: parseDuration(v.duration),
      viewCount: num(v.viewCount), likeCount: num(v.likeCount), commentCount: num(v.commentCount),
      categoryId: String(v.categoryId || ''), license: null, langHint: null, region: region, rank: rank
    };
  }

  // 커넥터 응답 한 덩어리({regionCode, videos}) → 공통 형식 목록. 모양이 다르면 빈 목록.
  function sightingsFromTool(payload, fallbackRegion) {
    var p = payload;
    if (typeof p === 'string') { try { p = JSON.parse(p); } catch (e) { return []; } }
    if (p && !p.videos && p.result) p = p.result;
    if (typeof p === 'string') { try { p = JSON.parse(p); } catch (e) { return []; } }
    if (!p || !Array.isArray(p.videos)) return [];
    var region = p.regionCode || fallbackRegion || 'KR';
    return p.videos.filter(function (v) { return v && v.videoId; })
      .map(function (v, i) { return fromTool(v, region, i + 1); });
  }

  // ── YouTube Data API v3로 한 번 수집 ──
  // 차트: videos.list chart=mostPopular (호출당 1단위) × 나라 × (기본 + 카테고리 5)
  // 재사용 허용: search.list videoLicense=creativeCommon, 최근 7일 조회수순 (호출당 100단위) × 나라
  var API_BASE = 'https://www.googleapis.com/youtube/v3/';
  var VIDEO_PARTS = 'snippet,contentDetails,statistics,status';
  var LANG_OF_REGION = { KR: 'ko', JP: 'ja', US: 'en' };

  function apiGet(fetchFn, key, path, params) {
    var qs = Object.keys(params).filter(function (k) { return params[k] != null; })
      .map(function (k) { return encodeURIComponent(k) + '=' + encodeURIComponent(params[k]); }).join('&');
    return fetchFn(API_BASE + path + '?' + qs, { headers: { 'X-Goog-Api-Key': key } }).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (body) {
        if (res.ok) return body;
        var e = body.error || {};
        var reason = (e.errors && e.errors[0] && e.errors[0].reason) || '';
        var msg = e.message || ('HTTP ' + res.status);
        var err = new Error(msg);
        err.status = res.status;
        // 남은 호출도 같은 이유로 실패하는 오류는 kind를 붙여 수집을 멈춘다.
        if (/API key not valid|API key expired|unregistered callers/i.test(msg)) err.kind = 'key';
        else if (/quota|rateLimitExceeded|dailyLimitExceeded/i.test(reason + ' ' + msg)) err.kind = 'quota';
        else if (reason === 'accessNotConfigured' || /has not been used in project|is disabled/i.test(msg)) err.kind = 'disabled';
        else if (reason === 'ipRefererBlocked' || /referer|referrer|IP address/i.test(msg)) err.kind = 'restricted';
        throw err;
      });
    });
  }

  // opts: { fetch, key, regions?, reusable?: false면 재사용 허용 검색을 건너뜀, now?, onProgress?(done, total) }
  // → { sightings, failed: [차트 이름], fatal: 멈추게 한 오류 | null, units: 쓴 할당량 }
  function collectFromApi(opts) {
    var fetchFn = opts.fetch, key = opts.key;
    var regions = opts.regions || PLAN.regions;
    var jobs = [];
    regions.forEach(function (region) {
      [null].concat(PLAN.categories).forEach(function (cat) {
        jobs.push({ chart: true, region: region, cat: cat, label: region + '/' + (cat || '기본') });
      });
    });
    if (opts.reusable !== false) {
      regions.forEach(function (region) { jobs.push({ chart: false, region: region, label: region + '/재사용 허용' }); });
    }
    var out = { sightings: [], failed: [], fatal: null, units: 0 };
    var since = new Date((opts.now || Date.now()) - 7 * DAY).toISOString();

    function run(job) {
      if (job.chart) {
        out.units += 1;
        return apiGet(fetchFn, key, 'videos', {
          part: VIDEO_PARTS, chart: 'mostPopular', regionCode: job.region, videoCategoryId: job.cat, maxResults: 50
        }).then(function (body) {
          return (body.items || []).map(function (v, i) { return fromApi(v, job.region, i + 1); });
        });
      }
      out.units += 100;
      return apiGet(fetchFn, key, 'search', {
        part: 'snippet', type: 'video', videoLicense: 'creativeCommon', order: 'viewCount', publishedAfter: since,
        regionCode: job.region, relevanceLanguage: LANG_OF_REGION[job.region], maxResults: 50
      }).then(function (body) {
        var ids = (body.items || []).map(function (x) { return x.id && x.id.videoId; }).filter(Boolean);
        if (!ids.length) return [];
        out.units += 1;
        return apiGet(fetchFn, key, 'videos', { part: VIDEO_PARTS, id: ids.join(',') }).then(function (detail) {
          return (detail.items || [])
            .filter(function (v) { return v.status && v.status.license === 'creativeCommon'; })
            .map(function (v, i) { var s = fromApi(v, job.region, i + 1); s.source = 'search'; return s; });
        });
      });
    }

    var i = 0;
    function next() {
      if (i >= jobs.length) return out;
      var job = jobs[i++];
      return run(job).then(function (rows) {
        out.sightings = out.sightings.concat(rows);
      }, function (err) {
        out.failed.push(job.label);
        out.lastError = err;
        if (err.kind) { out.fatal = err; i = jobs.length; }
      }).then(function () {
        if (opts.onProgress) opts.onProgress(i, jobs.length);
        return next();
      });
    }
    return Promise.resolve().then(next);
  }

  function union(a, b) {
    var out = (a || []).slice();
    (b || []).forEach(function (x) { if (out.indexOf(x) < 0) out.push(x); });
    return out;
  }

  // 새로 본 영상들을 기존 상태에 합친다. 같은 영상을 다시 보면 직전 조회수를 남겨 증가 속도를 잰다.
  function merge(state, sightings, nowISO) {
    var now = Date.parse(nowISO);
    var byId = {};
    ((state && state.items) || []).forEach(function (it) { byId[it.videoId] = it; });

    var batch = {};
    sightings.forEach(function (s) {
      if (!s || !s.videoId) return;
      var b = batch[s.videoId];
      if (!b) {
        b = batch[s.videoId] = {};
        for (var k in s) b[k] = s[k];
        b.regions = [];
        b.chart = s.source !== 'search';
      } else {
        if (s.source !== 'search') b.chart = true;
        if (s.rank < b.rank) b.rank = s.rank;
        if (!b.license && s.license) b.license = s.license;
        if (!b.langHint && s.langHint) b.langHint = s.langHint;
        if ((s.viewCount || 0) > (b.viewCount || 0)) b.viewCount = s.viewCount;
      }
      if (s.region && b.regions.indexOf(s.region) < 0) b.regions.push(s.region);
    });

    Object.keys(batch).forEach(function (id) {
      var b = batch[id], old = byId[id];
      if (old && now < Date.parse(old.lastSeenAt)) {   // 순서가 뒤바뀐 옛 자료: 나라만 보탠다
        old.regions = union(old.regions, b.regions);
        return;
      }
      var regions = old ? union(old.regions, b.regions) : b.regions;
      var item = {
        videoId: id, title: b.title, channelName: b.channelName, channelId: b.channelId,
        publishedAt: b.publishedAt || (old && old.publishedAt) || null,
        durationSeconds: b.durationSeconds || (old && old.durationSeconds) || 0,
        viewCount: b.viewCount, likeCount: b.likeCount, commentCount: b.commentCount,
        categoryId: b.categoryId, category: categoryOf(b.categoryId),
        license: b.license || (old && old.license) || null,
        langHint: b.langHint || (old && old.langHint) || null,
        regions: regions, rank: b.rank, onChart: b.chart,
        firstSeenAt: old ? old.firstSeenAt : nowISO, lastSeenAt: nowISO,
        prevViewCount: old ? old.prevViewCount : null, prevSeenAt: old ? old.prevSeenAt : null
      };
      if (old && now - Date.parse(old.lastSeenAt) >= MIN_DELTA_MS && old.viewCount != null) {
        item.prevViewCount = old.viewCount;
        item.prevSeenAt = old.lastSeenAt;
      }
      item.lang = detectLang(item.title, item.channelName, regions, item.langHint, item.category);
      byId[id] = item;
    });

    var prevUpdated = state && state.updatedAt;
    return {
      schema: 1,
      updatedAt: !prevUpdated || now > Date.parse(prevUpdated) ? nowISO : prevUpdated,
      items: Object.keys(byId).map(function (k) { return byId[k]; })
    };
  }

  // 오래 차트에서 사라진 영상은 버린다.
  function prune(state, nowISO, keepDays) {
    var cutoff = Date.parse(nowISO) - keepDays * DAY;
    state.items = state.items.filter(function (it) { return Date.parse(it.lastSeenAt) >= cutoff; });
    return state;
  }

  // 시간당 조회수 증가. 직전 수집이 있으면 그 사이 증가분, 없으면 게시 후 평균.
  function velocity(it) {
    var last = Date.parse(it.lastSeenAt);
    if (it.prevViewCount != null && it.prevSeenAt) {
      var dt = last - Date.parse(it.prevSeenAt);
      if (dt >= MIN_DELTA_MS) {
        return { perHour: Math.max(0, (it.viewCount || 0) - it.prevViewCount) / (dt / HOUR), basis: 'delta' };
      }
    }
    var age = Math.max(HOUR, last - Date.parse(it.publishedAt || it.firstSeenAt));
    return { perHour: (it.viewCount || 0) / (age / HOUR), basis: 'average' };
  }

  function kstDay(ms) { return new Date(ms + KST).toISOString().slice(0, 10); }

  // 조건에 맞는 영상을 골라 순위대로 돌려준다.
  // 차트 목록에는 차트에 오른 영상만, '재사용 허용만'에는 CC 라이선스 영상(차트 + 검색 수집분)만 나온다.
  // f: { sort: 'trending'|'views', period: 'all'|'today'|'week', category, lang, longOnly, reusableOnly, q,
  //      keepStale: 하루 넘게 차트에 없던 영상도 급상승 목록에 남긴다(저장한 영상 보기용) }
  function select(state, f, nowMs) {
    var updated = Date.parse(state.updatedAt);
    var q = (f.q || '').trim().toLowerCase();
    var today = kstDay(nowMs);
    var out = [];
    (state.items || []).forEach(function (it) {
      var last = Date.parse(it.lastSeenAt), first = Date.parse(it.firstSeenAt);
      if (f.sort !== 'views' && !f.keepStale && updated - last > TRENDING_WINDOW_MS) return;
      if (f.period === 'today' && kstDay(first) !== today) return;
      if (f.period === 'week' && nowMs - first > 7 * DAY) return;
      if (f.category && f.category !== 'all' && it.category !== f.category) return;
      if (f.lang && f.lang !== 'all' && it.lang !== f.lang) return;
      if (f.longOnly && !(it.durationSeconds > LONG_FORM_SECONDS)) return;
      if (f.reusableOnly ? it.license !== 'creativeCommon' : it.onChart === false) return;
      if (q && (it.title + '\n' + it.channelName).toLowerCase().indexOf(q) < 0) return;
      var v = velocity(it);
      out.push({ item: it, perHour: v.perHour, basis: v.basis, onChart: it.onChart !== false,
        current: updated - last <= CURRENT_WINDOW_MS });
    });
    out.sort(f.sort === 'views'
      ? function (a, b) { return (b.item.viewCount || 0) - (a.item.viewCount || 0); }
      : function (a, b) { return b.perHour - a.perHour || (b.item.viewCount || 0) - (a.item.viewCount || 0); });
    return out;
  }

  function hasLicenseData(state) {
    return (state.items || []).some(function (it) { return it.license != null; });
  }

  // ── 표시 형식 ──
  function oneDecimal(x) { return String(Math.round(x * 10) / 10); }
  function fmtCount(n) {
    n = Number(n) || 0;
    if (n >= 1e8) return oneDecimal(n / 1e8) + '억';
    if (n >= 1e4) return oneDecimal(n / 1e4) + '만';
    if (n >= 1e3) return oneDecimal(n / 1e3) + '천';
    return String(Math.round(n));
  }
  function pad(n) { return n < 10 ? '0' + n : String(n); }
  function fmtDuration(s) {
    s = Math.max(0, Math.floor(s || 0));
    var h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), sec = s % 60;
    return h ? h + ':' + pad(m) + ':' + pad(sec) : m + ':' + pad(sec);
  }
  function fmtAge(iso, nowMs) {
    if (!iso) return '';
    var d = Math.max(0, nowMs - Date.parse(iso));
    if (d < HOUR) return '방금';
    if (d < DAY) return Math.floor(d / HOUR) + '시간 전';
    var days = Math.floor(d / DAY);
    if (days < 7) return days + '일 전';
    if (days < 30) return Math.floor(days / 7) + '주 전';
    if (days < 365) return Math.floor(days / 30) + '개월 전';
    return Math.floor(days / 365) + '년 전';
  }
  // "11월 11일 19:01" (한국 시간)
  function fmtStamp(iso) {
    var d = new Date(Date.parse(iso) + KST);
    return (d.getUTCMonth() + 1) + '월 ' + d.getUTCDate() + '일 ' + pad(d.getUTCHours()) + ':' + pad(d.getUTCMinutes());
  }

  return {
    CATEGORIES: CATEGORIES, LANGS: LANGS, PLAN: PLAN,
    LONG_FORM_SECONDS: LONG_FORM_SECONDS, CURRENT_WINDOW_MS: CURRENT_WINDOW_MS,
    categoryOf: categoryOf, parseDuration: parseDuration, detectLang: detectLang,
    fromApi: fromApi, fromTool: fromTool, sightingsFromTool: sightingsFromTool,
    collectFromApi: collectFromApi, merge: merge, prune: prune, velocity: velocity, select: select, hasLicenseData: hasLicenseData,
    fmtCount: fmtCount, fmtDuration: fmtDuration, fmtAge: fmtAge, fmtStamp: fmtStamp
  };
});
