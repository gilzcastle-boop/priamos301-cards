#!/usr/bin/env node
/*
 * 유튜브 인기 영상 수집기 → popular/data.json
 *
 *   YOUTUBE_API_KEY=... node tools/fetch_popular.js
 *       YouTube Data API v3 (videos.list, chart=mostPopular)로 한국·미국·일본 차트를 받아 합친다.
 *       한 번 돌 때 호출 18회(나라 3 × 차트 6), 할당량 18단위.
 *
 *   node tools/fetch_popular.js --ingest a.json b.json ...
 *       PlayMCP YouTubeData 커넥터 응답({regionCode, videos, fetchedAt})을 받은 순서대로 합친다.
 *
 * 옵션: --out <파일>  --regions KR,US,JP  --keep-days 14  --fresh(이전 data.json을 무시)
 */
'use strict';
const fs = require('fs');
const path = require('path');
const core = require('../popular/core.js');

const args = process.argv.slice(2);
function opt(name, fallback) {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
}
const out = path.resolve(opt('--out', path.join(__dirname, '..', 'popular', 'data.json')));
const keepDays = Number(opt('--keep-days', '14'));
const regions = opt('--regions', core.PLAN.regions.join(',')).split(',').filter(Boolean);
const fresh = args.includes('--fresh');
const ingestAt = args.indexOf('--ingest');
const ingestFiles = ingestAt >= 0 ? args.slice(ingestAt + 1).filter((a) => !a.startsWith('--')) : null;

function loadState() {
  if (fresh || !fs.existsSync(out)) return { schema: 1, updatedAt: null, items: [] };
  return JSON.parse(fs.readFileSync(out, 'utf8'));
}

function save(state, source) {
  core.prune(state, state.updatedAt, keepDays);
  state.items.sort((a, b) => (b.viewCount || 0) - (a.viewCount || 0));
  // 영상 한 건을 한 줄에 써서 파일은 작게, 변경 내역은 줄 단위로 보이게 한다.
  const head = JSON.stringify({ schema: 1, updatedAt: state.updatedAt, source }).slice(0, -1);
  const body = state.items.map((it) => JSON.stringify(it)).join(',\n');
  fs.mkdirSync(path.dirname(out), { recursive: true });
  fs.writeFileSync(out, `${head},"items":[\n${body}\n]}\n`);
  console.log(`${path.relative(process.cwd(), out)}: 영상 ${state.items.length}개, 수집 ${core.fmtStamp(state.updatedAt)} (KST)`);
}

async function fetchChart(key, region, categoryId) {
  const url = new URL('https://www.googleapis.com/youtube/v3/videos');
  url.search = new URLSearchParams({
    part: 'snippet,contentDetails,statistics,status', chart: 'mostPopular',
    regionCode: region, maxResults: '50', key
  });
  if (categoryId) url.searchParams.set('videoCategoryId', categoryId);
  const res = await fetch(url);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const reason = body.error && body.error.message ? body.error.message : `HTTP ${res.status}`;
    throw new Error(reason);
  }
  return (body.items || []).map((v, i) => core.fromApi(v, region, i + 1));
}

async function collectFromApi(key) {
  const now = new Date().toISOString();
  const sightings = [];
  const failed = [];
  for (const region of regions) {
    for (const categoryId of [null, ...core.PLAN.categories]) {
      const label = `${region}/${categoryId || '기본'}`;
      try {
        const rows = await fetchChart(key, region, categoryId);
        sightings.push(...rows);
        console.log(`${label}: ${rows.length}개`);
      } catch (e) {
        failed.push(label);
        console.warn(`${label}: 건너뜀 — ${e.message}`);
      }
    }
  }
  if (!sightings.length) throw new Error('받은 영상이 없습니다. API 키와 할당량을 확인하세요.');
  const state = core.merge(loadState(), sightings, now);
  save(state, 'YouTube Data API v3 videos.list chart=mostPopular');
  if (failed.length) console.warn(`받지 못한 차트: ${failed.join(', ')}`);
}

function ingest(files) {
  const batches = files.map((f) => JSON.parse(fs.readFileSync(f, 'utf8')))
    .filter((b) => b && b.fetchedAt && Array.isArray(b.videos))
    .sort((a, b) => Date.parse(a.fetchedAt) - Date.parse(b.fetchedAt));
  if (!batches.length) throw new Error('합칠 응답 파일이 없습니다 (fetchedAt, videos 필요).');
  let state = loadState();
  for (const b of batches) {
    state = core.merge(state, core.sightingsFromTool(b, b.regionCode), b.fetchedAt);
  }
  save(state, 'PlayMCP YouTubeData get_trending_videos (YouTube Data API mostPopular)');
}

(async () => {
  if (ingestFiles) return ingest(ingestFiles);
  const key = process.env.YOUTUBE_API_KEY;
  if (!key) {
    console.error('YOUTUBE_API_KEY 환경변수가 없습니다. Google Cloud 콘솔에서 YouTube Data API v3 키를 만들어 넣어 주세요.');
    process.exit(2);
  }
  await collectFromApi(key);
})().catch((e) => { console.error(`실패: ${e.message}`); process.exit(1); });
