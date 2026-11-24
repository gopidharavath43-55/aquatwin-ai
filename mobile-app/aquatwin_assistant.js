(function(){
  if (window.__AQUATWIN_ASSISTANT_LOADED__) return;
  window.__AQUATWIN_ASSISTANT_LOADED__ = true;

  var QA_HIST_KEY = 'aquatwin_qa_history_v3';
  var histOpenedAt = 0;
  var askOpenedAt = 0;
  var histSearch = '';
  var lastFabTap = 0;

  var CSS = [
    '.at-hist-btn{display:inline-flex!important;align-items:center;gap:6px;height:36px;padding:0 12px;border-radius:999px;border:1px solid rgba(56,189,248,.45);background:rgba(14,34,61,.95);color:#e0f2fe;font-size:12px;font-weight:700;cursor:pointer;touch-action:manipulation;-webkit-tap-highlight-color:transparent;flex-shrink:0;z-index:2147482000}',
    '.at-hist-btn:active{transform:scale(.95);background:rgba(14,116,144,.55)}',
    '.at-hist-btn svg{width:15px;height:15px;stroke:#38bdf8;fill:none;stroke-width:2.1;pointer-events:none}',
    '.at-hist-count{background:rgba(14,165,233,.32);color:#7dd3fc;border-radius:999px;padding:1px 6px;font-size:10px;font-weight:800;pointer-events:none}',
    '#at-askai-fab{position:fixed!important;right:16px!important;bottom:82px!important;z-index:2147483000!important;display:inline-flex!important;align-items:center;gap:7px;padding:12px 18px;border-radius:999px;border:1px solid rgba(125,211,252,.70);background:linear-gradient(135deg,#0284c7,#0ea5e9,#2563eb);color:#fff;font-size:14px;font-weight:800;box-shadow:0 10px 26px rgba(14,165,233,.52);cursor:pointer;pointer-events:auto!important;touch-action:manipulation;-webkit-tap-highlight-color:transparent;user-select:none}',
    '#at-askai-fab:active{transform:scale(.94)}',
    '#at-askai-fab *{pointer-events:none}',
    '#at-askai-fab svg{width:18px;height:18px;stroke:#fff;fill:none;stroke-width:2.2}',
    '.at-sheet-bg{position:fixed!important;left:0!important;top:0!important;right:0!important;bottom:0!important;z-index:2147483600!important;background:rgba(2,8,20,.82);display:none;align-items:flex-end;justify-content:center}',
    '.at-sheet-bg.open{display:flex!important}',
    '.at-sheet{width:100%;max-width:540px;height:82vh;max-height:86vh;background:linear-gradient(180deg,#0b1c36,#061124);border-top-left-radius:22px;border-top-right-radius:22px;border-top:1px solid rgba(56,189,248,.42);display:flex;flex-direction:column;overflow:hidden;box-shadow:0 -12px 34px rgba(0,0,0,.65)}',
    '.at-sheet-head{padding:13px 15px;border-bottom:1px solid rgba(255,255,255,.09);display:flex;align-items:center;justify-content:space-between;gap:8px;flex-shrink:0}',
    '.at-sheet-title{font-size:15px;font-weight:800;color:#f8fafc}',
    '.at-sheet-sub{font-size:10.5px;color:#7dd3fc;margin-top:2px}',
    '.at-sheet-btn{border:1px solid rgba(148,163,184,.34);background:rgba(30,41,59,.88);color:#e2e8f0;border-radius:10px;padding:6px 11px;font-size:11.5px;font-weight:700;cursor:pointer;touch-action:manipulation}',
    '.at-live-strip{margin:8px 14px 2px;padding:6px 10px;border-radius:10px;background:rgba(16,185,129,.14);border:1px solid rgba(52,211,153,.32);font-size:10.5px;color:#a7f3d0;display:flex;align-items:center;gap:6px;flex-shrink:0}',
    '.at-live-dot{width:7px;height:7px;border-radius:50%;background:#34d399;flex-shrink:0}',
    '.at-tabs-row{display:flex;gap:6px;padding:8px 14px 6px;overflow-x:auto;flex-shrink:0}',
    '.at-tab-chip{padding:6px 11px;border-radius:999px;font-size:11px;font-weight:700;border:1px solid rgba(56,189,248,.32);background:rgba(15,31,56,.88);color:#bae6fd;white-space:nowrap;cursor:pointer;touch-action:manipulation}',
    '.at-tab-chip:active{background:rgba(14,165,233,.35);color:#fff}',
    '.at-sheet-body{padding:10px 14px 14px;overflow-y:auto;-webkit-overflow-scrolling:touch;flex:1;display:flex;flex-direction:column;gap:10px}',
    '.at-msg{max-width:94%;padding:10px 12px;border-radius:14px;font-size:12.5px;line-height:1.48;white-space:pre-line;word-break:break-word}',
    '.at-msg.ai{align-self:flex-start;background:rgba(14,42,74,.95);border:1px solid rgba(56,189,248,.30);color:#e2e8f0}',
    '.at-msg.user{align-self:flex-end;background:linear-gradient(135deg,#0284c7,#2563eb);color:#fff}',
    '.at-saved-tag{display:block;margin-top:6px;font-size:10px;color:#6ee7b7;font-weight:700}',
    '.at-input-bar{padding:10px 12px 14px;border-top:1px solid rgba(255,255,255,.09);display:flex;gap:8px;background:#061124;flex-shrink:0}',
    '.at-input{flex:1;border-radius:12px;border:1px solid rgba(56,189,248,.40);background:#0f1f38;color:#f8fafc;padding:10px 12px;font-size:13px;outline:none}',
    '.at-send{border:none;border-radius:12px;padding:0 16px;background:linear-gradient(135deg,#0ea5e9,#2563eb);color:#fff;font-size:13px;font-weight:800;cursor:pointer;touch-action:manipulation}',
    '.at-hist-search-bar{padding:10px 14px 6px;display:flex;gap:7px;flex-shrink:0}',
    '.at-qa-card{padding:11px 12px;border-radius:14px;background:rgba(15,31,56,.90);border:1px solid rgba(56,189,248,.24)}',
    '.at-qa-head{display:flex;justify-content:space-between;align-items:center;gap:8px;font-size:10.5px;color:#7dd3fc;margin-bottom:6px}',
    '.at-qa-del{background:rgba(239,68,68,.18);color:#fca5a5;border:1px solid rgba(248,113,113,.38);border-radius:7px;padding:2px 7px;font-size:10.5px;font-weight:700;cursor:pointer}',
    '.at-qa-q{font-size:13px;font-weight:800;color:#fff;margin-bottom:6px;line-height:1.35}',
    '.at-qa-a{font-size:12px;color:#cbd5e1;white-space:pre-line;line-height:1.48;padding-top:6px;border-top:1px solid rgba(255,255,255,.08)}'
  ].join('');

  function injectCss(){
    if (document.getElementById('at-ha-css')) return;
    var st = document.createElement('style');
    st.id = 'at-ha-css';
    st.textContent = CSS;
    document.head.appendChild(st);
  }

  function esc(s){
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function norm(s){
    return String(s || '').replace(/\s*(digital\s*twin|twin|district)\s*$/i,'').replace(/[^a-z0-9]+/gi,' ').trim().toLowerCase();
  }

  function nowStamp(){
    var d = new Date();
    return d.toLocaleDateString('en-IN',{day:'2-digit',month:'short'}) + ', ' +
           d.toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',hour12:true});
  }

  function getDistricts(){
    var d = window.AQUATWIN_ML_DATA;
    return (d && Array.isArray(d.districts)) ? d.districts : [];
  }

  function getSyncStamp(){
    var d = window.AQUATWIN_ML_DATA;
    return (d && d.last_satellite_sync) ? d.last_satellite_sync : 'Sentinel-2 Live';
  }

  function getActiveDistrictName(){
    var sels = Array.prototype.slice.call(document.querySelectorAll('select'));
    var vis = sels.filter(function(s){ return s.offsetParent !== null && s.options && s.options.length >= 10; });
    var sel = vis.length ? vis[vis.length - 1] : sels.find(function(s){ return s.options && s.options.length >= 10; });
    if (sel && sel.options && sel.selectedIndex >= 0) {
      return (sel.options[sel.selectedIndex].text || sel.value || 'Hyderabad').trim();
    }
    return 'Hyderabad';
  }

  function loadHistory(){
    try {
      var a = JSON.parse(localStorage.getItem(QA_HIST_KEY) || '[]');
      if (Array.isArray(a)) return a;
    } catch(e){}
    return [];
  }

  function saveHistory(arr){
    try { localStorage.setItem(QA_HIST_KEY, JSON.stringify(arr.slice(0, 80))); } catch(e){}
    var b = document.getElementById('at-hist-count');
    if (b) b.textContent = String(arr.length);
  }

  function recordQa(q, a){
    var arr = loadHistory();
    arr.unshift({ id: Date.now() + '_' + Math.floor(Math.random() * 9999), q: String(q).trim(), a: String(a).trim(), t: nowStamp() });
    saveHistory(arr);
    var hm = document.getElementById('at-hist-bg');
    if (hm && hm.classList.contains('open')) renderHistory();
  }

  function findDistrict(text, list){
    var q = norm(text);
    var shortMap = {
      'hyd': 'hyderabad', 'wgl': 'warangal', 'kmm': 'khammam', 'nzb': 'nizamabad',
      'krm': 'karimnagar', 'mbnr': 'mahabubnagar', 'nlg': 'nalgonda', 'rr': 'rangareddy',
      'hanamkonda': 'hanumakonda', 'komaram': 'kumuram bheem asifabad', 'asifabad': 'kumuram bheem asifabad',
      'kothagudem': 'bhadradri kothagudem', 'sircilla': 'rajanna sircilla', 'bhuvanagiri': 'yadadri bhuvanagiri',
      'gadwal': 'jogulamba gadwal', 'bhupalpally': 'jayashankar bhupalpally', 'malkajgiri': 'medchal malkajgiri'
    };
    var tokens = q.split(' ');
    for (var t = 0; t < tokens.length; t++) {
      if (shortMap[tokens[t]]) q += ' ' + shortMap[tokens[t]];
    }
    for (var i = 0; i < list.length; i++) {
      var dn = norm(list[i].district);
      if (dn && q.indexOf(dn) !== -1) return list[i];
    }
    for (var j = 0; j < list.length; j++) {
      var parts = norm(list[j].district).split(' ');
      for (var p = 0; p < parts.length; p++) {
        if (parts[p].length >= 5 && q.indexOf(parts[p]) !== -1) return list[j];
      }
    }
    return null;
  }

  function num(v, fb){ var n = Number(v); return isFinite(n) ? n : fb; }

  function formatFullDistrictReport(d){
    var wqi = num(d.xgb_wqi != null ? d.xgb_wqi : d.wqi_score, 72);
    var p1 = num(d.lstm_1m_wqi, wqi);
    var p3 = num(d.lstm_3m_wqi, (p1 + num(d.lstm_6m_wqi, p1)) / 2);
    var p6 = num(d.lstm_6m_wqi, p1);
    var ndwi = num(d.ndwi_mean, 0.04);
    var ndmi = num(d.ndmi_proxy, 0.08);
    var turb = num(d.turbidity_index, 1.05);
    var wc = num(d.water_coverage_pct, 1.2);
    var rain = num(d.rainfall_mm, 42);
    var resv = num(d.reservoir_idx, 58);
    var gwd = num(d.gw_depth_mbgl, 8.24);
    var gwe = num(d.gw_extraction_pct, 48);
    var gwr = num(d.gw_recharge_mm, 8.5);
    var gw1 = num(d.gw_pred_1m, gwd);
    var gw6 = num(d.gw_pred_6m, gwd);
    var st = d.gw_status || 'Safe';
    var risk = d.risk_level || (wqi >= 70 ? 'Safe' : (wqi >= 55 ? 'Moderate Risk' : 'High Risk'));
    var sync = d.last_satellite_sync || getSyncStamp();

    var advice = (wqi < 60 || st === 'Critical' || st === 'Over-Exploited')
      ? 'Action: Prioritize rainwater recharge pits, limit borewell pumping, and deploy turbidity treatment.'
      : 'Action: Stable conditions; continue Sentinel-2 monitoring and seasonal reservoir balancing.';

    return (
      d.district + ' — Live Digital Twin (' + sync + ')\n\n' +
      '[1] SATELLITE DATA (Sentinel-2 GEE)\n' +
      '• NDWI: ' + ndwi.toFixed(4) + ' | NDMI: ' + ndmi.toFixed(4) + '\n' +
      '• Turbidity Index: ' + turb.toFixed(4) + '\n' +
      '• Surface Water Coverage: ' + wc.toFixed(2) + '%\n\n' +
      '[2] WATER QUALITY & AI FORECAST\n' +
      '• Live WQI: ' + wqi.toFixed(1) + '/100 (' + risk + ')\n' +
      '• Forecast: +1M ' + p1.toFixed(1) + ' | +3M ' + p3.toFixed(1) + ' | +6M ' + p6.toFixed(1) + '\n' +
      '• Rainfall: ' + rain.toFixed(1) + ' mm | Reservoir Index: ' + resv.toFixed(1) + '\n\n' +
      '[3] GROUNDWATER AQUIFER\n' +
      '• Water Table Depth: ' + gwd.toFixed(2) + ' mbgl (' + st + ')\n' +
      '• Extraction: ' + gwe.toFixed(1) + '% | Recharge: ' + gwr.toFixed(1) + ' mm\n' +
      '• GW Forecast: +1M ' + gw1.toFixed(2) + ' m | +6M ' + gw6.toFixed(2) + ' m\n\n' +
      advice
    );
  }

  function answerQuery(question){
    var list = getDistricts();
    if (!list.length) return 'Live dataset is still loading. Please tap Send again in a moment.';
    var q = norm(question);

    // Compare two districts
    if (q.indexOf('compare') !== -1 || q.indexOf(' vs ') !== -1) {
      var hits = [];
      for (var i = 0; i < list.length; i++) {
        var dn = norm(list[i].district);
        if (dn && q.indexOf(dn) !== -1) hits.push(list[i]);
      }
      if (hits.length >= 2) {
        var a = hits[0], b = hits[1];
        return 'Live Satellite + Water + Groundwater Comparison:\n' +
          '1) ' + a.district + ': WQI ' + num(a.xgb_wqi,70).toFixed(1) + ' | Water ' + num(a.water_coverage_pct,1).toFixed(2) + '% | Turb ' + num(a.turbidity_index,1).toFixed(2) + ' | GW ' + num(a.gw_depth_mbgl,8).toFixed(2) + 'm (' + (a.gw_status||'Safe') + ')\n' +
          '2) ' + b.district + ': WQI ' + num(b.xgb_wqi,70).toFixed(1) + ' | Water ' + num(b.water_coverage_pct,1).toFixed(2) + '% | Turb ' + num(b.turbidity_index,1).toFixed(2) + ' | GW ' + num(b.gw_depth_mbgl,8).toFixed(2) + 'm (' + (b.gw_status||'Safe') + ')';
      }
    }

    // Specific district requested
    var dist = findDistrict(question, list);
    if (dist) return formatFullDistrictReport(dist);

    // Real-time Satellite query
    if (q.indexOf('satellite') !== -1 || q.indexOf('sentinel') !== -1 || q.indexOf('ndwi') !== -1 || q.indexOf('ndmi') !== -1 || q.indexOf('gee') !== -1 || q.indexOf('turbid') !== -1) {
      var topWater = list.slice().sort(function(a,b){ return num(b.water_coverage_pct,0) - num(a.water_coverage_pct,0); }).slice(0, 4);
      var highTurb = list.slice().sort(function(a,b){ return num(b.turbidity_index,0) - num(a.turbidity_index,0); }).slice(0, 4);
      return 'Live Sentinel-2 Satellite Telemetry (' + getSyncStamp() + ')\n\n' +
        'Highest Surface Water Coverage:\n' +
        topWater.map(function(d,i){ return (i+1)+'. '+d.district+': '+num(d.water_coverage_pct,0).toFixed(2)+'% (NDWI '+num(d.ndwi_mean,0).toFixed(3)+')'; }).join('\n') + '\n\n' +
        'Highest Turbidity Alerts:\n' +
        highTurb.map(function(d,i){ return (i+1)+'. '+d.district+': Turbidity '+num(d.turbidity_index,1).toFixed(3)+' (WQI '+num(d.xgb_wqi,70).toFixed(1)+')'; }).join('\n');
    }

    // Groundwater query
    if (q.indexOf('groundwater') !== -1 || q.indexOf('ground water') !== -1 || q.indexOf('gw') !== -1 || q.indexOf('aquifer') !== -1 || q.indexOf('borewell') !== -1 || q.indexOf('depth') !== -1 || q.indexOf('critical') !== -1 || q.indexOf('recharge') !== -1 || q.indexOf('extraction') !== -1) {
      var deep = list.slice().sort(function(a,b){ return num(b.gw_depth_mbgl,0) - num(a.gw_depth_mbgl,0); }).slice(0, 5);
      var shallow = list.slice().sort(function(a,b){ return num(a.gw_depth_mbgl,99) - num(b.gw_depth_mbgl,99); }).slice(0, 3);
      var avgGw = (list.reduce(function(s,x){ return s + num(x.gw_depth_mbgl,8.2); }, 0) / list.length).toFixed(2);
      return 'Telangana Live Groundwater Status (Avg: ' + avgGw + ' mbgl)\n\n' +
        'Most Stressed / Deepest Aquifers:\n' +
        deep.map(function(d,i){ return (i+1)+'. '+d.district+' — '+num(d.gw_depth_mbgl,8).toFixed(2)+' mbgl ('+(d.gw_status||'Safe')+', Ext '+num(d.gw_extraction_pct,45).toFixed(1)+'%, +6M '+num(d.gw_pred_6m,8).toFixed(2)+'m)'; }).join('\n') + '\n\n' +
        'Healthiest Shallow Aquifers:\n' +
        shallow.map(function(d,i){ return (i+1)+'. '+d.district+' — '+num(d.gw_depth_mbgl,5).toFixed(2)+' mbgl (Recharge '+num(d.gw_recharge_mm,10).toFixed(1)+' mm)'; }).join('\n');
    }

    // High risk / watchlist
    if (q.indexOf('risk') !== -1 || q.indexOf('worst') !== -1 || q.indexOf('low') !== -1 || q.indexOf('alert') !== -1 || q.indexOf('watchlist') !== -1) {
      var worst = list.slice().sort(function(a,b){ return num(a.xgb_wqi,99) - num(b.xgb_wqi,99); }).slice(0, 5);
      return 'Top 5 Priority Watchlist Districts (Live):\n' +
        worst.map(function(d,i){ return (i+1)+'. '+d.district+' — WQI '+num(d.xgb_wqi,60).toFixed(1)+' | Turb '+num(d.turbidity_index,1).toFixed(2)+' | Water '+num(d.water_coverage_pct,1).toFixed(2)+'% | GW '+num(d.gw_depth_mbgl,8).toFixed(1)+'m'; }).join('\n');
    }

    // Best / safe districts
    if (q.indexOf('best') !== -1 || q.indexOf('safe') !== -1 || q.indexOf('top') !== -1 || q.indexOf('clean') !== -1 || q.indexOf('highest') !== -1) {
      var best = list.slice().sort(function(a,b){ return num(b.xgb_wqi,0) - num(a.xgb_wqi,0); }).slice(0, 5);
      return 'Top 5 Healthiest Water Districts (Live):\n' +
        best.map(function(d,i){ return (i+1)+'. '+d.district+' — WQI '+num(d.xgb_wqi,75).toFixed(1)+'/100 | Water '+num(d.water_coverage_pct,1).toFixed(2)+'% | GW '+num(d.gw_depth_mbgl,7).toFixed(2)+'m'; }).join('\n');
    }

    // State overview
    if (q.indexOf('telangana') !== -1 || q.indexOf('state') !== -1 || q.indexOf('summary') !== -1 || q.indexOf('all') !== -1) {
      var avgWqi = (list.reduce(function(s,x){ return s + num(x.xgb_wqi,70); }, 0) / list.length).toFixed(1);
      var avgWc = (list.reduce(function(s,x){ return s + num(x.water_coverage_pct,1); }, 0) / list.length).toFixed(2);
      var avgGw = (list.reduce(function(s,x){ return s + num(x.gw_depth_mbgl,8.2); }, 0) / list.length).toFixed(2);
      var safeCnt = list.filter(function(x){ return num(x.xgb_wqi,70) >= 70; }).length;
      return 'Telangana Full Live Summary (33 Districts)\n' +
        '• Satellite Sync: ' + getSyncStamp() + '\n' +
        '• State Avg WQI: ' + avgWqi + '/100 (' + safeCnt + '/33 Safe)\n' +
        '• Avg Surface Water Cover: ' + avgWc + '%\n' +
        '• Avg Groundwater Depth: ' + avgGw + ' mbgl\n\n' +
        'Type any district name (e.g., Hyderabad, Jangaon, Khammam) for its complete Satellite + Water + Groundwater report.';
    }

    // Default: Active district complete report
    var cur = findDistrict(getActiveDistrictName(), list) || list[0];
    return formatFullDistrictReport(cur);
  }

  // Remove BOTH top-right header icons (document + notification bell) and mount History button
  function patchHeader(){
    var btns = Array.prototype.slice.call(document.querySelectorAll('header button, nav button, button, [role="button"]')).filter(function(el){
      if (el.id === 'at-history-btn' || el.id === 'at-askai-fab' || el.id === 'at-demo-toggle') return false;
      if (el.closest && (el.closest('#at-hist-bg') || el.closest('#at-askai-bg'))) return false;
      var r = el.getBoundingClientRect();
      return r.width > 14 && r.width <= 72 && r.height > 14 && r.height <= 72 && r.top >= 0 && r.bottom <= 115 && r.left > window.innerWidth * 0.50;
    });

    var slot = null;
    btns.forEach(function(el){
      if (!slot && el.parentNode) slot = el.parentNode;
      el.style.setProperty('display','none','important');
      el.style.setProperty('visibility','hidden','important');
      el.style.setProperty('pointer-events','none','important');
    });

    if (!document.getElementById('at-history-btn')) {
      var hb = document.createElement('button');
      hb.id = 'at-history-btn';
      hb.type = 'button';
      hb.className = 'at-hist-btn';
      hb.innerHTML =
        '<svg viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path stroke-linecap="round" stroke-linejoin="round" d="M3 3v5h5"/><path stroke-linecap="round" stroke-linejoin="round" d="M12 7v5l3 2"/></svg>' +
        '<span>History</span><span class="at-hist-count" id="at-hist-count">' + loadHistory().length + '</span>';
      hb.addEventListener('click', function(e){
        e.preventDefault();
        e.stopPropagation();
        openHistory();
      });
      if (slot) {
        slot.appendChild(hb);
      } else {
        hb.style.position = 'fixed';
        hb.style.top = '12px';
        hb.style.right = '14px';
        document.body.appendChild(hb);
      }
    }
  }

  function ensureHistoryModal(){
    if (document.getElementById('at-hist-bg')) return;
    var bg = document.createElement('div');
    bg.id = 'at-hist-bg';
    bg.className = 'at-sheet-bg';
    bg.innerHTML =
      '<div class="at-sheet">' +
        '<div class="at-sheet-head">' +
          '<div><div class="at-sheet-title">Ask AI History</div><div class="at-sheet-sub">Search saved Q&amp;As or ask &amp; save new</div></div>' +
          '<div style="display:flex;gap:6px"><button type="button" class="at-sheet-btn" id="at-hist-clear">Clear</button><button type="button" class="at-sheet-btn" id="at-hist-close">Close</button></div>' +
        '</div>' +
        '<div class="at-hist-search-bar">' +
          '<input type="text" class="at-input" id="at-hist-search" placeholder="Search history or ask a question..." />' +
          '<button type="button" class="at-send" id="at-hist-ask" style="font-size:11.5px;padding:0 12px">Ask &amp; Save</button>' +
        '</div>' +
        '<div class="at-sheet-body" id="at-hist-body"></div>' +
      '</div>';
    document.body.appendChild(bg);

    bg.addEventListener('click', function(e){
      if (e.target === bg && Date.now() - histOpenedAt > 450) bg.classList.remove('open');
    });
    document.getElementById('at-hist-close').addEventListener('click', function(){ bg.classList.remove('open'); });
    document.getElementById('at-hist-clear').addEventListener('click', function(){ saveHistory([]); renderHistory(); });

    var inp = document.getElementById('at-hist-search');
    inp.addEventListener('input', function(){ histSearch = this.value || ''; renderHistory(); });
    function askNow(){
      var q = (inp.value || '').trim();
      if (!q) return;
      var a = answerQuery(q);
      recordQa(q, a);
      inp.value = '';
      histSearch = '';
      renderHistory();
    }
    document.getElementById('at-hist-ask').addEventListener('click', askNow);
    inp.addEventListener('keydown', function(e){ if (e.key === 'Enter'){ e.preventDefault(); askNow(); } });
  }

  function renderHistory(){
    var body = document.getElementById('at-hist-body');
    if (!body) return;
    var all = loadHistory();
    var needle = histSearch.trim().toLowerCase();
    var items = needle ? all.filter(function(x){ return (x.q + ' ' + x.a).toLowerCase().indexOf(needle) !== -1; }) : all;

    if (!items.length) {
      body.innerHTML = '<div class="at-qa-card"><div class="at-qa-q">' +
        (needle ? 'No saved match for "' + esc(needle) + '"' : 'No Ask AI questions saved yet') +
        '</div><div class="at-qa-a">' +
        (needle ? 'Tap "Ask & Save" above to get a live Satellite + Water + Groundwater answer and save it.' : 'Ask any question in Ask AI or type above and tap "Ask & Save" — every question and full answer is saved here.') +
        '</div></div>';
      return;
    }

    body.innerHTML = items.map(function(it){
      return '<div class="at-qa-card">' +
        '<div class="at-qa-head"><span>Ask AI • ' + esc(it.t) + '</span><button type="button" class="at-qa-del" data-id="' + esc(it.id) + '">Delete</button></div>' +
        '<div class="at-qa-q">Q: ' + esc(it.q) + '</div>' +
        '<div class="at-qa-a">A: ' + esc(it.a) + '</div>' +
      '</div>';
    }).join('');

    var dels = body.querySelectorAll('.at-qa-del');
    for (var i = 0; i < dels.length; i++) {
      dels[i].addEventListener('click', function(){
        var id = this.getAttribute('data-id');
        saveHistory(loadHistory().filter(function(x){ return x.id !== id; }));
        renderHistory();
      });
    }
  }

  function openHistory(){
    ensureHistoryModal();
    histOpenedAt = Date.now();
    renderHistory();
    document.getElementById('at-hist-bg').classList.add('open');
  }

  function ensureAskAiModal(){
    if (document.getElementById('at-askai-bg')) return;
    var bg = document.createElement('div');
    bg.id = 'at-askai-bg';
    bg.className = 'at-sheet-bg';
    bg.innerHTML =
      '<div class="at-sheet">' +
        '<div class="at-sheet-head">' +
          '<div><div class="at-sheet-title">AquaTwin Ask AI</div><div class="at-sheet-sub">Real-Time Satellite • Surface Water • Groundwater</div></div>' +
          '<div style="display:flex;gap:6px"><button type="button" class="at-sheet-btn" id="at-askai-hist">History</button><button type="button" class="at-sheet-btn" id="at-askai-close">Close</button></div>' +
        '</div>' +
        '<div class="at-live-strip" id="at-live-strip"><span class="at-live-dot"></span><span id="at-live-strip-txt">Loading live 33-district dataset...</span></div>' +
        '<div class="at-tabs-row" id="at-askai-chips">' +
          '<button type="button" class="at-tab-chip" data-q="Current district full report">Current District</button>' +
          '<button type="button" class="at-tab-chip" data-q="Real time satellite data">Satellite Data</button>' +
          '<button type="button" class="at-tab-chip" data-q="Groundwater status">Groundwater</button>' +
          '<button type="button" class="at-tab-chip" data-q="Highest risk water districts">High Risk</button>' +
          '<button type="button" class="at-tab-chip" data-q="Telangana state summary">State Summary</button>' +
        '</div>' +
        '<div class="at-sheet-body" id="at-askai-msgs">' +
          '<div class="at-msg ai">Ready! Ask about any of Telangana\'s 33 districts for live Sentinel-2 satellite metrics, surface water WQI/forecasts, and groundwater aquifer depth. Every Q&amp;A auto-saves to History.</div>' +
        '</div>' +
        '<div class="at-input-bar">' +
          '<input type="text" class="at-input" id="at-askai-input" placeholder="Ask about Hyderabad, satellite, groundwater..." />' +
          '<button type="button" class="at-send" id="at-askai-send">Send</button>' +
        '</div>' +
      '</div>';
    document.body.appendChild(bg);

    function sendMsg(text){
      var msg = String(text || '').trim();
      if (!msg) return;
      var box = document.getElementById('at-askai-msgs');
      var u = document.createElement('div');
      u.className = 'at-msg user';
      u.textContent = msg;
      box.appendChild(u);

      var reply = '';
      try {
        reply = answerQuery(msg);
        recordQa(msg, reply);
      } catch(err) {
        reply = 'Unable to compute answer right now: ' + (err && err.message ? err.message : 'unknown error');
      }

      var a = document.createElement('div');
      a.className = 'at-msg ai';
      a.innerHTML = esc(reply) + '<span class="at-saved-tag">Saved to History</span>';
      box.appendChild(a);
      box.scrollTop = box.scrollHeight;
    }

    bg.addEventListener('click', function(e){
      if (e.target === bg && Date.now() - askOpenedAt > 450) bg.classList.remove('open');
    });
    document.getElementById('at-askai-close').addEventListener('click', function(){ bg.classList.remove('open'); });
    document.getElementById('at-askai-hist').addEventListener('click', function(){ bg.classList.remove('open'); openHistory(); });
    document.getElementById('at-askai-send').addEventListener('click', function(){
      var inp = document.getElementById('at-askai-input');
      sendMsg(inp.value);
      inp.value = '';
    });
    var inp = document.getElementById('at-askai-input');
    inp.addEventListener('keydown', function(e){ if (e.key === 'Enter'){ e.preventDefault(); sendMsg(this.value); this.value = ''; } });
    document.getElementById('at-askai-chips').addEventListener('click', function(e){
      var c = e.target.closest('.at-tab-chip');
      if (c) sendMsg(c.getAttribute('data-q'));
    });
  }

  function openAskAi(){
    ensureAskAiModal();
    askOpenedAt = Date.now();
    var list = getDistricts();
    var stxt = document.getElementById('at-live-strip-txt');
    if (stxt) {
      stxt.textContent = list.length + ' Districts Live • Satellite + Water + GW • ' + getSyncStamp();
    }
    document.getElementById('at-askai-bg').classList.add('open');
  }

  function mountFab(){
    // Hide any legacy/original Ask AI button so it can never block or conflict
    var els = document.querySelectorAll('button, [role="button"], div, a');
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      if (el.id === 'at-askai-fab' || (el.closest && (el.closest('#at-askai-bg') || el.closest('#at-hist-bg')))) continue;
      var txt = (el.textContent || '').replace(/\s+/g,' ').trim();
      if (/^ask\s*ai$/i.test(txt)) {
        var r = el.getBoundingClientRect();
        if (r.width > 40 && r.width < 250 && r.height > 24 && r.height < 110 && r.bottom > window.innerHeight * 0.55) {
          el.style.setProperty('display','none','important');
          el.style.setProperty('pointer-events','none','important');
        }
      }
    }

    if (document.getElementById('at-askai-fab')) return;
    var fab = document.createElement('button');
    fab.id = 'at-askai-fab';
    fab.type = 'button';
    fab.innerHTML = '<svg viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 18h6m-5 3h4M12 3a7 7 0 0 0-4 12.7c.7.6 1 1.3 1 2.3h6c0-1 .3-1.7 1-2.3A7 7 0 0 0 12 3z"/></svg><span>Ask AI</span>';

    function onTap(e){
      var now = Date.now();
      if (now - lastFabTap < 400) return;
      lastFabTap = now;
      e.preventDefault();
      e.stopPropagation();
      openAskAi();
    }
    fab.addEventListener('touchend', onTap, { passive: false });
    fab.addEventListener('click', onTap);
    document.body.appendChild(fab);
  }

  function boot(){
    injectCss();
    patchHeader();
    mountFab();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function(){ setTimeout(boot, 250); });
  } else {
    setTimeout(boot, 250);
  }
  setInterval(function(){ patchHeader(); mountFab(); }, 1500);
})();
