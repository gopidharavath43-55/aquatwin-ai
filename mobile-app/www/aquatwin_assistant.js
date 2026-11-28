/* ==========================================================================
   AquaTwin AI — Unified AI Recommendation Assistant, Quick Search & History
   Zero Google links • Native Apple Maps Integration • 33-District AI Advisor
   ========================================================================== */
(function () {
  if (window.__AQUATWIN_ASSISTANT_LOADED__) return;
  window.__AQUATWIN_ASSISTANT_LOADED__ = true;

  var QA_HIST_KEY = 'aquatwin_qa_history_v3';
  var histOpenedAt = 0;
  var askOpenedAt = 0;
  var histSearch = '';

  var CSS = [
    '.at-ai-chip{padding:8px 13px;border-radius:9999px;font-size:12px;font-weight:600;border:1px solid rgba(255,255,255,0.20);background:rgba(255,255,255,0.10);color:#fff;white-space:nowrap;flex-shrink:0;box-shadow:inset 0 1px 0 rgba(255,255,255,0.28)}',
    '.at-ai-chip:active{transform:scale(0.95);background:rgba(255,255,255,0.22)}',
    '.at-ai-chips-row{display:flex;gap:8px;padding:8px 16px;overflow-x:auto;-webkit-overflow-scrolling:touch;flex-shrink:0;border-bottom:1px solid rgba(255,255,255,0.10)}',
    '.at-ai-live{margin:10px 16px 2px;padding:7px 12px;border-radius:14px;background:rgba(48,209,88,0.14);border:1px solid rgba(48,209,88,0.30);font-size:11px;color:#86efac;display:flex;align-items:center;gap:7px;flex-shrink:0}',
    '.at-ai-dot{width:7px;height:7px;border-radius:50%;background:#30D158;flex-shrink:0}',
    '.at-ai-msg{flex-shrink:0;max-width:92%;padding:12px 14px;border-radius:18px;font-size:13px;line-height:1.48;white-space:pre-line;word-break:break-word}',
    '.at-ai-msg.ai{align-self:flex-start;background:rgba(255,255,255,0.10);border:1px solid rgba(255,255,255,0.16);box-shadow:inset 0 1px 0 rgba(255,255,255,0.26);color:#f4f6f9}',
    '.at-ai-msg.user{align-self:flex-end;background:linear-gradient(180deg,rgba(255,255,255,0.30),rgba(255,255,255,0.16));border:1px solid rgba(255,255,255,0.40);color:#fff;font-weight:500}',
    '.at-saved-tag{display:block;margin-top:6px;font-size:10px;color:#30D158;font-weight:700}',
    '.at-map-action-link{display:inline-flex;align-items:center;gap:6px;margin-top:8px;padding:6px 12px;border-radius:9999px;background:rgba(255,255,255,0.16);border:1px solid rgba(255,255,255,0.30);color:#fff;font-size:11px;font-weight:700;cursor:pointer}',
    '.at-ai-bar{padding:10px 14px calc(12px + env(safe-area-inset-bottom,0px));border-top:1px solid rgba(255,255,255,0.12);display:flex;gap:8px;align-items:center;flex-shrink:0;background:rgba(20,20,22,0.48)}',
    '.at-ai-input{flex:1;min-height:44px;border-radius:9999px;border:1px solid rgba(255,255,255,0.22);background:rgba(255,255,255,0.10);color:#fff;padding:0 16px;font-size:13.5px;outline:none;box-shadow:inset 0 1px 0 rgba(255,255,255,0.25)}',
    '.at-ai-send{min-width:68px;height:44px;border:1px solid rgba(255,255,255,0.40);border-radius:9999px;padding:0 16px;background:linear-gradient(180deg,rgba(255,255,255,0.28),rgba(255,255,255,0.14));color:#fff;font-size:13px;font-weight:700}',
    '.at-quick-jump{margin:6px 16px 0;padding:8px 12px;border-radius:14px;background:rgba(255,255,255,0.14);border:1px solid rgba(255,255,255,0.28);color:#fff;font-size:12.5px;font-weight:600;display:none;align-items:center;justify-content:space-between;gap:8px}',
    '.at-quick-jump.show{display:flex}',
    '.at-qa-card{flex-shrink:0;padding:13px 14px;border-radius:18px;background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);box-shadow:inset 0 1px 0 rgba(255,255,255,0.22)}',
    '.at-qa-head{display:flex;justify-content:space-between;align-items:center;gap:8px;font-size:11px;color:rgba(242,244,248,0.74);margin-bottom:6px}',
    '.at-qa-del{background:rgba(255,69,58,0.20);color:#ff6961;border:1px solid rgba(255,69,58,0.35);border-radius:9999px;padding:3px 9px;font-size:10.5px;font-weight:700}',
    '.at-qa-q{font-size:13.5px;font-weight:700;color:#fff;margin-bottom:6px;line-height:1.35}',
    '.at-qa-a{font-size:12px;color:rgba(242,244,248,0.82);white-space:pre-line;line-height:1.48;padding-top:6px;border-top:1px solid rgba(255,255,255,0.10)}'
  ].join('');

  function injectCss() {
    if (document.getElementById('at-ha-css')) return;
    var st = document.createElement('style');
    st.id = 'at-ha-css';
    st.textContent = CSS;
    document.head.appendChild(st);
  }

  function esc(s) {
    return window.atEscapeHtml ? window.atEscapeHtml(s) : String(s || '')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function norm(s) {
    return String(s || '')
      .replace(/\s*(digital\s*twin|twin|district)\s*$/i, '')
      .replace(/[^a-z0-9]+/gi, ' ')
      .trim()
      .toLowerCase();
  }

  function num(v, fb) {
    var n = Number(v);
    return isFinite(n) ? n : fb;
  }

  function getDistricts() {
    if (window.atGetLiveDistricts) {
      var live = window.atGetLiveDistricts();
      if (Array.isArray(live) && live.length) return live;
    }
    var d = window.AQUATWIN_ML_DATA;
    return (d && Array.isArray(d.districts)) ? d.districts : [];
  }

  function getRawMlRecord(distName) {
    var d = window.AQUATWIN_ML_DATA;
    if (!d || !Array.isArray(d.districts)) return null;
    var key = norm(distName);
    return d.districts.find(function (x) { return norm(x.district) === key; }) || null;
  }

  function getSyncStamp() {
    var d = window.AQUATWIN_ML_DATA;
    return (d && d.last_satellite_sync) ? d.last_satellite_sync : 'Sentinel-2 Live';
  }

  function getActiveDistrictName() {
    var sel = document.getElementById('simSelect') || document.querySelector('select');
    if (sel && sel.options && sel.selectedIndex >= 0) {
      return (sel.options[sel.selectedIndex].text || sel.value || 'Hyderabad').trim();
    }
    return 'Hyderabad';
  }

  function nowStamp() {
    var d = new Date();
    return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) + ', ' +
      d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: true });
  }

  function loadHistory() {
    try {
      var a = JSON.parse(localStorage.getItem(QA_HIST_KEY) || '[]');
      if (Array.isArray(a)) return a;
    } catch (e) {}
    return [];
  }

  function saveHistory(arr) {
    try { localStorage.setItem(QA_HIST_KEY, JSON.stringify(arr.slice(0, 80))); } catch (e) {}
  }

  function recordQa(q, a) {
    var cleanA = String(a || '').trim();
    if (!cleanA || /fetching live/i.test(cleanA)) return;
    var arr = loadHistory();
    arr.unshift({
      id: Date.now() + '_' + Math.floor(Math.random() * 9999),
      q: String(q).trim(),
      a: cleanA,
      t: nowStamp()
    });
    saveHistory(arr);
  }

  function findDistrict(text, list) {
    var q = norm(text);
    if (!q || !list.length) return null;
    var shortMap = {
      hyd: 'hyderabad', hyderbad: 'hyderabad', wgl: 'warangal', kmm: 'khammam',
      nzb: 'nizamabad', krm: 'karimnagar', mbnr: 'mahabubnagar', nlg: 'nalgonda',
      rr: 'ranga reddy', ranga: 'ranga reddy', hanamkonda: 'hanumakonda',
      komaram: 'kumuram bheem asifabad', asifabad: 'kumuram bheem asifabad',
      kothagudem: 'bhadradri kothagudem', bhadradri: 'bhadradri kothagudem',
      sircilla: 'rajanna sircilla', bhuvanagiri: 'yadadri bhuvanagiri',
      yadadri: 'yadadri bhuvanagiri', gadwal: 'jogulamba gadwal',
      bhupalpally: 'jayashankar bhupalpally', malkajgiri: 'medchal malkajgiri',
      medchal: 'medchal malkajgiri', peddapalle: 'peddapalli', jangoan: 'jangaon'
    };
    var expanded = q;
    var toks = q.split(' ');
    for (var t = 0; t < toks.length; t++) {
      if (shortMap[toks[t]]) expanded += ' ' + shortMap[toks[t]];
    }

    for (var i = 0; i < list.length; i++) {
      var dn = norm(list[i].district);
      if (dn && (expanded === dn || expanded.indexOf(dn) !== -1 || (q.length >= 4 && dn.indexOf(q) !== -1))) {
        return list[i];
      }
    }
    for (var j = 0; j < list.length; j++) {
      var parts = norm(list[j].district).split(' ');
      for (var p = 0; p < parts.length; p++) {
        if (parts[p].length >= 4 && expanded.indexOf(parts[p]) !== -1) return list[j];
      }
    }
    return null;
  }

  function fetchMobileLiveWeather(lat, lon) {
    if (!isFinite(lat) || !isFinite(lon) || typeof fetch !== 'function') return Promise.resolve(null);
    var url = 'https://api.open-meteo.com/v1/forecast?latitude=' + lat.toFixed(4) +
      '&longitude=' + lon.toFixed(4) +
      '&current=temperature_2m,relative_humidity_2m,precipitation,cloud_cover' +
      '&forecast_days=1&timezone=Asia%2FKolkata';
    var ctrl = typeof AbortController !== 'undefined' ? new AbortController() : null;
    var timer = ctrl ? setTimeout(function () { ctrl.abort(); }, 2500) : null;
    return fetch(url, ctrl ? { signal: ctrl.signal } : {})
      .then(function (r) { if (timer) clearTimeout(timer); return r.ok ? r.json() : null; })
      .then(function (j) {
        if (!j || !j.current) return null;
        return {
          temp: num(j.current.temperature_2m, null),
          hum: num(j.current.relative_humidity_2m, null),
          rain: num(j.current.precipitation, 0)
        };
      })
      .catch(function () { if (timer) clearTimeout(timer); return null; });
  }

  function formatFullDistrictReport(distItem, liveW) {
    var raw = getRawMlRecord(distItem.district) || distItem;
    var wqi = num(distItem.xgb_wqi != null ? distItem.xgb_wqi : raw.xgb_wqi, 72);
    var p1 = num(raw.lstm_1m_wqi, wqi);
    var p2 = num(raw.lstm_2m_wqi, wqi);
    var p6 = num(raw.lstm_6m_wqi, p1);
    var p1y = num(raw.lstm_1y_wqi, p6);
    var ndwi = num(distItem.ndwi != null ? distItem.ndwi : raw.ndwi_mean, -0.45);
    var turb = num(distItem.turb != null ? distItem.turb : raw.turbidity_index, 1.05);
    var wc = num(distItem.water != null ? distItem.water : raw.water_coverage_pct, 1.2);
    var rain = num(distItem.rain != null ? distItem.rain : raw.rainfall_mm, 20);
    var gwd = num(distItem.gw_depth != null ? distItem.gw_depth : raw.gw_depth_mbgl, 8.24);
    var gwe = num(distItem.gw_ext != null ? distItem.gw_ext : raw.gw_extraction_pct, 48);
    var gwr = num(distItem.gw_rech != null ? distItem.gw_rech : raw.gw_recharge_mm, 8.5);
    var st = distItem.gw_status || raw.gw_status || 'Safe';
    var risk = wqi >= 70 ? 'Safe' : (wqi >= 55 ? 'Moderate Risk' : 'High Risk');
    var sync = distItem.sync || raw.last_satellite_sync || getSyncStamp();

    var liveBlock = liveW && liveW.temp != null
      ? '[1] LIVE WEATHER (Now)\n• Temp: ' + liveW.temp.toFixed(1) + '°C | Humidity: ' + liveW.hum.toFixed(0) + '% | Rain: ' + liveW.rain.toFixed(1) + ' mm\n\n'
      : '';

    var recText = '';
    if (window.atBuildRecommendations) {
      var recObj = window.atBuildRecommendations(distItem, null);
      recText = '\n\n[AI RECOMMENDATIONS — 33-DISTRICT ENGINE]\n' +
        recObj.items.map(function (it) { return '• [' + it.priority + ' | ' + it.gain + '] ' + it.text; }).join('\n') +
        (recObj.benchmark ? '\n• ' + recObj.benchmark : '');
    }

    return (
      distItem.district + ' — Digital Twin (' + sync + ')\n\n' +
      liveBlock +
      '[SATELLITE & WATER QUALITY]\n' +
      '• Live WQI: ' + wqi.toFixed(1) + '/100 (' + risk + ')\n' +
      '• Forecast: +1M ' + p1.toFixed(1) + ' | +2M ' + p2.toFixed(1) + ' | +6M ' + p6.toFixed(1) + ' | +1Y ' + p1y.toFixed(1) + '\n' +
      '• NDWI: ' + ndwi.toFixed(4) + ' | Turbidity: ' + turb.toFixed(3) + ' | Water Cover: ' + wc.toFixed(2) + '%\n\n' +
      '[GROUNDWATER & RESERVOIR]\n' +
      '• Aquifer: ' + gwd.toFixed(2) + ' mbgl (' + st + ', ' + gwe.toFixed(1) + '% ext) | Recharge: ' + gwr.toFixed(1) + ' mm\n' +
      '• Reservoir: ' + (distItem.res_name || raw.reservoir_name || 'Basin Dam') + ' — ' + num(distItem.res_pct != null ? distItem.res_pct : raw.res_storage_pct, 45).toFixed(1) + '%\n' +
      '• Rainfall: ' + rain.toFixed(1) + ' mm' + recText
    );
  }

  function buildStateRecommendationsReport(list) {
    var opt = window.atGetStateOptimizationSummary ? window.atGetStateOptimizationSummary() : null;
    if (!opt) return 'Dataset loading...';

    var urgentLines = opt.topUrgent.map(function (d, idx) {
      var rec = window.atBuildRecommendations ? window.atBuildRecommendations(d, null) : null;
      var firstAction = rec && rec.items[0] ? rec.items[0].text : 'Prioritize turbidity & aquifer recharge.';
      return (idx + 1) + '. ' + d.district + ' (WQI ' + num(d.xgb_wqi, 60).toFixed(1) + ', GW ' + num(d.gw_ext, 50).toFixed(0) + '% ext)\n   → ' + firstAction;
    }).join('\n');

    var bestLines = opt.bestResilient.map(function (d, idx) {
      return (idx + 1) + '. ' + d.district + ' — WQI ' + num(d.xgb_wqi, 80).toFixed(1) + ' | Reservoir ' + num(d.res_pct, 60).toFixed(0) + '%';
    }).join('\n');

    return (
      '33-District AI Optimization & Best Results (' + list.length + ' Districts)\n' +
      '• State Avg WQI: ' + opt.avgWqi.toFixed(1) + ' / 100\n\n' +
      '[TOP PRIORITY INTERVENTIONS]\n' + urgentLines + '\n\n' +
      '[TOP RESILIENT BENCHMARKS]\n' + bestLines + '\n\n' +
      'Tip: Ask about any district (e.g. "Recommend for Hyderabad") or open AI Twin -> "Apply Best Plan".'
    );
  }

  function answerQuery(question) {
    var list = getDistricts();
    if (!list.length) return 'Live dataset is loading. Please try again.';
    var q = norm(question);

    if (q.indexOf('compare') !== -1 || q.indexOf(' vs ') !== -1) {
      var hits = [];
      for (var i = 0; i < list.length; i++) {
        var dn = norm(list[i].district);
        if (dn && q.indexOf(dn) !== -1) hits.push(list[i]);
      }
      if (hits.length >= 2) {
        var a = hits[0], b = hits[1];
        return 'District Comparison:\n' +
          '1) ' + a.district + ': WQI ' + num(a.xgb_wqi, 70).toFixed(1) + ' | Water ' + num(a.water, 1).toFixed(2) + '% | GW ' + num(a.gw_depth, 8).toFixed(2) + 'm (' + (a.gw_status || 'Safe') + ')\n' +
          '2) ' + b.district + ': WQI ' + num(b.xgb_wqi, 70).toFixed(1) + ' | Water ' + num(b.water, 1).toFixed(2) + '% | GW ' + num(b.gw_depth, 8).toFixed(2) + 'm (' + (b.gw_status || 'Safe') + ')';
      }
    }

    var dist = findDistrict(question, list);
    if (dist) return formatFullDistrictReport(dist, null);

    // Handle AI Recommendation / Optimization / Best Results / Action Plan queries
    if (/recommend|advice|action|plan|solution|optimi|best result|intervention|suggest|fix|improve/.test(q)) {
      return buildStateRecommendationsReport(list);
    }

    if (q.indexOf('satellite') !== -1 || q.indexOf('sentinel') !== -1 || q.indexOf('ndwi') !== -1 || q.indexOf('turbid') !== -1) {
      var topWater = list.slice().sort(function (a, b) { return num(b.water, 0) - num(a.water, 0); }).slice(0, 4);
      var highTurb = list.slice().sort(function (a, b) { return num(b.turb, 0) - num(a.turb, 0); }).slice(0, 4);
      return 'Live Sentinel-2 Satellite Telemetry (' + getSyncStamp() + ')\n\n' +
        'Highest Surface Water Coverage:\n' +
        topWater.map(function (d, i) { return (i + 1) + '. ' + d.district + ': ' + num(d.water, 0).toFixed(2) + '% (NDWI ' + num(d.ndwi, 0).toFixed(3) + ')'; }).join('\n') + '\n\n' +
        'Highest Turbidity Alerts:\n' +
        highTurb.map(function (d, i) { return (i + 1) + '. ' + d.district + ': Turb ' + num(d.turb, 1).toFixed(3) + ' (WQI ' + num(d.xgb_wqi, 70).toFixed(1) + ')'; }).join('\n');
    }

    if (q.indexOf('groundwater') !== -1 || q.indexOf('ground water') !== -1 || q.indexOf('gw') !== -1 || q.indexOf('aquifer') !== -1 || q.indexOf('depth') !== -1) {
      var deep = list.slice().sort(function (a, b) { return num(b.gw_depth, 0) - num(a.gw_depth, 0); }).slice(0, 5);
      var avgGw = (list.reduce(function (s, x) { return s + num(x.gw_depth, 8.2); }, 0) / list.length).toFixed(2);
      return 'Telangana Live Groundwater Status (Avg: ' + avgGw + ' mbgl)\n\nMost Stressed Aquifers:\n' +
        deep.map(function (d, i) { return (i + 1) + '. ' + d.district + ' — ' + num(d.gw_depth, 8).toFixed(2) + ' mbgl (' + (d.gw_status || 'Safe') + ', Ext ' + num(d.gw_ext, 45).toFixed(1) + '%)'; }).join('\n');
    }

    if (q.indexOf('risk') !== -1 || q.indexOf('worst') !== -1 || q.indexOf('watchlist') !== -1 || q.indexOf('high') !== -1) {
      var worst = list.slice().sort(function (a, b) { return num(a.xgb_wqi, 99) - num(b.xgb_wqi, 99); }).slice(0, 5);
      return 'Top 5 Priority Watchlist Districts:\n' +
        worst.map(function (d, i) { return (i + 1) + '. ' + d.district + ' — WQI ' + num(d.xgb_wqi, 60).toFixed(1) + ' | Turb ' + num(d.turb, 1).toFixed(2) + ' | GW ' + num(d.gw_depth, 8).toFixed(1) + 'm'; }).join('\n');
    }

    if (q.indexOf('telangana') !== -1 || q.indexOf('state') !== -1 || q.indexOf('summary') !== -1 || q.indexOf('all') !== -1 || q.indexOf('best') !== -1) {
      var avgWqi = (list.reduce(function (s, x) { return s + num(x.xgb_wqi, 70); }, 0) / list.length).toFixed(1);
      var avgWc = (list.reduce(function (s, x) { return s + num(x.water, 1); }, 0) / list.length).toFixed(2);
      var avgGw = (list.reduce(function (s, x) { return s + num(x.gw_depth, 8.2); }, 0) / list.length).toFixed(2);
      var safeCnt = list.filter(function (x) { return num(x.xgb_wqi, 70) >= 70; }).length;
      return 'Telangana Live Summary (' + list.length + ' Districts)\n' +
        '• Satellite Sync: ' + getSyncStamp() + '\n' +
        '• State Avg WQI: ' + avgWqi + '/100 (' + safeCnt + '/' + list.length + ' Safe)\n' +
        '• Avg Surface Water: ' + avgWc + '% | Avg GW Depth: ' + avgGw + ' mbgl\n\n' +
        buildStateRecommendationsReport(list);
    }

    if (q.indexOf('current') !== -1 || q.indexOf('selected') !== -1) {
      var cur = findDistrict(getActiveDistrictName(), list) || list[0];
      return formatFullDistrictReport(cur, null);
    }

    return buildStateRecommendationsReport(list);
  }

  function answerQueryAsync(question) {
    var list = getDistricts();
    var dist = findDistrict(question, list);
    if (!dist && (/current|selected/i.test(question))) {
      dist = findDistrict(getActiveDistrictName(), list);
    }
    if (dist) {
      return fetchMobileLiveWeather(num(dist.lat, 17.385), num(dist.lng, 78.4867)).then(function (liveW) {
        return {
          text: formatFullDistrictReport(dist, liveW),
          districtName: dist.district
        };
      });
    }
    return Promise.resolve({
      text: answerQuery(question),
      districtName: null
    });
  }

  function ensureHistoryModal() {
    if (document.getElementById('at-hist-bg')) return;
    var bg = document.createElement('div');
    bg.id = 'at-hist-bg';
    bg.className = 'at-modal-backdrop';
    bg.innerHTML =
      '<div class="at-modal-sheet lg-regular" style="height:82dvh;">' +
        '<div class="at-modal-head">' +
          '<div class="at-grabber" aria-hidden="true"></div>' +
          '<div class="at-modal-head-row">' +
            '<div><div class="at-modal-title">Saved Ask AI History</div><div class="at-modal-sub">Search saved Q&amp;As or ask &amp; save new</div></div>' +
            '<div style="display:flex;gap:6px"><button type="button" class="at-modal-close lg-press" id="at-hist-clear">Clear</button><button type="button" class="at-modal-close lg-press" id="at-hist-close">Done</button></div>' +
          '</div>' +
        '</div>' +
        '<div class="at-ai-bar" style="border-top:none;border-bottom:1px solid rgba(255,255,255,0.10);padding:10px 16px;">' +
          '<input type="text" class="at-ai-input" id="at-hist-search" placeholder="Search history or ask a question..." />' +
          '<button type="button" class="at-ai-send lg-press" id="at-hist-ask" style="min-width:92px;">Ask &amp; Save</button>' +
        '</div>' +
        '<div class="at-modal-body" id="at-hist-body"></div>' +
      '</div>';
    document.body.appendChild(bg);

    bg.addEventListener('click', function (e) {
      if (e.target === bg && Date.now() - histOpenedAt > 350) bg.classList.remove('open');
    });
    document.getElementById('at-hist-close').addEventListener('click', function () { bg.classList.remove('open'); });
    document.getElementById('at-hist-clear').addEventListener('click', function () { saveHistory([]); renderHistory(); });

    var inp = document.getElementById('at-hist-search');
    inp.addEventListener('input', function () { histSearch = this.value || ''; renderHistory(); });
    function askNow() {
      var q = (inp.value || '').trim();
      if (!q) return;
      var a = answerQuery(q);
      recordQa(q, a);
      inp.value = '';
      histSearch = '';
      renderHistory();
    }
    document.getElementById('at-hist-ask').addEventListener('click', askNow);
    inp.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); askNow(); } });
  }

  function renderHistory() {
    var body = document.getElementById('at-hist-body');
    if (!body) return;
    var all = loadHistory();
    var needle = histSearch.trim().toLowerCase();
    var items = needle ? all.filter(function (x) { return (x.q + ' ' + x.a).toLowerCase().indexOf(needle) !== -1; }) : all;

    if (!items.length) {
      body.innerHTML = '<div class="at-qa-card"><div class="at-qa-q">' +
        (needle ? 'No saved match for "' + esc(needle) + '"' : 'No Ask AI questions saved yet') +
        '</div><div class="at-qa-a">' +
        (needle ? 'Tap "Ask & Save" above to compute and save an answer.' : 'Ask any question in Ask AI — every question and answer auto-saves here.') +
        '</div></div>';
      return;
    }

    body.innerHTML = items.map(function (it) {
      return '<div class="at-qa-card">' +
        '<div class="at-qa-head"><span>Ask AI • ' + esc(it.t) + '</span><button type="button" class="at-qa-del" data-id="' + esc(it.id) + '">Delete</button></div>' +
        '<div class="at-qa-q">Q: ' + esc(it.q) + '</div>' +
        '<div class="at-qa-a">A: ' + esc(it.a) + '</div>' +
      '</div>';
    }).join('');

    body.querySelectorAll('.at-qa-del').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var id = btn.getAttribute('data-id');
        saveHistory(loadHistory().filter(function (x) { return x.id !== id; }));
        renderHistory();
      });
    });
  }

  function openHistory() {
    ensureHistoryModal();
    histOpenedAt = Date.now();
    renderHistory();
    document.getElementById('at-hist-bg').classList.add('open');
  }

  function ensureAskAiModal() {
    if (document.getElementById('at-askai-bg')) return;
    var bg = document.createElement('div');
    bg.id = 'at-askai-bg';
    bg.className = 'at-modal-backdrop';
    bg.innerHTML =
      '<div class="at-modal-sheet lg-regular" style="height:84dvh;">' +
        '<div class="at-modal-head">' +
          '<div class="at-grabber" aria-hidden="true"></div>' +
          '<div class="at-modal-head-row">' +
            '<div><div class="at-modal-title">AquaTwin Ask AI</div><div class="at-modal-sub">33-District Recommendations &bull; Quick Search &bull; 1M–1Y ML</div></div>' +
            '<div style="display:flex;gap:6px"><button type="button" class="at-modal-close lg-press" id="at-askai-hist">History</button><button type="button" class="at-modal-close lg-press" id="at-askai-close">Done</button></div>' +
          '</div>' +
        '</div>' +
        '<div class="at-ai-live"><span class="at-ai-dot"></span><span id="at-live-strip-txt">Loading 33-district dataset...</span></div>' +
        '<div class="at-quick-jump" id="at-quick-jump"><span id="at-quick-jump-lbl">Jump to district</span><button type="button" class="at-modal-close lg-press" id="at-quick-jump-btn">Open on Apple Maps</button></div>' +
        '<div class="at-ai-chips-row" id="at-askai-chips">' +
          '<button type="button" class="at-ai-chip" data-q="Best AI recommendations">AI Recommendations</button>' +
          '<button type="button" class="at-ai-chip" data-q="Current district report">Current District</button>' +
          '<button type="button" class="at-ai-chip" data-q="Hyderabad">Hyderabad</button>' +
          '<button type="button" class="at-ai-chip" data-q="Real time satellite data">Satellite</button>' +
          '<button type="button" class="at-ai-chip" data-q="Groundwater status">Groundwater</button>' +
          '<button type="button" class="at-ai-chip" data-q="Telangana state summary">State Summary</button>' +
        '</div>' +
        '<div class="at-modal-body" id="at-askai-msgs">' +
          '<div class="at-ai-msg ai">Ready! Ask for AI Recommendations across all 33 districts, tap a quick chip, or enter any district name for satellite, groundwater, reservoir, and 1M–1Y forecast insights.</div>' +
        '</div>' +
        '<div class="at-ai-bar">' +
          '<input type="text" class="at-ai-input" id="at-askai-input" placeholder="Ask AI recommendations, Hyderabad, groundwater..." />' +
          '<button type="button" class="at-ai-send lg-press" id="at-askai-send">Send</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(bg);

    var jumpDist = null;
    var jumpRow = document.getElementById('at-quick-jump');
    var jumpLbl = document.getElementById('at-quick-jump-lbl');
    var jumpBtn = document.getElementById('at-quick-jump-btn');

    function updateQuickJump(text) {
      var list = getDistricts();
      var hit = findDistrict(text, list);
      if (hit && String(text || '').trim().length >= 3) {
        jumpDist = hit.district;
        jumpLbl.textContent = hit.district + ' — WQI ' + num(hit.xgb_wqi, 70).toFixed(1);
        jumpRow.classList.add('show');
      } else {
        jumpDist = null;
        jumpRow.classList.remove('show');
      }
    }

    jumpBtn.addEventListener('click', function () {
      if (!jumpDist) return;
      bg.classList.remove('open');
      if (window.atSelectDistrict) window.atSelectDistrict(jumpDist, { fly: true, expandSheet: true });
      if (window.switchTab) window.switchTab('map');
    });

    function sendMsg(text) {
      var msg = String(text || '').trim();
      if (!msg) return;
      if (window.atTriggerHaptic) window.atTriggerHaptic('LIGHT');
      var box = document.getElementById('at-askai-msgs');
      var u = document.createElement('div');
      u.className = 'at-ai-msg user';
      u.textContent = msg;
      box.appendChild(u);

      var a = document.createElement('div');
      a.className = 'at-ai-msg ai';
      a.textContent = 'Analyzing 33-district telemetry...';
      box.appendChild(a);
      box.scrollTop = box.scrollHeight;

      answerQueryAsync(msg).then(function (res) {
        recordQa(msg, res.text);
        var mapBtnHtml = res.districtName
          ? '<br><button type="button" class="at-map-action-link lg-press" data-focus-dist="' + esc(res.districtName) + '">Open ' + esc(res.districtName) + ' in Apple Maps ↗</button>'
          : '';
        a.innerHTML = esc(res.text) + '<span class="at-saved-tag">Saved to History</span>' + mapBtnHtml;
        var mapJump = a.querySelector('[data-focus-dist]');
        if (mapJump) {
          mapJump.addEventListener('click', function () {
            var dn = mapJump.getAttribute('data-focus-dist');
            bg.classList.remove('open');
            if (window.atSelectDistrict) window.atSelectDistrict(dn, { fly: true, expandSheet: true });
            if (window.switchTab) window.switchTab('map');
          });
        }
        box.scrollTop = box.scrollHeight;
      });
    }

    bg.addEventListener('click', function (e) {
      if (e.target === bg && Date.now() - askOpenedAt > 350) bg.classList.remove('open');
    });
    document.getElementById('at-askai-close').addEventListener('click', function () { bg.classList.remove('open'); });
    document.getElementById('at-askai-hist').addEventListener('click', function () { bg.classList.remove('open'); openHistory(); });

    var inp = document.getElementById('at-askai-input');
    inp.addEventListener('input', function () { updateQuickJump(this.value); });
    document.getElementById('at-askai-send').addEventListener('click', function () {
      sendMsg(inp.value);
      inp.value = '';
      updateQuickJump('');
    });
    inp.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        sendMsg(this.value);
        this.value = '';
        updateQuickJump('');
      }
    });
    document.getElementById('at-askai-chips').addEventListener('click', function (e) {
      var c = e.target.closest ? e.target.closest('.at-ai-chip') : null;
      if (c) sendMsg(c.getAttribute('data-q'));
    });

    window.__atSendAiMsg = sendMsg;
  }

  function openAskAi(prefillQuery) {
    ensureAskAiModal();
    askOpenedAt = Date.now();
    var list = getDistricts();
    var stxt = document.getElementById('at-live-strip-txt');
    if (stxt) {
      stxt.textContent = list.length + ' Districts Live • AI Recommendations + 3Y ML';
    }
    document.getElementById('at-askai-bg').classList.add('open');
    if (prefillQuery && typeof window.__atSendAiMsg === 'function') {
      window.__atSendAiMsg(prefillQuery);
    }
  }

  window.atOpenAssistantForDistrict = function (name) {
    openAskAi(name);
  };

  function boot() {
    injectCss();
    var fab = document.getElementById('at-askai-fab');
    if (fab && !fab.dataset.atBound) {
      fab.dataset.atBound = '1';
      fab.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        if (window.atTriggerHaptic) window.atTriggerHaptic('MEDIUM');
        openAskAi();
      });
    }
    document.addEventListener('click', function (e) {
      var hBtn = e.target.closest ? e.target.closest('[data-open-history="1"]') : null;
      if (hBtn) {
        var pop = document.getElementById('at-glass-popover');
        if (pop) pop.classList.remove('open');
        openHistory();
      }
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
