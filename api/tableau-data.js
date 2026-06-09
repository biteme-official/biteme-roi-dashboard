const TABLEAU_SERVER = 'https://prod-apnortheast-a.online.tableau.com';
const SITE_NAME = 'biteme01';
const API_VER = '3.24';

const VIEWS = [
  { id: 'e53fb200-eb4b-42db-98f2-4c30ba519577', key: 'platform', hasSub: true, subPrefix: 'pf_' },
  { id: 'c75b28ac-3bf1-4f05-9633-f4dabe0782b8', key: 'ss_total' },
  { id: 'd846cbe3-1720-42f8-b5ff-3f9eaca3704f', key: 'ssfw' },
  { id: '8e53722f-55a7-41c7-88e6-a37aa8c65ea7', key: 'compira' },
  { id: '3062396f-f1fb-4d51-8014-5dac66a0a53e', key: 'coupang' },
  { id: 'df575f01-23f5-466d-8989-710881e9055c', key: 'b2b' },
  { id: 'ade7640b-6c24-4819-9de2-43e30af2941c', key: 'etc' },
  { id: 'e47c337f-2eeb-4f65-a61c-89d17694c9d3', key: 'overseas' },
  { id: 'f091ac20-f5ae-4b5d-98f1-5682ab0fada2', key: 'etc_channel', isChannelCM: true },
];

const AVG_MEASURES = new Set(['Avg. dau']);

const MONTH_NUM = {};
for (let i = 1; i <= 12; i++) MONTH_NUM[`${i}월`] = String(i).padStart(2, '0');

function parseCSVLine(line) {
  const result = [];
  let cur = '', inQ = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (inQ) {
      if (ch === '"') {
        if (i + 1 < line.length && line[i + 1] === '"') { cur += '"'; i++; }
        else inQ = false;
      } else cur += ch;
    } else {
      if (ch === '"') inQ = true;
      else if (ch === ',') { result.push(cur.trim()); cur = ''; }
      else cur += ch;
    }
  }
  result.push(cur.trim());
  return result;
}

function parseCSV(text) {
  if (text.charCodeAt(0) === 0xFEFF) text = text.slice(1);
  const lines = text.split('\n').filter(l => l.trim());
  if (lines.length < 2) return [];
  const headers = parseCSVLine(lines[0]);
  const rows = [];
  for (let i = 1; i < lines.length; i++) {
    const vals = parseCSVLine(lines[i]);
    if (vals.length < headers.length) continue;
    const row = {};
    headers.forEach((h, j) => { row[h] = vals[j]; });
    rows.push(row);
  }
  return rows;
}

function isoWeekKey(year, month, day) {
  const dt = new Date(parseInt(year), parseInt(month) - 1, parseInt(day));
  dt.setDate(dt.getDate() + 3 - (dt.getDay() + 6) % 7);
  const w1 = new Date(dt.getFullYear(), 0, 4);
  w1.setDate(w1.getDate() + 3 - (w1.getDay() + 6) % 7);
  const wn = 1 + Math.round((dt - w1) / 604800000);
  return `${dt.getFullYear()}-W${String(wn).padStart(2, '0')}`;
}

function roundVal(v) {
  if (Math.abs(v) >= 100) return Math.round(v);
  if (Math.abs(v) >= 1) return Math.round(v * 10) / 10;
  return Math.round(v * 10000) / 10000;
}

