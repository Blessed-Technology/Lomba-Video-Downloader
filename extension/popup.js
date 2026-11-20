const $ = id => document.getElementById(id);
const DEFAULT_SERVER = 'http://localhost:5000';
const SUPPORTED = /(^|\.)(youtube\.com|youtu\.be|vimeo\.com)$/;
const jobKey = (url, kind, height) => `${kind}|${height ?? ''}|${url}`;

let server = DEFAULT_SERVER;
let tabUrl = '';
let rowEls = {}; // key -> {btn, status}

const msg = (t, err = false) => { $('msg').textContent = t; $('msg').className = err ? 'err' : ''; };

function duration(s) {
  if (!s) return '';
  const h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), sec = s % 60;
  const p = n => String(n).padStart(2, '0');
  return h ? `${h}:${p(m)}:${p(sec)}` : `${m}:${p(sec)}`;
}

function supported(url) {
  try {
    const u = new URL(url);
    if (u.protocol !== 'https:' && u.protocol !== 'http:') return false;
    const h = u.hostname.toLowerCase();
    if (h === 'localhost' || h === '127.0.0.1' || h.endsWith('.local')) return false;
    return true;
  } catch { return false; }
}

function detectActiveVideoOnPage() {
  const host = location.hostname.toLowerCase();
  const centerY = window.innerHeight / 2;

  function findClosestLink(selector) {
    const links = Array.from(document.querySelectorAll(selector));
    let best = null, minDist = Infinity;
    for (const a of links) {
      const rect = a.getBoundingClientRect();
      if (rect.bottom > 0 && rect.top < window.innerHeight) {
        const dist = Math.abs((rect.top + rect.bottom) / 2 - centerY);
        if (dist < minDist) {
          minDist = dist;
          best = a.href;
        }
      }
    }
    return best;
  }

  if (host.includes('tiktok.com')) {
    const link = findClosestLink('a[href*="/video/"]');
    if (link) return link;
  }
  if (host.includes('instagram.com')) {
    const link = findClosestLink('a[href*="/reel/"], a[href*="/p/"]');
    if (link) return link;
  }
  if (host.includes('twitter.com') || host.includes('x.com')) {
    const link = findClosestLink('a[href*="/status/"]');
    if (link) return link;
  }
  return null;
}

function isFeedOrHomeUrl(url) {
  try {
    const u = new URL(url);
    const p = u.pathname.replace(/\/+$/, '').toLowerCase();
    const h = u.hostname.toLowerCase();
    if (h.includes('tiktok.com')) {
      return !p || p === '/en' || p === '/foryou' || p === '/following' || p === '/explore';
    }
    if (h.includes('youtube.com')) {
      return !p || p === '/feed' || p === '/feed/explore';
    }
    if (h.includes('instagram.com')) {
      return !p || p === '/reels';
    }
    if (h.includes('twitter.com') || h.includes('x.com')) {
      return !p || p === '/home' || p === '/explore';
    }
    return false;
  } catch { return false; }
}

async function init() {
  const saved = await chrome.storage.local.get('server');
  server = (saved.server || DEFAULT_SERVER).replace(/\/+$/, '');
  $('server').value = server;

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  tabUrl = tab?.url || '';
  if (!supported(tabUrl)) {
    msg('Open a video page (YouTube, TikTok, Twitter/X, Instagram, etc.), then click the icon.');
    return;
  }

  // If on a feed/homepage, attempt to find the video on screen
  if (tab?.id && chrome.scripting && isFeedOrHomeUrl(tabUrl)) {
    try {
      const [res] = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: detectActiveVideoOnPage,
      });
      if (res?.result) {
        tabUrl = res.result;
      }
    } catch {}
  }

  if (isFeedOrHomeUrl(tabUrl)) {
    msg('Please open or click on the specific video you want to download (not the home feed), then try again.', true);
    return;
  }

  loadInfo();
}

async function loadInfo() {
  msg('Fetching video details...');
  try {
    const r = await fetch(server + '/api/info', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: tabUrl }),
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.error || 'Could not read this video.');
    render(d);
    msg('');
  } catch (e) {
    if (e instanceof TypeError) {
      msg(`Can't reach the server at ${server}. Start it with "python app.py" or change the address below.`, true);
    } else msg(e.message, true);
  }
}

function render(d) {
  $('thumb').src = d.thumbnail || '';
  $('title').textContent = d.title || 'Untitled';
  $('meta').textContent = [d.uploader, duration(d.duration)].filter(Boolean).join('  |  ');
  const ul = $('options'); ul.innerHTML = ''; rowEls = {};
  d.options.forEach(o => {
    const li = document.createElement('li');
    li.innerHTML = `<span class="label"></span><span class="size"></span><span class="status"></span><button>Download</button>`;
    li.querySelector('.label').textContent = o.label;
    li.querySelector('.size').textContent = o.size || '';
    const btn = li.querySelector('button'), status = li.querySelector('.status');
    btn.addEventListener('click', () => {
      btn.disabled = true;
      chrome.runtime.sendMessage({ type: 'start', server, url: tabUrl, kind: o.kind, height: o.height });
    });
    rowEls[jobKey(tabUrl, o.kind, o.height)] = { btn, status };
    ul.appendChild(li);
  });
  $('card').hidden = false;
  chrome.storage.session.get('progress').then(({ progress }) => applyProgress(progress || {}));
}

function applyProgress(progress) {
  for (const [key, st] of Object.entries(progress)) {
    const row = rowEls[key];
    if (!row) continue;
    const { btn, status } = row;
    status.className = 'status';
    if (st.status === 'preparing' || st.status === 'starting' || st.status === 'retrying') {
      btn.disabled = true;
      status.textContent = st.status === 'retrying' ? 'Retrying...' : `${st.pct || 0}%` + (st.eta ? ` | ${duration(st.eta)}` : '');
      if (st.status === 'retrying') msg(st.message);
    } else if (st.status === 'done') {
      btn.disabled = false; btn.textContent = 'Again';
      status.textContent = 'Saved';
      msg(st.message);
    } else if (st.status === 'error') {
      btn.disabled = false; btn.textContent = 'Resume';
      status.textContent = 'Failed'; status.classList.add('err');
      msg(st.message, true);
    }
  }
}

chrome.storage.onChanged.addListener((changes, area) => {
  if (area === 'session' && changes.progress) applyProgress(changes.progress.newValue || {});
});

$('save').addEventListener('click', async () => {
  let value = $('server').value.trim().replace(/\/+$/, '');
  try {
    const origin = new URL(value).origin;
    const isLocal = /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin);
    if (!isLocal) {
      const ok = await chrome.permissions.request({ origins: [origin + '/*'] });
      if (!ok) { msg('Permission to reach that server was not granted.', true); return; }
    }
  } catch { msg('Enter a full address like http://localhost:5000', true); return; }
  await chrome.storage.local.set({ server: value });
  server = value;
  msg('Server saved.');
  if (supported(tabUrl)) loadInfo();
});

init();
