/* GitRatio Bunny Takeover — native WebView frontend. No external JS/CSS dependencies. */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const state = { anime: null, episodes: [], selected: new Set(), library: [], page: 'home', submitting: false };
  let poll = null;
  let statusPending = null;
  let lastStatusItems = null;

  function notice(message, isError = false) {
    const node = $('notice');
    node.hidden = !message;
    node.textContent = message || '';
    node.style.borderColor = isError ? '#fb6074' : '#4be9ed';
  }
  async function call(method, ...args) {
    const api = window.pywebview && window.pywebview.api;
    if (!api || typeof api[method] !== 'function') {
      throw new Error('Native desktop bridge unavailable. Launch PaheBatcher through its installed app.');
    }
    return api[method](...args);
  }
  function setPage(page) {
    const known = ['home', 'episodes', 'downloads', 'player', 'library', 'settings', 'about'];
    if (!known.includes(page)) page = 'home';
    if (page === 'episodes' && !state.anime) page = 'home';
    state.page = page;
    document.querySelectorAll('.page').forEach((el) => el.classList.toggle('current', el.id === 'page-' + page));
    document.querySelectorAll('[data-nav]').forEach((el) => {
      const active = el.dataset.nav === page;
      el.classList.toggle('active', active);
      el.setAttribute('aria-current', active ? 'page' : 'false');
    });
    notice('');
    if (page === 'library' || page === 'player') refreshLibrary().catch(showError);
    if (page === 'downloads') refreshStatus().catch(showError);
    if (page === 'about') renderAboutUpdateStatus().catch(() => {});
  }
  function showError(error) {
    notice(error && error.message ? error.message : String(error), true);
    console.error(error);
  }
  function fmtNum(n) { return String(n).padStart(2, '0'); }
  function fmtBytes(n) {
    const bytes = Number(n) || 0;
    if (bytes > 1024 * 1024 * 1024) return (bytes / (1024 ** 3)).toFixed(2) + ' GB';
    if (bytes > 1024 * 1024) return (bytes / (1024 ** 2)).toFixed(1) + ' MB';
    return (bytes / 1024).toFixed(0) + ' KB';
  }
  function renderResults(items) {
    const root = $('search-results'); root.replaceChildren();
    $('result-count').textContent = items.length + ' result' + (items.length === 1 ? '' : 's');
    if (!items.length) {
      const block = document.createElement('div'); block.className = 'empty';
      block.textContent = 'No matching titles found. Try a different search.'; root.append(block); return;
    }
    items.forEach((item) => {
      const row = document.createElement('article'); row.className = 'result-card'; row.tabIndex = 0; row.setAttribute('role', 'button');
      const art = document.createElement('div'); art.className = 'poster'; art.textContent = (item.title || 'Anime').slice(0, 14);
      const info = document.createElement('div'); info.style.minWidth = '0';
      const h = document.createElement('h3'); h.textContent = item.title || 'Unknown title';
      const chips = document.createElement('div'); chips.className = 'chips';
      [item.type, item.year, item.episodes ? item.episodes + ' episodes' : ''].filter(Boolean).forEach((v, i) => {
        const chip = document.createElement('span'); chip.className = i === 0 ? 'chip pink' : 'chip'; chip.textContent = String(v); chips.append(chip);
      });
      const p = document.createElement('p'); p.textContent = 'Open to view source-provided episode information and download options.';
      info.append(h, chips, p); row.append(art, info);
      const open = () => loadSeries(String(item.session || ''));
      row.addEventListener('click', open);
      row.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
      root.append(row);
    });
  }
  async function search(e) {
    e.preventDefault(); const query = $('query').value.trim(); if (!query) return;
    const button = $('search-button'); button.disabled = true; button.textContent = 'Searching…'; notice('');
    try { renderResults(await call('search', query)); }
    catch (err) { showError(err); }
    finally { button.disabled = false; button.textContent = '⌕ Search'; }
  }
  async function loadSeries(session) {
    if (!session) return showError(new Error('This source did not provide a series identifier.'));
    notice('Loading episodes from the source…');
    try {
      const data = await call('scan', session);
      state.anime = data;
      state.episodes = Array.isArray(data.episodes) ? data.episodes : [];
      state.selected.clear();
      $('series-title').textContent = data.title || 'Unknown series';
      $('series-summary').textContent = state.episodes.length + ' episodes available';
      $('episode-count').textContent = '(' + state.episodes.length + ')';
      $('series-description').textContent = data.description || 'This source has not provided a synopsis.';
      renderEpisodes(); setPage('episodes');
    } catch (err) { showError(err); }
  }
  function renderEpisodes() {
    const root = $('episode-list'); root.replaceChildren();
    if (!state.episodes.length) { const empty = document.createElement('div'); empty.className = 'empty'; empty.textContent = 'No episodes returned by this source.'; root.append(empty); }
    state.episodes.forEach((ep, index) => {
      const row = document.createElement('label'); row.className = 'episode';
      const ck = document.createElement('input'); ck.type = 'checkbox'; ck.checked = state.selected.has(index);
      ck.setAttribute('aria-label', 'Select episode ' + ep.ep_str);
      const thumb = document.createElement('div'); thumb.className = 'ep-thumb'; thumb.textContent = fmtNum(ep.ep_str || index + 1);
      const desc = document.createElement('div'); desc.className = 'episode-text';
      const heading = document.createElement('strong'); heading.textContent = 'Ep ' + (ep.ep_str || index + 1) + ' — ' + (ep.title || 'Episode');
      const secondary = document.createElement('small'); secondary.textContent = (ep.audio || 'Audio from source') + ' · Episode ' + (index + 1);
      desc.append(heading, secondary); row.append(ck, thumb, desc);
      row.classList.toggle('selected', ck.checked);
      ck.addEventListener('change', () => {
        if (ck.checked) state.selected.add(index); else state.selected.delete(index);
        row.classList.toggle('selected', ck.checked); updateSelection();
      });
      root.append(row);
    });
    updateSelection();
  }
  function updateSelection() {
    const n = state.selected.size;
    const quality = Number($('quality').value || 720);
    const estimateMb = n * ({360: 50, 720: 90, 1080: 150}[quality] || 90);
    $('selection-summary').textContent = n ? n + ' episodes selected · ~' + fmtBytes(estimateMb * 1024 * 1024) + ' estimated' : 'Select episodes to enable download';
    $('download-selected').disabled = n === 0 || state.submitting;
    $('mobile-download-selected').disabled = n === 0 || state.submitting;
    $('download-selected').textContent = n ? '↓ Download ' + n + ' episode' + (n === 1 ? '' : 's') : '↓ Download';
    $('mobile-download-selected').textContent = $('download-selected').textContent;
  }
  function selectAll(on) { state.selected = new Set(on ? state.episodes.map((_ep, i) => i) : []); renderEpisodes(); }
  function selectRange() {
    const text = $('range').value.trim(); if (!text) return;
    const selected = new Set();
    for (const part of text.split(/[,\s]+/)) {
      const match = /^(\d+)(?:-(\d*))?$/.exec(part);
      if (!match) return showError(new Error('Invalid episode range: ' + part));
      const start = Number(match[1]); const end = match[2] === undefined ? start : (match[2] ? Number(match[2]) : state.episodes.length);
      if (start < 1 || end < start || end > 500) return showError(new Error('Episode range is outside supported bounds.'));
      for (let n = start; n <= end; n++) {
        const index = state.episodes.findIndex((ep, i) => Number(ep.ep_str || i + 1) === n);
        if (index >= 0) selected.add(index);
      }
    }
    state.selected = selected; renderEpisodes(); notice('');
  }
  async function savePrefs() {
    const settings = { quality: Number($('settings-quality').value), audio_lang: $('settings-audio').value, max_parallel: Number($('settings-parallel').value) };
    try {
      const saved = await call('save_settings', settings);
      if (!saved || !saved.ok) throw new Error('Settings were not saved.');
      $('quality').value = String(settings.quality); $('audio').value = settings.audio_lang; $('parallel').value = String(settings.max_parallel);
      notice('Settings saved.'); updateSelection();
    } catch (e) { showError(e); }
  }
  async function updatePrefFromDownload() {
    const values = {quality:Number($('quality').value),audio_lang:$('audio').value,max_parallel:Number($('parallel').value)};
    await call('save_settings', values);
    $('settings-quality').value = String(values.quality);$('settings-audio').value = values.audio_lang;$('settings-parallel').value = String(values.max_parallel);
    updateSelection();
  }
  async function downloadSelected() {
    if (!state.anime || !state.selected.size || state.submitting) return;
    state.submitting = true; updateSelection(); notice('');
    try {
      await updatePrefFromDownload();
      const result = await call('download', [...state.selected].sort((a,b) => a-b));
      if (!result || !result.started) throw new Error(result && result.error || 'Could not start download.');
      state.selected.clear();
      notice(result.pending ? 'Series queued for download.' : 'Download started. You can add another series.');
      setPage('downloads'); await refreshStatus();
    } catch (err) { showError(err); }
    finally { state.submitting = false; updateSelection(); }
  }
  async function refreshStatus() {
    if (statusPending) return statusPending;
    statusPending = renderStatus();
    try { await statusPending; } finally { statusPending = null; }
  }
  async function renderStatus() {
    const data = await call('status');
    $('download-title').textContent = data.title || 'No active download';
    $('download-percent').textContent = Math.round((data.fraction || 0) * 100) + '%';
    $('download-progress').style.width = Math.round((data.fraction || 0) * 100) + '%';
    $('download-details').textContent = data.message || 'No active download';
    $('home-status').textContent = data.active ? (data.title + ' · ' + Math.round((data.fraction || 0) * 100) + '% · ' + (data.queued || []).length + ' waiting') : (data.message || 'No active downloads');
    $('cancel').disabled = !data.active;
    updateSelection();
    const root = $('download-items');
    const signature = JSON.stringify([data.queued || [], data.items || []]);
    if (signature !== lastStatusItems) {
    root.replaceChildren();
    for (const item of data.queued || []) {
      const p = document.createElement('p');
      p.textContent = 'Queued: ' + item.title + ' · ' + item.episodes + ' episodes';
      root.append(p);
    }
    for (const item of data.items || []) {
      const p = document.createElement('p');
      p.textContent = 'Episode ' + item.episode + ' · ' + item.state + ' · ' + Math.round((item.fraction || 0) * 100) + '%';
      root.append(p);
    }
    lastStatusItems = signature;
    }
    if (data.active && !poll) poll = setInterval(() => refreshStatus().catch(showError), 2000);
    if (!data.active && poll) {clearInterval(poll);poll=null;}
  }
  async function refreshLibrary() {
    state.library = await call('library');
    const root = $('library-grid'); root.replaceChildren();
    const playlist = $('player-library'); playlist.replaceChildren();
    if (!state.library.length) {
      const block = document.createElement('div'); block.className = 'card empty'; block.textContent = 'No downloaded videos yet.'; root.append(block);
      playlist.textContent = 'No saved videos found. Download an episode to create a playlist.'; return;
    }
    state.library.forEach((item) => {
      const card = document.createElement('div'); card.className = 'card library-item';
      const art = document.createElement('div'); art.className = 'poster'; art.textContent = '▷ ' + item.name.split('.').pop().toUpperCase();
      const label = document.createElement('strong'); label.textContent = item.name;
      const info = document.createElement('p'); info.className = 'muted'; info.textContent = fmtBytes(item.size) + ' · ' + item.series;
      const play = document.createElement('button'); play.className = 'btn btn-pink'; play.textContent = '▷ Play'; play.addEventListener('click', () => openVideo(item.id));
      const format = document.createElement('select');
      format.setAttribute('aria-label', 'Output format for ' + item.name);
      for (const ext of ['mp4','mkv','webm']) {
        const opt = document.createElement('option'); opt.value = ext; opt.textContent = ext.toUpperCase(); format.append(opt);
      }
      const mode = document.createElement('select');
      mode.setAttribute('aria-label', 'Conversion mode for ' + item.name);
      for (const [value, label] of [['copy','Lossless remux'],['encode','Transcode (limited threads)']]) {
        const opt = document.createElement('option'); opt.value = value; opt.textContent = label; mode.append(opt);
      }
      const convert = document.createElement('button'); convert.className = 'btn'; convert.textContent = 'Convert copy';
      convert.addEventListener('click', async () => {
        if (state.converting) return;
        state.converting = true; convert.disabled = true;
        convert.textContent = 'Converting…';
        try {
          const result = await call('convert_media', item.id, format.value, mode.value === 'encode');
          if (!result || !result.ok) throw new Error('Conversion failed.');
          await refreshLibrary(); notice('Saved ' + result.name + '. Original preserved.');
        } catch (e) { showError(e); }
        finally { state.converting = false; convert.disabled = false; convert.textContent = 'Remux copy'; }
      });
      card.append(art,label,info);
      if (item.playable !== false) card.append(play);
      card.append(format,mode,convert); root.append(card);
      if (item.playable === false) return;
      const row = document.createElement('button'); row.className = 'btn'; row.style.cssText = 'width:100%;margin:5px 0;justify-content:flex-start;overflow:hidden;text-overflow:ellipsis'; row.textContent = '▷ ' + item.name; row.addEventListener('click', () => openVideo(item.id)); playlist.append(row);
    });
  }
  async function openVideo(id) {
    try { const result = await call('play', id); if (!result || !result.ok) throw new Error('Could not open this video.'); }
    catch (err) { showError(err); }
  }
  async function renderAboutUpdateStatus() {
    const info = await call('update_status');
    const label = $('about-update-status');
    if (info && info.available && typeof info.version === 'string') {
      label.textContent = 'A newer GitHub preview (v' + info.version + ') is available. Open Release notes below to get it manually.';
    } else if (info && info.checked) {
      label.textContent = 'No newer version reported, or GitHub was unavailable. Check Release notes for the latest preview.';
    } else {
      label.textContent = 'Checking GitHub release metadata once this session. No update files are downloaded.';
    }
  }
  async function showReleaseUpdate() {
    // The Python backend performs one bounded request per launch. This method
    // only reads the in-memory result; no browser network call or polling.
    try {
      const latest = await call('update_status');
      if (!latest || !latest.available || !/^\d+\.\d+\.\d+$/.test(latest.version || '')) return;
      $('release-update-label').textContent = 'PaheBatcher v' + latest.version + ' is available on GitHub.';
      $('release-update').hidden = false;
    } catch (error) {
      // Offline is normal; updates must never interrupt the downloader.
      console.debug('Update check unavailable.', error);
    }
  }
  async function startup() {
    const ready = await call('bootstrap');
    if (ready && ready.settings) {
      if (typeof ready.version === 'string' && /^\d+\.\d+\.\d+/.test(ready.version)) {
        $('about-version').textContent = 'v' + ready.version;
      }
      const s = ready.settings;
      for (const [id, value] of [['quality',s.quality],['audio',s.audio_lang],['parallel',s.max_parallel],['settings-quality',s.quality],['settings-audio',s.audio_lang],['settings-parallel',s.max_parallel]]) {
        $(id).value = String(value);
      }
      $('save-path').value = s.output_dir || '';
    }
    if (!ready.solver_ok) notice('The site solver is not ready. Check the bundled browser prerequisites.', true);
    await refreshStatus();
    setPage('home');
    // One delayed, in-memory result read: avoids holding up startup.
    setTimeout(showReleaseUpdate, 4000);
  }
  function hooks() {
    document.querySelectorAll('[data-nav]').forEach((el) => el.addEventListener('click', () => setPage(el.dataset.nav)));
    document.querySelectorAll('[data-nav-go]').forEach((el) => el.addEventListener('click', () => setPage(el.dataset.navGo)));
    $('search-form').addEventListener('submit', search);
    $('select-all').addEventListener('click', () => selectAll(true));
    $('select-none').addEventListener('click', () => selectAll(false));
    $('select-range').addEventListener('click', selectRange);
    $('download-selected').addEventListener('click', downloadSelected);
    $('mobile-download-selected').addEventListener('click', downloadSelected);
    $('quality').addEventListener('change', updatePrefFromDownload);
    $('audio').addEventListener('change', updatePrefFromDownload);
    $('parallel').addEventListener('change', updatePrefFromDownload);
    $('settings-save').addEventListener('click', savePrefs);
    $('network-check').addEventListener('click', async () => {
      const button = $('network-check');
      button.disabled = true;
      $('network-status').textContent = 'Checking local configuration…';
      try {
        const info = await call('network_status');
        $('network-warp').textContent = info.warp_detected ? 'Client detected' : 'Client not detected';
        $('network-proxy').textContent = info.system_proxy_configured ? 'Configured' : 'Not detected';
        $('network-status').textContent = 'Local check complete. Active routing has not been verified.';
      } catch (e) {
        $('network-status').textContent = 'Local network check failed.';
        showError(e);
      } finally { button.disabled = false; }
    });
    $('cancel').addEventListener('click', async () => { try{await call('cancel');await refreshStatus();}catch(e){showError(e);} });
    $('change-folder').addEventListener('click', async () => {try{ const folder=await call('choose_folder');if(folder){$('save-path').value=folder;notice('Download folder updated.');}}catch(e){showError(e);} });
    $('refresh-library').addEventListener('click', () => refreshLibrary().catch(showError));
    $('go-library').addEventListener('click', () => setPage('library'));
    $('home-view-downloads').addEventListener('click', () => setPage('downloads'));
    $('player-open').addEventListener('click', () => setPage('library'));
    $('release-update-open').addEventListener('click', () =>
      call('open_external', 'https://github.com/GitRatio/pahebatcher/releases/tag/preview').catch(showError));
    $('release-update-dismiss').addEventListener('click', () => { $('release-update').hidden = true; });
    $('about-check-updates').addEventListener('click', () => renderAboutUpdateStatus().catch(showError));
    document.querySelectorAll('a[href^="https://"]').forEach((a) => a.addEventListener('click', (e) => {
      e.preventDefault();call('open_external',a.href).catch(showError);
    }));
  }
  hooks();
  if(window.pywebview && window.pywebview.api) startup().catch(showError);
  else window.addEventListener('pywebviewready', () => startup().catch(showError), {once:true});
})();