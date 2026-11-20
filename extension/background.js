// Runs downloads in the background so they continue after the popup closes.
// Progress is written to chrome.storage.session, which the popup listens to.
// Each storage write also keeps the service worker alive during polling.

const running = new Set();
const sleep = ms => new Promise(r => setTimeout(r, ms));
const jobKey = (url, kind, height) => `${kind}|${height ?? ''}|${url}`;

async function setState(key, patch) {
  const { progress = {} } = await chrome.storage.session.get('progress');
  progress[key] = { ...(progress[key] || {}), ...patch };
  await chrome.storage.session.set({ progress });
}

async function postJson(path, server, body) {
  const r = await fetch(server + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  return { ok: r.ok, status: r.status, data };
}

async function runJob({ server, url, kind, height }) {
  const key = jobKey(url, kind, height);
  if (running.has(key)) return;
  running.add(key);
  await setState(key, { status: 'starting', pct: 0, eta: null, message: '' });
  chrome.action.setBadgeBackgroundColor({ color: '#FED063' });

  try {
    // 1. Start (or resume) the server-side job.
    let job;
    while (!job) {
      try {
        const res = await postJson('/api/prepare', server, { url, kind, height });
        if (!res.ok) throw new Error(res.data.error || 'Could not start the download.');
        job = res.data.job;
      } catch (e) {
        if (e instanceof TypeError) {
          await setState(key, { status: 'retrying', message: 'Server unreachable. Retrying...' });
          await sleep(3000);
        } else throw e;
      }
    }

    // 2. Poll until the server has the whole file. Network drops just retry.
    while (true) {
      let st;
      try {
        const r = await fetch(`${server}/api/status/${job}`);
        if (r.status === 404) {
          await postJson('/api/prepare', server, { url, kind, height }); // resumes partial files
          await sleep(1500);
          continue;
        }
        st = await r.json();
      } catch {
        await setState(key, { status: 'retrying', message: 'Connection lost. Reconnecting...' });
        await sleep(3000);
        continue;
      }

      if (st.status === 'error') throw new Error(st.error || 'Download failed. Try again to resume.');
      if (st.status === 'done') break;

      const pct = Math.floor(st.progress || 0);
      await setState(key, { status: 'preparing', pct, eta: st.eta || null, message: '' });
      chrome.action.setBadgeText({ text: pct + '%' });
      await sleep(1500);
    }

    // 3. Hand the finished file to Chrome's download manager with Save As dialog.
    await chrome.downloads.download({ url: `${server}/api/file/${job}`, saveAs: true });
    await setState(key, { status: 'done', pct: 100, message: 'File saved successfully.' });
    chrome.action.setBadgeText({ text: 'OK' });
    setTimeout(() => chrome.action.setBadgeText({ text: '' }), 8000);
  } catch (e) {
    await setState(key, { status: 'error', message: e.message });
    chrome.action.setBadgeText({ text: '!' });
    chrome.action.setBadgeBackgroundColor({ color: '#FF8A7A' });
  } finally {
    running.delete(key);
  }
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type === 'start') {
    runJob(msg); // fire and forget; popup watches storage for progress
    sendResponse({ started: true });
  }
  return false;
});