async function signIn() {
  const resp = await fetch(`${TABLEAU_SERVER}/api/${API_VER}/auth/signin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    body: JSON.stringify({
      credentials: {
        personalAccessTokenName: process.env.TABLEAU_PAT_NAME,
        personalAccessTokenSecret: process.env.TABLEAU_PAT_SECRET,
        site: { contentUrl: SITE_NAME }
      }
    })
  });
  if (!resp.ok) throw new Error(`Tableau sign-in failed: ${resp.status}`);
  const data = await resp.json();
  return { token: data.credentials.token, siteId: data.credentials.site.id };
}

async function fetchViewCSV(token, siteId, viewId) {
  const url = `${TABLEAU_SERVER}/api/${API_VER}/sites/${siteId}/views/${viewId}/data`;
  const resp = await fetch(url, {
    headers: { 'X-Tableau-Auth': token, 'Accept': 'text/csv' }
  });
  if (!resp.ok) throw new Error(`View ${viewId} fetch failed: ${resp.status}`);
  return resp.text();
}

function processView(csv, viewCfg) {
  const rows = parseCSV(csv);
  const daily = {};

  for (const row of rows) {
    const dayRaw = row['Day of day'];
    const monthRaw = row['Month of day'];
    const yearRaw = row['Year of day'];
    const measure = row['Measure Names'];
    const valueRaw = row['Measure Values'];
    const salesType = row['매출구분'];

    if (!dayRaw || !monthRaw || !yearRaw) continue;
    const month = MONTH_NUM[monthRaw];
    if (!month) continue;

    const day = String(parseInt(dayRaw)).padStart(2, '0');
    const year = yearRaw.trim();
    const value = parseFloat(valueRaw) || 0;
    const dateStr = `${year}-${month}-${day}`;

    if (viewCfg.isChannelCM) {
      if (!daily['__channel_cm']) daily['__channel_cm'] = {};
      if (!daily['__channel_cm'][dateStr]) daily['__channel_cm'][dateStr] = {};
      const ch = salesType || 'All';
      daily['__channel_cm'][dateStr][ch] = (daily['__channel_cm'][dateStr][ch] || 0) + value;
      continue;
    }

    if (!measure) continue;
    const keys = [viewCfg.key];
    if (viewCfg.hasSub && salesType) keys.push(`${viewCfg.subPrefix}${salesType}`);

    for (const key of keys) {
      if (!daily[key]) daily[key] = {};
      if (!daily[key][dateStr]) daily[key][dateStr] = {};
      if (key === viewCfg.key && viewCfg.hasSub) {
        daily[key][dateStr][measure] = (daily[key][dateStr][measure] || 0) + value;
      } else {
        daily[key][dateStr][measure] = value;
      }
    }
  }
  return daily;
}

function aggregate(allDaily) {
  const views = {};

  for (const [vk, dayMap] of Object.entries(allDaily)) {
    const Y = {}, Q = {}, M = {}, W = {}, D = {};
    const cnt = { Y: {}, Q: {}, M: {}, W: {} };

    for (const [ds, measures] of Object.entries(dayMap)) {
      const [yr, mo] = ds.split('-');
      const yk = yr;
      const mk = `${yr}-${mo}`;
      const qk = `${yr}-Q${Math.ceil(parseInt(mo) / 3)}`;
      const wk = isoWeekKey(yr, mo, ds.split('-')[2]);

      D[ds] = {};
      for (const [m, v] of Object.entries(measures)) {
        D[ds][m] = roundVal(v);
      }

      for (const [m, v] of Object.entries(measures)) {
        for (const [gKey, bucket, cBucket] of [[yk, Y, cnt.Y], [qk, Q, cnt.Q], [mk, M, cnt.M], [wk, W, cnt.W]]) {
          if (!bucket[gKey]) bucket[gKey] = {};
          if (!cBucket[gKey]) cBucket[gKey] = {};
          bucket[gKey][m] = (bucket[gKey][m] || 0) + v;
          cBucket[gKey][m] = (cBucket[gKey][m] || 0) + 1;
        }
      }
    }

    for (const [gName, bucket] of [['Y', Y], ['Q', Q], ['M', M], ['W', W]]) {
      for (const [pk, measures] of Object.entries(bucket)) {
        for (const m of AVG_MEASURES) {
          if (measures[m] != null && cnt[gName]?.[pk]?.[m]) {
            measures[m] = measures[m] / cnt[gName][pk][m];
          }
        }
        for (const [m, v] of Object.entries(measures)) {
          measures[m] = roundVal(v);
        }
      }
    }

    views[vk] = { Y, Q, M, W, D };
  }
  return views;
}

function aggregateChannelCM(dailyChannels) {
  const Y = {}, Q = {}, M = {}, W = {}, D = {};
  for (const [ds, channels] of Object.entries(dailyChannels)) {
    const [yr, mo] = ds.split('-');
    const yk = yr;
    const mk = `${yr}-${mo}`;
    const qk = `${yr}-Q${Math.ceil(parseInt(mo) / 3)}`;
    const wk = isoWeekKey(yr, mo, ds.split('-')[2]);

    D[ds] = {};
    for (const [ch, v] of Object.entries(channels)) {
      D[ds][ch] = roundVal(v);
    }
    for (const [ch, v] of Object.entries(channels)) {
      for (const [gKey, bucket] of [[yk, Y], [qk, Q], [mk, M], [wk, W]]) {
        if (!bucket[gKey]) bucket[gKey] = {};
        bucket[gKey][ch] = roundVal((bucket[gKey][ch] || 0) + v);
      }
    }
  }
  return { Y, Q, M, W, D };
}

function sumViews(views, componentKeys) {
  const result = { Y: {}, Q: {}, M: {}, W: {}, D: {} };
  for (const gran of ['Y', 'Q', 'M', 'W', 'D']) {
    const allP = new Set();
    for (const k of componentKeys) {
      if (views[k]?.[gran]) Object.keys(views[k][gran]).forEach(p => allP.add(p));
    }
    for (const p of allP) {
      result[gran][p] = {};
      for (const k of componentKeys) {
        const src = views[k]?.[gran]?.[p];
        if (!src) continue;
        for (const [m, v] of Object.entries(src)) {
          result[gran][p][m] = roundVal((result[gran][p][m] || 0) + v);
        }
      }
    }
  }
  return result;
}

module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  if (req.method === 'OPTIONS') return res.status(200).end();

  let token;
  try {
    const auth = await signIn();
    token = auth.token;

    const csvs = await Promise.all(
      VIEWS.map(v => fetchViewCSV(token, auth.siteId, v.id))
    );

    const allDaily = {};
    let channelDaily = null;
    for (let i = 0; i < VIEWS.length; i++) {
      const daily = processView(csvs[i], VIEWS[i]);
      if (daily['__channel_cm']) {
        channelDaily = daily['__channel_cm'];
        delete daily['__channel_cm'];
      }
      Object.assign(allDaily, daily);
    }

    let views = aggregate(allDaily);

    views.brand_total = sumViews(views, ['ss_total', 'coupang', 'b2b', 'etc']);
    views.grand_total = sumViews(views, ['platform', 'brand_total', 'overseas']);

    const channel_cm = channelDaily ? aggregateChannelCM(channelDaily) : {};

    const allDates = new Set();
    for (const vd of Object.values(allDaily)) Object.keys(vd).forEach(d => allDates.add(d));
    const cutoff = [...allDates].sort().pop() || '';

    res.setHeader('Cache-Control', 's-maxage=300, stale-while-revalidate=60');
    res.status(200).json({ views, channel_cm, cutoff });

  } catch (err) {
    console.error('Tableau API error:', err);
    res.status(500).json({ error: err.message });
  } finally {
    if (token) {
      fetch(`${TABLEAU_SERVER}/api/${API_VER}/auth/signout`, {
        method: 'POST', headers: { 'X-Tableau-Auth': token }
      }).catch(() => {});
    }
  }
};
