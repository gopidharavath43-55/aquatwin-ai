/* ==========================================================================
   AquaTwin AI — Universal Apple Liquid Glass Engine, 33-District AI Advisor,
   CSV Merge/Dedup, Apple Maps Styles & High-Capacity Persistent Storage
   ========================================================================== */
(function () {
  'use strict';

  var HORIZONS = ['1m', '2m', '6m', '1y'];
  var MAP_STYLES = ['satellite', 'explore', 'dark'];
  var EXPECTED_FP = '3d595bae06b6bafc348b97e1804200e50a826695b13063b34658f97b28d81dbc';
  var BAKED_VERSION = window.AQUATWIN_VERSION || '1.150';
  var DB_NAME = 'AquaTwinVaultDB';
  var DB_VERSION = 1;
  var MERGED_STORAGE_KEY = 'aquatwin_merged_records_v1';
  if (!window.AQUATWIN_VERSION) window.AQUATWIN_VERSION = BAKED_VERSION;

  /* ------------------------------------------------------------------------
     1. Security, Sanitization & Integrity Lock
     ------------------------------------------------------------------------ */
  window.atEscapeHtml = function (str) {
    return String(str == null ? '' : str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  };

  window.atSafeJsonParse = function (raw) {
    return JSON.parse(raw, function (k, v) {
      if (k === '__proto__' || k === 'constructor' || k === 'prototype') return undefined;
      return v;
    });
  };

  window.atIsTrustedApkUrl = function (url) {
    try {
      var u = new URL(String(url || ''));
      return u.protocol === 'https:' && u.hostname === 'github.com' &&
        u.pathname.indexOf('/gopidharavath43-55/aquatwin-ai/releases/') === 0;
    } catch (e) { return false; }
  };

  function deepFreeze(obj, seen) {
    if (!obj || typeof obj !== 'object') return obj;
    if (!seen) seen = new Set();
    if (seen.has(obj) || Object.isFrozen(obj)) return obj;
    seen.add(obj);
    Object.freeze(obj);
    Object.keys(obj).forEach(function (k) { deepFreeze(obj[k], seen); });
    return obj;
  }

  function verifyTelemetryFingerprint() {
    var list = (window.AQUATWIN_ML_DATA && Array.isArray(window.AQUATWIN_ML_DATA.districts))
      ? window.AQUATWIN_ML_DATA.districts : null;
    if (!list || !list.length || !window.crypto || !window.crypto.subtle) return;
    var parts = list.map(function (d) {
      var name = String(d.district || '').trim().toLowerCase();
      var val = (d.xgb_wqi != null) ? d.xgb_wqi : (d.wqi_score != null ? d.wqi_score : 0);
      return name + ':' + Math.floor(Number(val) * 10 + 0.5);
    }).sort();
    var bytes = new TextEncoder().encode(parts.join('|'));
    window.crypto.subtle.digest('SHA-256', bytes).then(function (buf) {
      var hex = Array.from(new Uint8Array(buf)).map(function (x) { return x.toString(16).padStart(2, '0'); }).join('');
      if (hex !== EXPECTED_FP) console.warn('AQUATWIN_SECURITY: Fingerprint mismatch:', hex);
      else console.log('AQUATWIN_SECURITY: Runtime data frozen & SHA-256 verified.');
    }).catch(function () {});
  }

  /* ------------------------------------------------------------------------
     2. Persistent High-Capacity Storage Vault (IndexedDB + CacheStorage)
     ------------------------------------------------------------------------ */
  function openVaultDB() {
    return new Promise(function (resolve) {
      if (!window.indexedDB) { resolve(null); return; }
      try {
        var req = window.indexedDB.open(DB_NAME, DB_VERSION);
        req.onupgradeneeded = function (ev) {
          var db = ev.target.result;
          if (!db.objectStoreNames.contains('vault')) db.createObjectStore('vault');
        };
        req.onsuccess = function (ev) { resolve(ev.target.result); };
        req.onerror = function () { resolve(null); };
      } catch (e) { resolve(null); }
    });
  }

  function vaultPut(key, value) {
    return openVaultDB().then(function (db) {
      if (!db) return;
      return new Promise(function (res) {
        try {
          var tx = db.transaction('vault', 'readwrite');
          tx.objectStore('vault').put(value, key);
          tx.oncomplete = function () { res(true); };
          tx.onerror = function () { res(false); };
        } catch (e) { res(false); }
      });
    });
  }

  function vaultGet(key) {
    return openVaultDB().then(function (db) {
      if (!db) return null;
      return new Promise(function (res) {
        try {
          var tx = db.transaction('vault', 'readonly');
          var req = tx.objectStore('vault').get(key);
          req.onsuccess = function () { res(req.result || null); };
          req.onerror = function () { res(null); };
        } catch (e) { res(null); }
      });
    });
  }

  function requestPersistentStorage() {
    if (navigator.storage && typeof navigator.storage.persist === 'function') {
      navigator.storage.persist().catch(function () {});
    }
  }

  function updateStorageStatusUI(extraMsg) {
    var el = document.getElementById('at-storage-status');
    if (!el) return;
    if (navigator.storage && typeof navigator.storage.estimate === 'function') {
      navigator.storage.estimate().then(function (est) {
        var usedMb = ((est.usage || 0) / (1024 * 1024)).toFixed(2);
        var quotaMb = ((est.quota || 0) / (1024 * 1024)).toFixed(0);
        el.textContent = (extraMsg ? extraMsg + ' • ' : '') + usedMb + ' MB / ' + quotaMb + ' MB stored';
      }).catch(function () {
        el.textContent = extraMsg || 'Persistent Storage Ready';
      });
    } else {
      el.textContent = extraMsg || 'Local Vault Active';
    }
  }

  function prewarmTileStorage(showNotification) {
    if (navigator.onLine === false) {
      updateStorageStatusUI('Offline vault ready');
      return;
    }
    var urls = [];
    // Pre-cache Telangana tiles across zoom 6..8 for Satellite, Explore, and Dark Apple Maps styles
    var boxes = [
      [6, 45, 46, 28, 29],
      [7, 91, 93, 56, 58],
      [8, 182, 185, 113, 116]
    ];
    boxes.forEach(function (b) {
      var z = b[0];
      for (var x = b[1]; x <= b[2]; x++) {
        for (var y = b[3]; y <= b[4]; y++) {
          urls.push('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/' + z + '/' + y + '/' + x);
          urls.push('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/' + z + '/' + y + '/' + x);
          urls.push('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/' + z + '/' + y + '/' + x);
        }
      }
    });

    if (showNotification) showToast('Caching ' + urls.length + ' map tiles to storage...');
    var idx = 0;
    function step() {
      if (idx >= urls.length) {
        updateStorageStatusUI(urls.length + ' tiles cached');
        if (showNotification) showToast('Offline tile vault updated');
        return;
      }
      var batch = urls.slice(idx, idx + 4);
      idx += 4;
      Promise.all(batch.map(function (u) {
        return fetch(u, { mode: 'cors' }).catch(function () {});
      })).then(function () {
        setTimeout(step, 80);
      });
    }
    step();
  }

  /* ------------------------------------------------------------------------
     3. Safe Capacitor Haptics + Toast
     ------------------------------------------------------------------------ */
  function triggerHaptic(style) {
    try {
      var cap = window.Capacitor;
      if (cap && cap.Plugins && cap.Plugins.Haptics && typeof cap.Plugins.Haptics.impact === 'function') {
        cap.Plugins.Haptics.impact({ style: style || 'LIGHT' }).catch(function () {});
        return;
      }
      if (
        navigator.vibrate &&
        navigator.userActivation &&
        navigator.userActivation.hasBeenActive
      ) {
        navigator.vibrate(style === 'MEDIUM' ? 14 : 8);
      }
    } catch (e) {}
  }
  window.atTriggerHaptic = triggerHaptic;

  function showToast(msg) {
    var t = document.getElementById('at-toast');
    if (!t) return;
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(t._tm);
    t._tm = setTimeout(function () { t.classList.remove('show'); }, 2200);
  }
  window.atToast = showToast;

  /* ------------------------------------------------------------------------
     4. Telangana 33-District Telemetry & Merged CSV Overlay Store
     ------------------------------------------------------------------------ */
  function num(v, fb) {
    var n = Number(v);
    return isFinite(n) ? n : fb;
  }

  function getStatusFromData(turb, water) {
    if (isNaN(turb)) return 'Normal';
    if (turb >= 1.15) return 'High Turbidity';
    if (!isNaN(water) && water < 1.0) return 'Low Water';
    return 'Normal';
  }

  function computeAI(turb, water, ndwi) {
    var t = isNaN(turb) ? 1.0 : turb;
    var w = isNaN(water) ? 1.5 : water;
    var n = isNaN(ndwi) ? -0.45 : ndwi;
    var raw = 88.0 - Math.max(0, (t - 0.95) * 110.0) + Math.min(10.0, w * 2.2) + (n + 0.5) * 20.0;
    var wqi = Number(Math.max(15.0, Math.min(98.0, raw)).toFixed(1));
    var risk = wqi < 55 ? 'High Risk' : (wqi < 72 ? 'Moderate Risk' : 'Low Risk');
    return { wqi: wqi, risk: risk };
  }

  function statusClass(s) {
    if (s === 'High Turbidity') return 'High';
    if (s === 'Low Water') return 'Low';
    return 'Normal';
  }

  function statusColor(s) {
    if (s === 'High Turbidity') return '#FF6961';
    if (s === 'Low Water') return '#FFD60A';
    return '#32D74B';
  }

  function normDistrictKey(name) {
    var k = String(name || '').toLowerCase().replace(/[^a-z0-9]/g, '');
    var aliases = {
      rangareddy: 'rangareddy',
      komarambheem: 'kumurambheemasifabad',
      komarambheemasifabad: 'kumurambheemasifabad',
      kumurambheem: 'kumurambheemasifabad',
      bhadradri: 'bhadradrikothagudem',
      jayashankar: 'jayashankarbhupalpally',
      jogulamba: 'jogulambagadwal',
      medchalmalkajgiri: 'medchalmalkajgiri',
      medchal: 'medchalmalkajgiri',
      rajannasircilla: 'rajannasircilla',
      sircilla: 'rajannasircilla',
      yadadri: 'yadadribhuvanagiri',
      yadadribhuvanagiri: 'yadadribhuvanagiri',
      peddapalle: 'peddapalli',
      jangoan: 'jangaon',
      hanamkonda: 'hanumakonda',
      hyd: 'hyderabad'
    };
    return aliases[k] || k;
  }

  function loadMergedOverrides() {
    try {
      var raw = JSON.parse(localStorage.getItem(MERGED_STORAGE_KEY) || '[]');
      return Array.isArray(raw) ? raw : [];
    } catch (e) { return []; }
  }

  function pickOvNum(ov, keys) {
    if (!ov) return null;
    for (var i = 0; i < keys.length; i++) {
      var v = ov[keys[i]];
      if (v !== undefined && v !== null && v !== '' && isFinite(Number(v))) return Number(v);
    }
    return null;
  }

  function buildDistrictList() {
    var ml = (window.AQUATWIN_ML_DATA && Array.isArray(window.AQUATWIN_ML_DATA.districts))
      ? window.AQUATWIN_ML_DATA.districts : [];
    var raw = (window.TELANGANA_DATA && Array.isArray(window.TELANGANA_DATA))
      ? window.TELANGANA_DATA : [];
    var overrides = loadMergedOverrides().slice().sort(function (a, b) {
      return String((a && a.date) || '').localeCompare(String((b && b.date) || ''));
    });
    var ovMap = {};
    overrides.forEach(function (o) {
      if (o && o.district) ovMap[normDistrictKey(o.district)] = o;
    });

    var src = ml.length ? ml : raw;
    return src.map(function (r) {
      var dName = String(r.district || 'Hyderabad').trim();
      var ov = ovMap[normDistrictKey(dName)];
      var lat = num(r.latitude != null ? r.latitude : r.lat, 17.385);
      var lng = num(r.longitude != null ? r.longitude : r.lon, 78.4867);
      var ovNdwi = pickOvNum(ov, ['ndwi_mean', 'ndwi']);
      var ovTurb = pickOvNum(ov, ['turbidity_index', 'turbidity', 'turb']);
      var ovWater = pickOvNum(ov, ['water_coverage_pct', 'water_coverage', 'water']);
      var ovGw = pickOvNum(ov, ['groundwater_level_m', 'gw_depth_mbgl', 'gw_depth']);
      var ovRes = pickOvNum(ov, ['reservoir_capacity_percent', 'res_storage_pct', 'reservoir_pct']);
      var ovRain = pickOvNum(ov, ['rainfall_mm', 'rainfall', 'rain']);
      var ovPoll = pickOvNum(ov, ['pollution_idx', 'pollution']);

      var ndwi = ovNdwi != null ? ovNdwi : num(r.ndwi_mean, -0.45);
      var turb = ovTurb != null ? ovTurb : num(r.turbidity_index, 1.05);
      var water = ovWater != null ? ovWater : num(r.water_coverage_pct, 1.5);
      var gwDepth = ovGw != null ? ovGw : num(r.gw_depth_mbgl, 8.2);
      var resPct = ovRes != null ? ovRes : num(r.res_storage_pct != null ? r.res_storage_pct : r.reservoir_idx, 50.0);
      var rainMm = ovRain != null ? ovRain : num(r.rainfall_mm, 20.0);
      var pollIdx = ovPoll != null ? ovPoll : num(r.pollution_idx, 40.0);

      var status = getStatusFromData(turb, water);
      var ai = computeAI(turb, water, ndwi);
      var ovWqi = pickOvNum(ov, ['wqi_score', 'xgb_wqi', 'wqi']);
      var wqi = ov ? (ovWqi != null ? ovWqi : ai.wqi) : (r.wqi_score != null ? num(r.wqi_score, ai.wqi) : ai.wqi);
      var xgbWqi = ov ? (ovWqi != null ? ovWqi : ai.wqi) : (r.xgb_wqi != null ? num(r.xgb_wqi, wqi) : wqi);

      return {
        district: dName,
        lat: lat,
        lng: lng,
        ndwi: Number(ndwi.toFixed(4)),
        turb: Number(turb.toFixed(4)),
        water: Number(water.toFixed(4)),
        pollution_idx: pollIdx,
        status: status,
        wqi: Number(wqi.toFixed(1)),
        xgb_wqi: Number(xgbWqi.toFixed(1)),
        risk: ov ? (wqi < 55 ? 'High Risk' : (wqi < 72 ? 'Moderate Risk' : 'Low Risk')) : (r.risk_level || ai.risk),
        lstm_1m_wqi: num(r.lstm_1m_wqi, xgbWqi),
        lstm_2m_wqi: num(r.lstm_2m_wqi, xgbWqi),
        lstm_6m_wqi: num(r.lstm_6m_wqi, xgbWqi),
        lstm_1y_wqi: num(r.lstm_1y_wqi, xgbWqi),
        gw_depth: gwDepth,
        gw_ext: num(r.gw_extraction_pct, 48.0),
        gw_rech: num(r.gw_recharge_mm, 12.0),
        gw_status: gwDepth >= 13 ? 'Over-Exploited' : (gwDepth >= 11.5 ? 'Critical' : (r.gw_status || 'Safe')),
        gw_1m: num(r.gw_pred_1m, gwDepth),
        gw_2m: num(r.gw_pred_2m, gwDepth),
        gw_6m: num(r.gw_pred_6m, gwDepth),
        gw_1y: num(r.gw_pred_1y, gwDepth),
        res_name: r.reservoir_name || 'Basin Reservoir',
        river_basin: r.river_basin || 'Godavari',
        res_cap: num(r.res_capacity_tmc, 10.0),
        res_sto: num(r.res_storage_tmc, 5.0),
        res_pct: resPct,
        res_status: resPct < 35 ? 'Low' : (resPct < 65 ? 'Moderate' : (r.res_status || 'Normal')),
        res_1m: num(r.res_pred_1m, resPct),
        res_2m: num(r.res_pred_2m, resPct),
        res_6m: num(r.res_pred_6m, resPct),
        res_1y: num(r.res_pred_1y, resPct),
        rain: rainMm,
        rain_dep: num(r.rain_departure_pct, -15.0),
        rain_6m_cum: num(r.rain_6m_cum_mm, 620.0),
        spi_6m: num(r.spi_6m_proxy, -0.7),
        rain_status: r.rain_status || 'Normal',
        rain_1m: num(r.rain_pred_1m, rainMm),
        rain_2m: num(r.rain_pred_2m, rainMm),
        rain_6m: num(r.rain_pred_6m, rainMm),
        rain_1y: num(r.rain_pred_1y, rainMm),
        hydro_stress: num(r.hydro_stress_index, 38.0),
        sync: ov && ov.date ? ('CSV ' + ov.date) : (r.last_satellite_sync || (window.AQUATWIN_ML_DATA && window.AQUATWIN_ML_DATA.last_satellite_sync) || 'Live')
      };
    });
  }

  var districts = buildDistrictList();
  var selected = districts.find(function (d) { return d.district.toLowerCase() === 'hyderabad'; }) || districts[0];
  var activeHorizon = '6m';
  var activeView = 'map';
  var isDemoOn = false;
  var demoIdx = 0;
  var demoTimer = null;
  var map = null;
  var activeMapStyle = 'satellite';
  var layers = {};
  var markerRefs = {};
  var simChart = null;
  var sheetChart = null;

  /* ------------------------------------------------------------------------
     5. 33-District Multi-Modal AI Recommendation & Optimization Engine
     ------------------------------------------------------------------------ */
  function buildRecommendations(d, simOverrides) {
    if (!d) return { items: [], benchmark: '', optimalDelta: { rain: 15, temp: -0.5, poll: -25 } };
    var turb = simOverrides ? simOverrides.turb : d.turb;
    var water = simOverrides ? simOverrides.water : d.water;
    var wqi = simOverrides ? simOverrides.wqi : d.xgb_wqi;

    // Peer Benchmark in the same River Basin across all 33 districts
    var basinPeers = districts.filter(function (x) { return x.river_basin === d.river_basin && x.district !== d.district; })
      .sort(function (a, b) { return b.xgb_wqi - a.xgb_wqi; });
    var bestPeer = basinPeers[0] || districts.slice().sort(function (a, b) { return b.xgb_wqi - a.xgb_wqi; })[0];

    var items = [];

    // 1. Surface Water & Turbidity / Pollution Intervention
    if (turb >= 1.15 || d.pollution_idx >= 48 || wqi < 65) {
      items.push({
        priority: 'Immediate',
        gain: '+7.2 WQI',
        text: 'Deploy multi-stage intake filtration & curb urban/industrial runoff (' + d.district + ' turbidity ' + turb.toFixed(2) + ', pollution idx ' + d.pollution_idx.toFixed(0) + ').'
      });
    } else {
      items.push({
        priority: 'Maintain',
        gain: '+2.4 WQI',
        text: 'Surface clarity optimal (turbidity ' + turb.toFixed(2) + ', NDWI ' + d.ndwi.toFixed(3) + '); sustain Sentinel-2 5-day monitoring.'
      });
    }

    // 2. Groundwater Aquifer Balance
    if (d.gw_ext >= 75 || d.gw_depth >= 11.0 || d.gw_status === 'Over-Exploited' || d.gw_status === 'Critical') {
      items.push({
        priority: '30-Day Aquifer',
        gain: '+14% Recharge',
        text: 'Enforce borewell extraction caps (' + d.gw_ext.toFixed(1) + '% used, ' + d.gw_depth.toFixed(1) + ' mbgl ' + d.gw_status + ') and construct urban injection recharge shafts.'
      });
    } else {
      items.push({
        priority: 'Aquifer Buffer',
        gain: '+0.6m Table',
        text: 'Groundwater stable at ' + d.gw_depth.toFixed(2) + ' mbgl (' + d.gw_ext.toFixed(1) + '% extraction); expand check-dam percolation ahead of dry months.'
      });
    }

    // 3. Reservoir & Drought / Trajectory Optimization
    var wqiTrend6m = d.lstm_6m_wqi - d.xgb_wqi;
    if (d.res_pct < 40 || water < 1.0) {
      items.push({
        priority: 'Reservoir Allocation',
        gain: '+12% Storage',
        text: d.res_name + ' at ' + d.res_pct.toFixed(1) + '% (' + d.res_status + '). Shift irrigation to micro-drip & balance canal feed from ' + bestPeer.district + ' surplus corridor.'
      });
    } else if (wqiTrend6m < -3 || d.rain_status === 'Deficit') {
      items.push({
        priority: 'Seasonal Forecast',
        gain: '+5.5 WQI',
        text: '6-month forecast dips to ' + d.lstm_6m_wqi.toFixed(1) + ' WQI (SPI ' + d.spi_6m.toFixed(2) + '). Pre-stage ' + d.res_name + ' (' + d.res_pct.toFixed(0) + '%) buffer releases.'
      });
    } else {
      items.push({
        priority: 'Basin Surplus',
        gain: 'Top Resilience',
        text: d.res_name + ' holds ' + d.res_pct.toFixed(1) + '% storage; maintain balanced outflow and inter-district drought reserve.'
      });
    }

    var benchmarkText = bestPeer
      ? ('Basin Benchmark (' + d.river_basin + '): ' + bestPeer.district + ' achieves ' + bestPeer.xgb_wqi.toFixed(1) + ' WQI (' + bestPeer.res_pct.toFixed(0) + '% reservoir, ' + bestPeer.gw_depth.toFixed(1) + 'm GW).')
      : '';

    var optRain = (d.res_pct < 40 || d.rain_status === 'Deficit' || water < 1.0) ? 25 : 10;
    var optTemp = (d.res_pct < 45 || d.gw_depth >= 11) ? -1.0 : -0.5;
    var optPoll = (turb >= 1.15 || d.pollution_idx >= 48 || wqi < 65) ? -30 : -15;

    return {
      items: items,
      benchmark: benchmarkText,
      optimalDelta: { rain: optRain, temp: optTemp, poll: optPoll }
    };
  }
  window.atBuildRecommendations = buildRecommendations;

  function getStateOptimizationSummary() {
    var avgWqi = districts.reduce(function (s, d) { return s + d.xgb_wqi; }, 0) / Math.max(1, districts.length);
    var topUrgent = districts.slice().sort(function (a, b) {
      var sa = a.xgb_wqi - (a.gw_ext > 80 ? 10 : 0) - (a.res_pct < 30 ? 8 : 0);
      var sb = b.xgb_wqi - (b.gw_ext > 80 ? 10 : 0) - (b.res_pct < 30 ? 8 : 0);
      return sa - sb;
    }).slice(0, 3);
    var bestResilient = districts.slice().sort(function (a, b) { return b.xgb_wqi - a.xgb_wqi; }).slice(0, 3);

    return {
      avgWqi: avgWqi,
      topUrgent: topUrgent,
      bestResilient: bestResilient
    };
  }
  window.atGetStateOptimizationSummary = getStateOptimizationSummary;

  window.atGetLiveDistricts = function () { return districts; };

  function renderRecommendationNodes(containerId, d, simOverrides) {
    var box = document.getElementById(containerId);
    if (!box) return;
    var rec = buildRecommendations(d, simOverrides);
    box.innerHTML = rec.items.map(function (it) {
      return '<div class="ai-rec-item">' +
        '<div class="ai-rec-top"><span class="ai-rec-tag">' + window.atEscapeHtml(it.priority) + '</span><span class="ai-rec-gain tabular">' + window.atEscapeHtml(it.gain) + '</span></div>' +
        '<div class="ai-rec-body">' + window.atEscapeHtml(it.text) + '</div>' +
      '</div>';
    }).join('') + (rec.benchmark ? '<div class="ai-rec-bench">' + window.atEscapeHtml(rec.benchmark) + '</div>' : '');
  }

  /* ------------------------------------------------------------------------
     6. Liquid Glass Appearance & Apple Maps Style Controller
     ------------------------------------------------------------------------ */
  function setGlassMix(pct, modeName) {
    var clamped = Math.max(0, Math.min(100, Number(pct)));
    var mix = clamped / 100;
    var root = document.documentElement;
    var mode = modeName || (clamped <= 22 ? 'clear' : (clamped >= 75 ? 'tinted' : 'default'));

    root.setAttribute('data-glass-mode', mode);
    root.style.setProperty('--lg-mix', mix.toFixed(2));
    root.style.setProperty('--lg-clear-scrim', (0.28 + mix * 0.28).toFixed(2));
    root.style.setProperty('--lg-regular-alpha', (0.50 + mix * 0.34).toFixed(2));

    var slider = document.getElementById('at-glass-slider');
    var pctEl = document.getElementById('at-glass-pct');
    var lblEl = document.getElementById('at-glass-mode-label');
    if (slider) slider.value = String(Math.round(clamped));
    if (pctEl) pctEl.textContent = Math.round(clamped) + '%';
    if (lblEl) lblEl.textContent = mode.charAt(0).toUpperCase() + mode.slice(1);

    document.querySelectorAll('[data-glass-preset]').forEach(function (b) {
      b.classList.toggle('active', b.getAttribute('data-glass-preset') === mode);
    });

    try {
      localStorage.setItem('aquatwin_glass_mix', String(Math.round(clamped)));
      localStorage.setItem('aquatwin_glass_mode', mode);
    } catch (e) {}
  }

  function setMapStyle(styleName) {
    if (MAP_STYLES.indexOf(styleName) === -1) return;
    activeMapStyle = styleName;
    if (map && layers.satBase) {
      Object.keys(layers).forEach(function (k) {
        if (map.hasLayer(layers[k])) map.removeLayer(layers[k]);
      });
      if (styleName === 'satellite') {
        layers.satBase.addTo(map);
        layers.satLabels.addTo(map);
      } else if (styleName === 'explore') {
        layers.explore.addTo(map);
      } else {
        layers.dark.addTo(map);
        if (layers.darkLabels) layers.darkLabels.addTo(map);
      }
    }

    var mapSection = document.getElementById('view-map');
    if (mapSection) {
      mapSection.setAttribute('aria-label', 'Apple Maps ' + styleName.charAt(0).toUpperCase() + styleName.slice(1) + ' View');
    }
    var lbl = document.getElementById('at-map-mode-label');
    if (lbl) lbl.textContent = styleName.charAt(0).toUpperCase() + styleName.slice(1);
    document.querySelectorAll('[data-map-style]').forEach(function (b) {
      b.classList.toggle('active', b.getAttribute('data-map-style') === styleName);
    });
    try { localStorage.setItem('aquatwin_map_style', styleName); } catch (e) {}
  }

  function initGlassAndMapControls() {
    var savedMix = 45, savedMode = 'default', savedMap = 'satellite';
    try {
      var m = localStorage.getItem('aquatwin_glass_mix');
      var md = localStorage.getItem('aquatwin_glass_mode');
      var mp = localStorage.getItem('aquatwin_map_style');
      if (m !== null && !isNaN(Number(m))) savedMix = Number(m);
      if (md) savedMode = md;
      if (mp && MAP_STYLES.indexOf(mp) !== -1) savedMap = mp;
    } catch (e) {}
    setGlassMix(savedMix, savedMode);
    activeMapStyle = savedMap;

    var pop = document.getElementById('at-glass-popover');
    var slider = document.getElementById('at-glass-slider');
    if (slider) slider.addEventListener('input', function () { setGlassMix(this.value); });

    document.querySelectorAll('[data-glass-preset]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        triggerHaptic('LIGHT');
        var preset = btn.getAttribute('data-glass-preset');
        setGlassMix(preset === 'clear' ? 10 : (preset === 'tinted' ? 90 : 45), preset);
      });
    });

    document.querySelectorAll('[data-map-style]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        triggerHaptic('LIGHT');
        var st = btn.getAttribute('data-map-style');
        setMapStyle(st);
        showToast('Apple Maps: ' + st.charAt(0).toUpperCase() + st.slice(1));
      });
    });

    var warmBtn = document.getElementById('at-warm-storage');
    if (warmBtn) {
      warmBtn.addEventListener('click', function () {
        triggerHaptic('MEDIUM');
        prewarmTileStorage(true);
      });
    }

    document.addEventListener('click', function (e) {
      var trg = e.target && e.target.closest ? e.target.closest('[data-open-appearance="1"]') : null;
      if (trg) {
        e.stopPropagation();
        triggerHaptic('LIGHT');
        updateStorageStatusUI();
        pop.classList.toggle('open');
        return;
      }
      if (pop && pop.classList.contains('open') && !pop.contains(e.target)) {
        pop.classList.remove('open');
      }
    });
  }

  /* ------------------------------------------------------------------------
     7. Chart Helper (Chart.js + Offline Canvas Fallback)
     ------------------------------------------------------------------------ */
  function drawFallbackCanvasChart(canvas, labels, values) {
    if (!canvas) return;
    var ctx = canvas.getContext('2d');
    if (!ctx) return;
    var rect = canvas.parentElement.getBoundingClientRect();
    var w = Math.max(260, Math.round(rect.width || 320));
    var h = Math.max(120, Math.round(rect.height || 140));
    var dpr = window.devicePixelRatio || 1;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    var padL = 30, padR = 14, padT = 14, padB = 26;
    var plotW = w - padL - padR, plotH = h - padT - padB;
    var minV = 20, maxV = 100;

    ctx.strokeStyle = 'rgba(255,255,255,0.10)';
    ctx.lineWidth = 1;
    [40, 60, 80].forEach(function (v) {
      var y = padT + plotH * (1 - (v - minV) / (maxV - minV));
      ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(w - padR, y); ctx.stroke();
      ctx.fillStyle = 'rgba(242,244,248,0.52)';
      ctx.font = '10px -apple-system, sans-serif';
      ctx.fillText(String(v), 4, y + 3);
    });

    var pts = values.map(function (val, idx) {
      var x = padL + (plotW * idx) / Math.max(1, values.length - 1);
      var y = padT + plotH * (1 - Math.max(0, Math.min(1, (val - minV) / (maxV - minV))));
      return { x: x, y: y };
    });

    var grad = ctx.createLinearGradient(0, padT, 0, padT + plotH);
    grad.addColorStop(0, 'rgba(255, 255, 255, 0.28)');
    grad.addColorStop(1, 'rgba(255, 255, 255, 0.01)');

    ctx.beginPath();
    pts.forEach(function (p, i) { if (i === 0) ctx.moveTo(p.x, p.y); else ctx.lineTo(p.x, p.y); });
    ctx.lineTo(pts[pts.length - 1].x, padT + plotH);
    ctx.lineTo(pts[0].x, padT + plotH);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    ctx.beginPath();
    pts.forEach(function (p, i) { if (i === 0) ctx.moveTo(p.x, p.y); else ctx.lineTo(p.x, p.y); });
    ctx.strokeStyle = '#FFFFFF';
    ctx.lineWidth = 2.4;
    ctx.stroke();

    pts.forEach(function (p, i) {
      ctx.beginPath();
      ctx.arc(p.x, p.y, i === pts.length - 1 ? 4.5 : 3, 0, Math.PI * 2);
      ctx.fillStyle = '#FFFFFF';
      ctx.fill();
      ctx.fillStyle = 'rgba(242,244,248,0.74)';
      ctx.font = '10px -apple-system, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(labels[i], p.x, h - 6);
    });
  }

  function renderHorizonChart(canvasId, chartRefName, labels, values, highlightIdx) {
    var canvas = document.getElementById(canvasId);
    if (!canvas) return;
    if (typeof window.Chart !== 'function') {
      drawFallbackCanvasChart(canvas, labels, values);
      return;
    }

    var pointRadii = values.map(function (_, i) { return i === highlightIdx ? 6 : 3.5; });
    var pointColors = values.map(function (_, i) { return i === highlightIdx ? '#F5E6CC' : '#FFFFFF'; });
    var existing = chartRefName === 'sheet' ? sheetChart : simChart;

    if (existing) {
      existing.data.labels = labels;
      existing.data.datasets[0].data = values;
      existing.data.datasets[0].pointRadius = pointRadii;
      existing.data.datasets[0].pointBackgroundColor = pointColors;
      existing.update('none');
      return;
    }

    var ctx = canvas.getContext('2d');
    var inst = new window.Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          data: values,
          borderColor: 'rgba(255, 255, 255, 0.92)',
          backgroundColor: 'rgba(255, 255, 255, 0.14)',
          borderWidth: 2.5,
          fill: true,
          tension: 0.36,
          pointRadius: pointRadii,
          pointBackgroundColor: pointColors,
          pointBorderColor: '#FFFFFF',
          pointBorderWidth: 1.5
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: 'rgba(242,244,248,0.68)', font: { size: 11 } }, grid: { display: false } },
          y: { min: 20, max: 100, ticks: { color: 'rgba(242,244,248,0.55)', font: { size: 10.5 } }, grid: { color: 'rgba(255,255,255,0.08)' } }
        }
      }
    });
    if (chartRefName === 'sheet') sheetChart = inst;
    else simChart = inst;
  }

  function setHorizon(h) {
    if (HORIZONS.indexOf(h) === -1) return;
    activeHorizon = h;
    var idx = HORIZONS.indexOf(h);
    ['sheet-horizon-segs', 'sim-horizon-segs'].forEach(function (cid) {
      var wrap = document.getElementById(cid);
      if (!wrap) return;
      wrap.style.setProperty('--seg-idx', String(idx));
      wrap.querySelectorAll('.at-seg-btn').forEach(function (b) {
        b.classList.toggle('active', b.getAttribute('data-horizon') === h);
      });
    });
    updateMapSheetContent();
    renderMultiModalPanels();
    runSim();
  }

  function bindHorizonControls() {
    document.querySelectorAll('.at-seg-btn[data-horizon]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        triggerHaptic('LIGHT');
        setHorizon(btn.getAttribute('data-horizon'));
      });
    });
  }

  /* ------------------------------------------------------------------------
     8. Apple Maps-Style 3-Detent Draggable Bottom Sheet
     ------------------------------------------------------------------------ */
  var currentDetent = 'half';
  var sheetY = 0;

  function getDetentOffsets() {
    var vh = window.innerHeight || 844;
    var safeTop = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--safe-top')) || 0;
    return {
      full: Math.max(16, Math.round(safeTop + 14)),
      half: Math.round(vh * 0.44),
      collapsed: Math.max(Math.round(vh * 0.44) + 120, vh - 150)
    };
  }

  function snapSheetTo(detent, animate) {
    var sheet = document.getElementById('at-map-sheet');
    var mapView = document.getElementById('view-map');
    if (!sheet) return;
    var d = getDetentOffsets();
    currentDetent = detent;
    sheetY = d[detent] != null ? d[detent] : d.half;
    sheet.setAttribute('data-detent', detent);
    if (mapView) mapView.classList.toggle('sheet-full-active', detent === 'full');

    if (animate !== false) sheet.classList.add('animating');
    else sheet.classList.remove('animating');
    sheet.style.setProperty('--sheet-y', sheetY + 'px');

    var cyc = document.getElementById('at-sheet-cycle-btn');
    if (cyc) cyc.textContent = detent === 'full' ? 'Map' : (detent === 'collapsed' ? 'Details' : 'Expand');
  }

  function initBottomSheetDrag() {
    var sheet = document.getElementById('at-map-sheet');
    var handle = document.getElementById('at-sheet-drag-handle');
    var cyc = document.getElementById('at-sheet-cycle-btn');
    if (!sheet || !handle) return;

    var dragging = false, startY = 0, startSheetY = 0, lastY = 0, lastTime = 0, velocityY = 0;

    if (cyc) {
      cyc.addEventListener('pointerdown', function (e) { e.stopPropagation(); });
      cyc.addEventListener('click', function (e) {
        e.stopPropagation();
        triggerHaptic('LIGHT');
        snapSheetTo(currentDetent === 'half' ? 'full' : (currentDetent === 'full' ? 'collapsed' : 'half'), true);
      });
    }

    handle.addEventListener('pointerdown', function (e) {
      if (e.button && e.button !== 0) return;
      if (e.target && e.target.closest && e.target.closest('#at-sheet-cycle-btn')) return;
      try { handle.setPointerCapture(e.pointerId); } catch (err) {}
      var offsets = getDetentOffsets();
      dragging = true;
      startY = e.clientY;
      lastY = e.clientY;
      lastTime = performance.now();
      velocityY = 0;
      startSheetY = sheetY || offsets.half;
      sheet.classList.remove('animating');
    });

    handle.addEventListener('pointermove', function (e) {
      if (!dragging) return;
      if (e.cancelable) e.preventDefault();
      var now = performance.now();
      var dt = Math.max(8, now - lastTime);
      velocityY = (e.clientY - lastY) / dt;
      lastY = e.clientY;
      lastTime = now;

      var offsets = getDetentOffsets();
      var rawY = startSheetY + (e.clientY - startY);
      if (rawY < offsets.full) rawY = offsets.full - (offsets.full - rawY) * 0.25;
      if (rawY > offsets.collapsed) rawY = offsets.collapsed + (rawY - offsets.collapsed) * 0.25;
      sheetY = rawY;
      sheet.style.setProperty('--sheet-y', rawY.toFixed(1) + 'px');
    });

    function onEnd() {
      if (!dragging) return;
      dragging = false;
      var offsets = getDetentOffsets();
      var projected = sheetY + velocityY * 140;
      if (Math.abs(lastY - startY) < 6) {
        triggerHaptic('LIGHT');
        snapSheetTo(currentDetent === 'collapsed' ? 'half' : (currentDetent === 'half' ? 'full' : 'half'), true);
        return;
      }
      var best = 'half', bestDist = Infinity;
      ['full', 'half', 'collapsed'].forEach(function (k) {
        var dist = Math.abs(projected - offsets[k]);
        if (dist < bestDist) { bestDist = dist; best = k; }
      });
      triggerHaptic('MEDIUM');
      snapSheetTo(best, true);
    }

    handle.addEventListener('pointerup', onEnd);
    handle.addEventListener('pointercancel', onEnd);
    snapSheetTo('half', false);
    window.addEventListener('resize', function () {
      if (!dragging) snapSheetTo(currentDetent, false);
    }, { passive: true });
  }

  /* ------------------------------------------------------------------------
     9. Apple Maps Styles (Satellite, Explore, Dark) & District Markers
     ------------------------------------------------------------------------ */
  function initMap() {
    if (typeof window.L !== 'object' || !document.getElementById('map')) return;
    var BLANK_PX = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
    var tileOpts = {
      maxZoom: 19,
      maxNativeZoom: 18,
      keepBuffer: 8,
      updateWhenIdle: true,
      updateWhenZooming: false,
      crossOrigin: true,
      errorTileUrl: BLANK_PX
    };

    map = window.L.map('map', { zoomControl: false, attributionControl: false }).setView([17.85, 79.15], 7.2);
    window.__atMap = map;
    window.map = map;

    layers.satBase = window.L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', tileOpts);
    layers.satLabels = window.L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', Object.assign({ opacity: 0.96 }, tileOpts));
    layers.explore = window.L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}', tileOpts);
    layers.dark = window.L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', Object.assign({}, tileOpts, { maxNativeZoom: 16 }));
    layers.darkLabels = window.L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}', Object.assign({}, tileOpts, { maxNativeZoom: 16, opacity: 0.92 }));

    setMapStyle(activeMapStyle);

    districts.forEach(function (d) {
      var col = statusColor(d.status);
      var m = window.L.circleMarker([d.lat, d.lng], {
        radius: d.district === selected.district ? 11 : 8,
        fillColor: col,
        color: '#FFFFFF',
        weight: d.district === selected.district ? 2.5 : 1.5,
        fillOpacity: 0.94
      }).addTo(map);

      m.bindTooltip(d.district + ' • ' + d.xgb_wqi.toFixed(1), { direction: 'top', offset: [0, -6] });
      m.on('click', function () {
        triggerHaptic('LIGHT');
        selectDistrict(d.district, { fly: true, expandSheet: true });
      });
      markerRefs[d.district.toLowerCase()] = m;
    });

    var satBtn = document.getElementById('at-sat-toggle-btn');
    if (satBtn) {
      satBtn.addEventListener('click', function () {
        triggerHaptic('LIGHT');
        var next = MAP_STYLES[(MAP_STYLES.indexOf(activeMapStyle) + 1) % MAP_STYLES.length];
        setMapStyle(next);
        showToast('Apple Maps: ' + next.charAt(0).toUpperCase() + next.slice(1));
      });
    }

    var recenterBtn = document.getElementById('at-map-recenter');
    if (recenterBtn) {
      recenterBtn.addEventListener('click', function () {
        triggerHaptic('LIGHT');
        map.flyTo([17.85, 79.15], 7.2, { duration: 0.7 });
      });
    }

    var zIn = document.getElementById('at-map-zoom-in');
    var zOut = document.getElementById('at-map-zoom-out');
    if (zIn) zIn.addEventListener('click', function () { triggerHaptic('LIGHT'); map.zoomIn(); });
    if (zOut) zOut.addEventListener('click', function () { triggerHaptic('LIGHT'); map.zoomOut(); });
  }

  function highlightActiveMarker() {
    Object.keys(markerRefs).forEach(function (k) {
      var m = markerRefs[k];
      var isSel = selected && k === selected.district.toLowerCase();
      m.setStyle({ radius: isSel ? 12 : 8, weight: isSel ? 2.5 : 1.5 });
    });
  }

  /* ------------------------------------------------------------------------
     10. District Selection, Sheet Content, Overview, Districts & Simulator
     ------------------------------------------------------------------------ */
  function selectDistrict(nameOrRec, opts) {
    opts = opts || {};
    var target = typeof nameOrRec === 'string'
      ? districts.find(function (d) { return d.district.toLowerCase() === nameOrRec.toLowerCase(); })
      : nameOrRec;
    if (!target) return;
    selected = target;

    var sel = document.getElementById('simSelect');
    if (sel && sel.value !== selected.district) sel.value = selected.district;

    updateMapHudAndSheet();
    highlightActiveMarker();
    runSim();
    renderMultiModalPanels();

    if (opts.fly && map) {
      map.flyTo([selected.lat - 0.18, selected.lng], Math.max(map.getZoom(), 8.3), { duration: 0.65 });
    }
    if (opts.expandSheet && currentDetent === 'collapsed') {
      snapSheetTo('half', true);
    }
  }
  window.atSelectDistrict = selectDistrict;

  function updateMapHudAndSheet() {
    if (!selected) return;
    var col = statusColor(selected.status);
    var dot = document.getElementById('at-map-dot');
    var pName = document.getElementById('at-map-pill-name');
    var pWqi = document.getElementById('at-map-pill-wqi');
    if (dot) { dot.style.color = col; dot.style.background = col; }
    if (pName) pName.textContent = selected.district;
    if (pWqi) pWqi.textContent = selected.xgb_wqi.toFixed(1);
    updateMapSheetContent();
  }

  function updateMapSheetContent() {
    if (!selected) return;
    var d = selected;
    var col = statusColor(d.status);
    var hLabel = activeHorizon === '1y' ? '+1Y' : ('+' + activeHorizon.toUpperCase());

    var titleEl = document.getElementById('sheet-dist-name');
    var subEl = document.getElementById('sheet-dist-sub');
    if (titleEl) titleEl.textContent = d.district;
    if (subEl) {
      subEl.innerHTML = '<span style="color:' + col + ';font-weight:700">' + window.atEscapeHtml(d.status) +
        '</span><span>&bull;</span><span>' + window.atEscapeHtml(d.river_basin) + ' Basin</span>';
    }

    var wqiEl = document.getElementById('sheet-wqi');
    var turbEl = document.getElementById('sheet-turb');
    var gwEl = document.getElementById('sheet-gw');
    var resEl = document.getElementById('sheet-res');
    if (wqiEl) { wqiEl.textContent = d.xgb_wqi.toFixed(1); wqiEl.style.color = col; }
    if (turbEl) turbEl.textContent = d.turb.toFixed(2);
    if (gwEl) gwEl.textContent = d.gw_depth.toFixed(1) + 'm';
    if (resEl) resEl.textContent = d.res_pct.toFixed(0) + '%';

    var wqiMap = { '1m': d.lstm_1m_wqi, '2m': d.lstm_2m_wqi, '6m': d.lstm_6m_wqi, '1y': d.lstm_1y_wqi };
    var gwMap = { '1m': d.gw_1m, '2m': d.gw_2m, '6m': d.gw_6m, '1y': d.gw_1y };
    var resMap = { '1m': d.res_1m, '2m': d.res_2m, '6m': d.res_6m, '1y': d.res_1y };
    var rainMap = { '1m': d.rain_1m, '2m': d.rain_2m, '6m': d.rain_6m, '1y': d.rain_1y };

    var cTitle = document.getElementById('sheet-chart-title');
    var cVal = document.getElementById('sheet-chart-val');
    if (cTitle) cTitle.textContent = 'ML Forecast Trajectory (' + hLabel + ')';
    if (cVal) cVal.textContent = wqiMap[activeHorizon].toFixed(1) + ' / 100';

    var hIdx = HORIZONS.indexOf(activeHorizon) + 1;
    renderHorizonChart('sheetForecastChart', 'sheet', ['Now', '+1M', '+2M', '+6M', '+1Y'],
      [d.xgb_wqi, d.lstm_1m_wqi, d.lstm_2m_wqi, d.lstm_6m_wqi, d.lstm_1y_wqi], hIdx);

    var mmGrid = document.getElementById('sheet-mm-grid');
    if (mmGrid) {
      mmGrid.innerHTML =
        '<div class="at-mm-box"><div class="at-mm-k">Surface WQI (' + hLabel + ')</div><div class="at-mm-v tabular">' + wqiMap[activeHorizon].toFixed(1) + ' / 100</div><div class="at-mm-d tabular">Now: ' + d.xgb_wqi.toFixed(1) + '</div></div>' +
        '<div class="at-mm-box"><div class="at-mm-k">Groundwater (' + hLabel + ')</div><div class="at-mm-v tabular">' + gwMap[activeHorizon].toFixed(2) + ' m</div><div class="at-mm-d">' + window.atEscapeHtml(d.gw_status) + '</div></div>' +
        '<div class="at-mm-box"><div class="at-mm-k">Reservoir (' + hLabel + ')</div><div class="at-mm-v tabular">' + resMap[activeHorizon].toFixed(1) + '%</div><div class="at-mm-d tabular">Now: ' + d.res_pct.toFixed(1) + '%</div></div>' +
        '<div class="at-mm-box"><div class="at-mm-k">Rainfall (' + hLabel + ')</div><div class="at-mm-v tabular">' + rainMap[activeHorizon].toFixed(1) + ' mm</div><div class="at-mm-d tabular">SPI: ' + d.spi_6m.toFixed(2) + '</div></div>';
    }

    var mmTbl = document.getElementById('sheet-mm-table');
    if (mmTbl) {
      mmTbl.innerHTML =
        '<thead><tr><th>Metric</th><th>Now</th><th>+1M</th><th>+2M</th><th>+6M</th><th>+1Y</th></tr></thead>' +
        '<tbody class="tabular">' +
          '<tr><td>Water WQI</td><td>' + d.xgb_wqi.toFixed(1) + '</td><td>' + d.lstm_1m_wqi.toFixed(1) + '</td><td>' + d.lstm_2m_wqi.toFixed(1) + '</td><td>' + d.lstm_6m_wqi.toFixed(1) + '</td><td>' + d.lstm_1y_wqi.toFixed(1) + '</td></tr>' +
          '<tr><td>GW (mbgl)</td><td>' + d.gw_depth.toFixed(2) + '</td><td>' + d.gw_1m.toFixed(2) + '</td><td>' + d.gw_2m.toFixed(2) + '</td><td>' + d.gw_6m.toFixed(2) + '</td><td>' + d.gw_1y.toFixed(2) + '</td></tr>' +
          '<tr><td>Reservoir</td><td>' + d.res_pct.toFixed(1) + '%</td><td>' + d.res_1m.toFixed(1) + '%</td><td>' + d.res_2m.toFixed(1) + '%</td><td>' + d.res_6m.toFixed(1) + '%</td><td>' + d.res_1y.toFixed(1) + '%</td></tr>' +
          '<tr><td>Rainfall</td><td>' + d.rain.toFixed(1) + '</td><td>' + d.rain_1m.toFixed(1) + '</td><td>' + d.rain_2m.toFixed(1) + '</td><td>' + d.rain_6m.toFixed(1) + '</td><td>' + d.rain_1y.toFixed(1) + '</td></tr>' +
        '</tbody>';
    }

    var gwBox = document.getElementById('sheet-gw-box');
    if (gwBox) {
      var stressPct = Math.max(8, Math.min(100, Math.round((d.gw_depth / 18.0) * 100)));
      gwBox.innerHTML =
        '<div class="dash-sec-title"><span>Groundwater Aquifer</span><span class="tag ' + (d.gw_status === 'Safe' ? 'Normal' : 'High') + '">' + window.atEscapeHtml(d.gw_status) + '</span></div>' +
        '<div class="at-gw-grid">' +
          '<div class="at-gw-cell"><span class="at-gw-lbl">Depth</span><b class="at-gw-val tabular">' + d.gw_depth.toFixed(2) + ' m</b></div>' +
          '<div class="at-gw-cell"><span class="at-gw-lbl">Extraction</span><b class="at-gw-val tabular">' + d.gw_ext.toFixed(1) + '%</b></div>' +
          '<div class="at-gw-cell"><span class="at-gw-lbl">Recharge</span><b class="at-gw-val tabular">' + d.gw_rech.toFixed(1) + ' mm</b></div>' +
        '</div>' +
        '<div class="at-top-livebar" style="margin-top:10px;padding-top:8px;">' +
          '<div class="at-top-livebar-head"><span>Aquifer Depth Stress</span><b class="tabular">' + d.gw_depth.toFixed(2) + ' / 18.0 mbgl</b></div>' +
          '<div class="at-top-livebar-track"><div class="at-top-livebar-fill" style="width:' + stressPct + '%;background:linear-gradient(90deg,#30D158,#FF9F0A,#FF453A);"></div></div>' +
        '</div>';
    }

    var resBox = document.getElementById('sheet-res-box');
    if (resBox) {
      resBox.innerHTML =
        '<div class="dash-sec-title"><span>Reservoir Storage</span><span class="tag ' + (d.res_status === 'Normal' ? 'Normal' : 'Low') + '">' + window.atEscapeHtml(d.res_status) + '</span></div>' +
        '<p style="font-size:12.5px;color:var(--label-secondary);margin-bottom:8px;">' + window.atEscapeHtml(d.res_name) + '</p>' +
        '<div class="metrics-grid">' +
          '<div class="m-box"><small>Storage Fill</small><strong class="tabular">' + d.res_pct.toFixed(1) + '%</strong></div>' +
          '<div class="m-box"><small>Volume (TMC)</small><strong class="tabular">' + d.res_sto.toFixed(1) + ' / ' + d.res_cap.toFixed(1) + '</strong></div>' +
        '</div>';
    }

    renderRecommendationNodes('sheet-ai-rec', d, null);
  }

  /* ------------------------------------------------------------------------
     11. Navigation Dock & Scroll Auto-Minimize
     ------------------------------------------------------------------------ */
  var navTabs = [], tabRects = [], navLeft = 0, navWidth = 0, activeIdx = 2;
  var springX = 0, springVx = 0, springTargetX = 0, springW = 74, springVw = 0, springTargetW = 74;
  var animRaf = null, lastTs = 0, isDockDragging = false, suppressTabClickUntil = 0;

  function measureDock() {
    var nav = document.querySelector('nav.at-nav-pill');
    if (!nav) return;
    navTabs = Array.prototype.slice.call(nav.querySelectorAll('.tab'));
    var nr = nav.getBoundingClientRect();
    navLeft = nr.left;
    navWidth = nr.width;
    tabRects = navTabs.map(function (t) {
      var r = t.getBoundingClientRect();
      return { left: (r.left - navLeft), width: Math.max(48, r.width), cx: r.left + r.width * 0.5 };
    });
  }

  function stepLensSpring(ts) {
    var lens = document.getElementById('at-lg-tab-lens');
    if (!lens || isDockDragging) { animRaf = null; return; }
    if (!lastTs) lastTs = ts;
    var dt = Math.min(0.032, Math.max(0.002, (ts - lastTs) / 1000));
    lastTs = ts;

    var STIFF = 420, DAMP = 32;
    springVx += (STIFF * (springTargetX - springX) - DAMP * springVx) * dt;
    springX += springVx * dt;
    springVw += (STIFF * (springTargetW - springW) - DAMP * springVw) * dt;
    springW += springVw * dt;

    var stretch = Math.min(0.14, Math.abs(springVx) * 0.00015);
    lens.style.width = springW.toFixed(1) + 'px';
    lens.style.transform = 'translate3d(' + springX.toFixed(2) + 'px, 0, 0) scale(' + (1 + stretch).toFixed(3) + ', ' + (1 - stretch * 0.35).toFixed(3) + ')';

    if (Math.abs(springTargetX - springX) < 0.2 && Math.abs(springVx) < 0.8) {
      springX = springTargetX; springVx = 0;
      lens.style.width = springW.toFixed(1) + 'px';
      lens.style.transform = 'translate3d(' + springX.toFixed(1) + 'px, 0, 0) scale(1, 1)';
      animRaf = null; lastTs = 0;
      return;
    }
    animRaf = requestAnimationFrame(stepLensSpring);
  }

  function snapLens(idx, instant) {
    var lens = document.getElementById('at-lg-tab-lens');
    if (!lens) return;
    if (!tabRects.length) measureDock();
    if (!tabRects[idx]) return;
    activeIdx = idx;
    springTargetX = tabRects[idx].left;
    springTargetW = tabRects[idx].width;
    if (instant) {
      springX = springTargetX; springW = springTargetW; springVx = 0;
      lens.style.width = springW.toFixed(1) + 'px';
      lens.style.transform = 'translate3d(' + springX.toFixed(1) + 'px, 0, 0)';
    } else if (!animRaf) {
      lastTs = 0;
      animRaf = requestAnimationFrame(stepLensSpring);
    }
  }

  function switchTab(name, btn) {
    activeView = name;
    document.querySelectorAll('.view').forEach(function (v) { v.classList.remove('active'); });
    document.querySelectorAll('.tab').forEach(function (t) { t.classList.remove('active'); });
    var vEl = document.getElementById('view-' + name);
    if (vEl) vEl.classList.add('active');

    var targetBtn = btn || document.querySelector('.tab[data-view="' + name + '"]');
    if (targetBtn) {
      targetBtn.classList.add('active');
      var idx = navTabs.indexOf(targetBtn);
      if (idx >= 0) snapLens(idx, false);
    }

    var dock = document.getElementById('at-dock-wrap');
    if (dock) dock.classList.remove('dock-compact');
    if (name === 'map' && map) setTimeout(function () { map.invalidateSize({ animate: false }); }, 220);
    if (name === 'dash') syncDashboard();
    if (name === 'sim') { runSim(); renderMultiModalPanels(); }
    triggerHaptic('LIGHT');
  }
  window.switchTab = switchTab;

  function initFloatingDock() {
    var nav = document.querySelector('nav.at-nav-pill');
    var lens = document.getElementById('at-lg-tab-lens');
    if (!nav || !lens) return;
    measureDock();
    snapLens(2, true);

    navTabs.forEach(function (btn, idx) {
      btn.addEventListener('click', function (e) {
        if (performance.now() < suppressTabClickUntil && e.isTrusted) { e.preventDefault(); e.stopPropagation(); return; }
        switchTab(btn.getAttribute('data-view'), btn);
        snapLens(idx, false);
      });
    });

    var startX = 0, didMove = false, hoverIdx = -1;
    function startDrag(cx) {
      measureDock();
      if (animRaf) { cancelAnimationFrame(animRaf); animRaf = null; }
      isDockDragging = true; didMove = false; hoverIdx = -1; startX = cx;
    }
    function moveDrag(cx, e) {
      if (!isDockDragging) return;
      if (!didMove && Math.abs(cx - startX) > 6) didMove = true;
      if (!didMove) return;
      if (e && e.cancelable) e.preventDefault();
      var x = Math.max(4, Math.min(Math.max(4, navWidth - springW - 4), cx - navLeft - springW * 0.5));
      springX = x; springTargetX = x;
      lens.style.transform = 'translate3d(' + x.toFixed(1) + 'px, 0, 0) scale(1.06, 1.03)';
      var best = 0, bestD = Infinity;
      for (var i = 0; i < tabRects.length; i++) {
        var d = Math.abs(cx - tabRects[i].cx);
        if (d < bestD) { bestD = d; best = i; }
      }
      hoverIdx = best;
    }
    function endDrag() {
      if (!isDockDragging) return;
      isDockDragging = false;
      if (didMove) {
        suppressTabClickUntil = performance.now() + 260;
        if (hoverIdx >= 0 && navTabs[hoverIdx] && hoverIdx !== activeIdx) {
          switchTab(navTabs[hoverIdx].getAttribute('data-view'), navTabs[hoverIdx]);
        } else {
          snapLens(activeIdx, false);
        }
      }
    }

    nav.addEventListener('touchstart', function (e) { if (e.touches.length) startDrag(e.touches[0].clientX); }, { passive: true });
    nav.addEventListener('touchmove', function (e) { if (e.touches.length) moveDrag(e.touches[0].clientX, e); }, { passive: false });
    nav.addEventListener('touchend', endDrag, { passive: true });
    nav.addEventListener('mousedown', function (e) { if (e.button === 0) startDrag(e.clientX); });
    window.addEventListener('mousemove', function (e) { if (isDockDragging) moveDrag(e.clientX, e); });
    window.addEventListener('mouseup', endDrag);
    window.addEventListener('resize', function () { measureDock(); snapLens(activeIdx, true); }, { passive: true });

    var lastScrollY = {}, dock = document.getElementById('at-dock-wrap');
    document.querySelectorAll('.view:not(#view-map), #at-sheet-scroll').forEach(function (sc) {
      var id = sc.id || 'sc';
      lastScrollY[id] = 0;
      sc.addEventListener('scroll', function () {
        if (!dock) return;
        var cur = sc.scrollTop, prev = lastScrollY[id] || 0;
        if (cur > 40 && cur - prev > 10) dock.classList.add('dock-compact');
        else if (cur <= 20 || prev - cur > 10) dock.classList.remove('dock-compact');
        lastScrollY[id] = cur;
      }, { passive: true });
    });
  }

  /* ------------------------------------------------------------------------
     12. Overview, Districts List & AI Twin Simulator
     ------------------------------------------------------------------------ */
  function syncDashboard() {
    var total = districts.length;
    if (!total) return;
    var safe = 0, mod = 0, high = 0, sumWqi = 0;
    districts.forEach(function (d) {
      sumWqi += d.xgb_wqi;
      if (d.status === 'High Turbidity') high++;
      else if (d.status === 'Low Water') mod++;
      else safe++;
    });
    var avg = sumWqi / total;
    var cur = isDemoOn ? districts[demoIdx % total] : null;
    var ringPct = cur ? cur.xgb_wqi : avg;
    var ringCol = ringPct >= 70 ? '#30D158' : (ringPct >= 55 ? '#FF9F0A' : '#FF453A');

    var sc = document.getElementById('dash-score');
    var lbl = document.getElementById('dash-ring-lbl');
    var arc = document.getElementById('dash-arc');
    if (sc) { sc.textContent = ringPct.toFixed(1) + '%'; sc.style.color = '#FFFFFF'; }
    if (lbl) lbl.textContent = cur ? cur.district.slice(0, 9).toUpperCase() : 'HEALTH';
    if (arc) {
      arc.setAttribute('stroke', ringCol);
      arc.setAttribute('stroke-dashoffset', (219.9 * (1 - ringPct / 100)).toFixed(1));
    }

    var bl = document.getElementById('at-bar-left');
    var bp = document.getElementById('at-bar-pct');
    var bf = document.getElementById('at-bar-fill');
    if (bl) bl.textContent = cur ? ('Live Stream: ' + cur.district) : 'Telangana Avg (' + total + ' Districts)';
    if (bp) { bp.textContent = ringPct.toFixed(1) + '%'; bp.style.color = ringCol; }
    if (bf) { bf.style.width = ringPct.toFixed(1) + '%'; bf.style.background = ringCol; }

    document.getElementById('dash-kpi-wqi').textContent = avg.toFixed(1);
    document.getElementById('dash-kpi-safe').textContent = String(safe);
    document.getElementById('dash-kpi-mod').textContent = String(mod);
    document.getElementById('dash-kpi-high').textContent = String(high);

    document.getElementById('dash-total').textContent = total + ' Districts';
    document.getElementById('bar-safe').style.width = (safe / total * 100) + '%';
    document.getElementById('bar-mod').style.width = (mod / total * 100) + '%';
    document.getElementById('bar-crit').style.width = (high / total * 100) + '%';
    document.getElementById('leg-safe').textContent = 'Normal: ' + safe;
    document.getElementById('leg-mod').textContent = 'Low Water: ' + mod;
    document.getElementById('leg-crit').textContent = 'High Turb: ' + high;

    // Render 33-District State Optimization Insights
    var optBox = document.getElementById('dash-ai-insights');
    if (optBox) {
      var opt = getStateOptimizationSummary();
      var urgentNames = opt.topUrgent.map(function (x) { return x.district + ' (' + x.xgb_wqi.toFixed(1) + ')'; }).join(', ');
      var bestNames = opt.bestResilient.map(function (x) { return x.district + ' (' + x.xgb_wqi.toFixed(1) + ')'; }).join(', ');
      optBox.innerHTML =
        '<div class="ai-rec-item">' +
          '<div class="ai-rec-top"><span class="ai-rec-tag">Priority Focus</span><span class="ai-rec-gain tabular">Avg ' + opt.avgWqi.toFixed(1) + ' WQI</span></div>' +
          '<div class="ai-rec-body">Top intervention targets: <b>' + window.atEscapeHtml(urgentNames) + '</b>. Focus on turbidity filtration, groundwater recharge, and reservoir balancing.</div>' +
        '</div>' +
        '<div class="ai-rec-bench">Top Basin Benchmarks: ' + window.atEscapeHtml(bestNames) + '</div>';
    }

    var wb = document.getElementById('dash-watch');
    if (wb) {
      var sorted = districts.slice().sort(function (a, b) { return a.xgb_wqi - b.xgb_wqi; });
      wb.innerHTML = '';
      sorted.slice(0, 3).forEach(function (d) {
        var row = document.createElement('div');
        row.className = 'dash-item';
        row.innerHTML =
          '<div><b>' + window.atEscapeHtml(d.district) + '</b>' +
          '<small class="tabular">WQI ' + d.xgb_wqi.toFixed(1) + ' &bull; Turb ' + d.turb.toFixed(2) + ' &bull; Water ' + d.water.toFixed(2) + '%</small></div>' +
          '<span class="dash-badge ' + statusClass(d.status) + '">' + window.atEscapeHtml(d.status) + '</span>';
        row.addEventListener('click', function () {
          selectDistrict(d, { fly: true, expandSheet: true });
          switchTab('map');
        });
        wb.appendChild(row);
      });
    }

    renderRealtimeFeed(avg);
  }

  function renderRealtimeFeed(avg) {
    var listEl = document.getElementById('at-rt-list');
    var pctEl = document.getElementById('at-rt-ticker-pct');
    var subEl = document.getElementById('at-rt-sub');
    if (!listEl) return;
    if (pctEl) pctEl.textContent = (isDemoOn ? districts[demoIdx % districts.length].xgb_wqi : avg).toFixed(1) + '%';
    if (subEl) subEl.textContent = isDemoOn
      ? 'Live Demo playing: ' + districts[demoIdx % districts.length].district
      : 'All ' + districts.length + ' Districts • Tap any district to focus on Apple Maps';

    listEl.innerHTML = '';
    districts.forEach(function (d, i) {
      var isAct = (isDemoOn && i === demoIdx % districts.length) || (!isDemoOn && selected && d.district === selected.district);
      var col = d.xgb_wqi >= 70 ? '#30D158' : (d.xgb_wqi >= 55 ? '#FF9F0A' : '#FF453A');
      var row = document.createElement('div');
      row.className = 'at-rt-row' + (isAct ? ' active' : '');
      row.innerHTML =
        '<div class="at-rt-row-head"><span>' + (i + 1) + '. ' + window.atEscapeHtml(d.district) + '</span><span class="tabular" style="color:' + col + '">' + d.xgb_wqi.toFixed(1) + '%</span></div>' +
        '<div class="at-rt-meta tabular"><span>Water: ' + d.water.toFixed(2) + '%</span><span>GW Use: ' + d.gw_ext.toFixed(1) + '%</span><span>+1M: ' + d.lstm_1m_wqi.toFixed(1) + '%</span></div>' +
        '<div class="at-rt-bar"><div class="at-rt-fill" style="width:' + Math.min(100, d.xgb_wqi) + '%;background:' + col + ';"></div></div>';
      row.addEventListener('click', function () {
        selectDistrict(d, { fly: true, expandSheet: true });
        switchTab('map');
      });
      listEl.appendChild(row);
    });
  }

  function initDemoToggle() {
    var btn = document.getElementById('at-demo-toggle');
    if (!btn) return;
    btn.addEventListener('click', function () {
      triggerHaptic('LIGHT');
      isDemoOn = !isDemoOn;
      btn.classList.toggle('on', isDemoOn);
      if (isDemoOn) {
        demoTimer = setInterval(function () {
          demoIdx = (demoIdx + 1) % districts.length;
          syncDashboard();
        }, 2000);
      } else if (demoTimer) {
        clearInterval(demoTimer);
        demoTimer = null;
      }
      syncDashboard();
    });
  }

  function renderList() {
    var q = (document.getElementById('searchBox') ? document.getElementById('searchBox').value : '').toLowerCase();
    var st = document.getElementById('statusFilter') ? document.getElementById('statusFilter').value : 'ALL';
    var filtered = districts.filter(function (d) {
      return d.district.toLowerCase().indexOf(q) !== -1 && (st === 'ALL' || d.status === st);
    });
    var box = document.getElementById('districtList');
    if (!box) return;
    box.innerHTML = '';
    filtered.forEach(function (d) {
      var el = document.createElement('div');
      el.className = 'd-card ios-row';
      el.innerHTML =
        '<div>' +
          '<div class="d-name">' + window.atEscapeHtml(d.district) + '</div>' +
          '<div class="d-meta tabular">WQI: <b>' + d.xgb_wqi.toFixed(1) + '</b> &bull; Turb: ' + d.turb.toFixed(2) + ' &bull; Water: ' + d.water.toFixed(2) + '%</div>' +
        '</div>' +
        '<span class="tag ' + statusClass(d.status) + '">' + window.atEscapeHtml(d.status) + '</span>';
      el.addEventListener('click', function () {
        triggerHaptic('LIGHT');
        selectDistrict(d, { fly: true, expandSheet: true });
        switchTab('map');
      });
      box.appendChild(el);
    });
  }

  function resetSliders() {
    document.getElementById('rainSlider').value = 0;
    document.getElementById('tempSlider').value = 0;
    document.getElementById('pollSlider').value = 0;
    runSim();
    triggerHaptic('LIGHT');
  }
  window.resetSliders = resetSliders;

  function applyOptimalPlan() {
    if (!selected) return;
    var rec = buildRecommendations(selected, null);
    document.getElementById('rainSlider').value = rec.optimalDelta.rain;
    document.getElementById('tempSlider').value = rec.optimalDelta.temp;
    document.getElementById('pollSlider').value = rec.optimalDelta.poll;
    runSim();
    triggerHaptic('MEDIUM');
    showToast('Applied optimal AI intervention for ' + selected.district);
  }

  function runSim() {
    if (!selected) return;
    var rEl = document.getElementById('rainSlider');
    var tEl = document.getElementById('tempSlider');
    var pEl = document.getElementById('pollSlider');
    if (!rEl || !tEl || !pEl) return;

    var rain = Number(rEl.value), temp = Number(tEl.value), poll = Number(pEl.value);
    document.getElementById('rainVal').textContent = (rain > 0 ? '+' : '') + rain + '%';
    document.getElementById('tempVal').textContent = (temp > 0 ? '+' : '') + temp + '°C';
    document.getElementById('pollVal').textContent = (poll > 0 ? '+' : '') + poll + '%';

    var waterFactor = 1.0 + (rain * 0.009) - (temp * 0.045);
    var simWater = Number(Math.max(0.1, selected.water * waterFactor).toFixed(2));
    var simTurb = Number(Math.max(0.5, selected.turb + Math.max(0, rain) * 0.0018 + poll * 0.0045 + Math.max(0, temp) * 0.015).toFixed(3));
    var simNdwi = Number(Math.max(-1, Math.min(1, selected.ndwi + (simWater - selected.water) * 0.04)).toFixed(4));
    var ai = computeAI(simTurb, simWater, simNdwi);

    document.getElementById('simWqi').textContent = ai.wqi.toFixed(1) + ' / 100';
    var riskEl = document.getElementById('simRisk');
    riskEl.textContent = ai.risk === 'Low Risk' ? 'Safe' : (ai.risk === 'Moderate Risk' ? 'Medium' : 'High Turbidity');
    riskEl.style.color = ai.risk === 'High Risk' ? 'var(--ios-coral)' : (ai.risk === 'Moderate Risk' ? 'var(--ios-amber)' : 'var(--ios-mint)');
    document.getElementById('simTurb').textContent = simTurb.toFixed(3);
    document.getElementById('simWater').textContent = simWater.toFixed(2) + '%';

    renderRecommendationNodes('simAction', selected, { turb: simTurb, water: simWater, wqi: ai.wqi });

    var deltaShift = ai.wqi - selected.wqi;
    var pts = [
      ai.wqi,
      Number(Math.max(15, Math.min(98, selected.lstm_1m_wqi + deltaShift * 0.6)).toFixed(1)),
      Number(Math.max(15, Math.min(98, selected.lstm_2m_wqi + deltaShift * 0.65)).toFixed(1)),
      Number(Math.max(15, Math.min(98, selected.lstm_6m_wqi + deltaShift * 0.7)).toFixed(1)),
      Number(Math.max(15, Math.min(98, selected.lstm_1y_wqi + deltaShift * 0.75)).toFixed(1))
    ];
    renderHorizonChart('forecastChart', 'sim', ['Now', '+1M', '+2M', '+6M', '+1Y'], pts, HORIZONS.indexOf(activeHorizon) + 1);
  }
  window.runSim = runSim;

  function renderMultiModalPanels() {
    if (!selected) return;
    var d = selected;
    var hLabel = activeHorizon === '1y' ? '+1Y' : ('+' + activeHorizon.toUpperCase());

    var mlEl = document.getElementById('at-ml-panel');
    if (mlEl) {
      mlEl.innerHTML =
        '<div class="dash-sec-title"><span>XGBoost + LSTM Engine (' + window.atEscapeHtml(d.district) + ')</span><span class="tag Normal">R2 0.94 / 0.89</span></div>' +
        '<div class="at-gw-grid">' +
          '<div class="at-gw-cell"><span class="at-gw-lbl">Current WQI</span><b class="at-gw-val tabular">' + d.xgb_wqi.toFixed(1) + '</b></div>' +
          '<div class="at-gw-cell"><span class="at-gw-lbl">LSTM +1M</span><b class="at-gw-val tabular">' + d.lstm_1m_wqi.toFixed(1) + '</b></div>' +
          '<div class="at-gw-cell"><span class="at-gw-lbl">LSTM +1Y</span><b class="at-gw-val tabular">' + d.lstm_1y_wqi.toFixed(1) + '</b></div>' +
        '</div>';
    }

    var mmEl = document.getElementById('at-mm3y-card');
    if (mmEl) {
      var wqiMap = { '1m': d.lstm_1m_wqi, '2m': d.lstm_2m_wqi, '6m': d.lstm_6m_wqi, '1y': d.lstm_1y_wqi };
      var gwMap = { '1m': d.gw_1m, '2m': d.gw_2m, '6m': d.gw_6m, '1y': d.gw_1y };
      var resMap = { '1m': d.res_1m, '2m': d.res_2m, '6m': d.res_6m, '1y': d.res_1y };
      var rainMap = { '1m': d.rain_1m, '2m': d.rain_2m, '6m': d.rain_6m, '1y': d.rain_1y };

      mmEl.innerHTML =
        '<div class="dash-sec-title"><span>3-Year AI Forecast — ' + window.atEscapeHtml(d.district) + '</span><span class="tag Normal">36M Trained</span></div>' +
        '<div class="at-mm-grid">' +
          '<div class="at-mm-box"><div class="at-mm-k">Surface WQI (' + hLabel + ')</div><div class="at-mm-v tabular">' + wqiMap[activeHorizon].toFixed(1) + ' / 100</div><div class="at-mm-d tabular">Now: ' + d.xgb_wqi.toFixed(1) + '</div></div>' +
          '<div class="at-mm-box"><div class="at-mm-k">Groundwater (' + hLabel + ')</div><div class="at-mm-v tabular">' + gwMap[activeHorizon].toFixed(2) + ' mbgl</div><div class="at-mm-d">' + window.atEscapeHtml(d.gw_status) + '</div></div>' +
          '<div class="at-mm-box"><div class="at-mm-k">Reservoir Fill (' + hLabel + ')</div><div class="at-mm-v tabular">' + resMap[activeHorizon].toFixed(1) + '%</div><div class="at-mm-d">' + window.atEscapeHtml(d.res_name) + '</div></div>' +
          '<div class="at-mm-box"><div class="at-mm-k">Rainfall (' + hLabel + ')</div><div class="at-mm-v tabular">' + rainMap[activeHorizon].toFixed(1) + ' mm</div><div class="at-mm-d tabular">6M Cum: ' + d.rain_6m_cum.toFixed(0) + ' mm</div></div>' +
        '</div>' +
        '<table class="at-mm-table"><thead><tr><th>Metric</th><th>Now</th><th>+1M</th><th>+2M</th><th>+6M</th><th>+1Y</th></tr></thead>' +
        '<tbody class="tabular">' +
          '<tr><td>Water WQI</td><td>' + d.xgb_wqi.toFixed(1) + '</td><td>' + d.lstm_1m_wqi.toFixed(1) + '</td><td>' + d.lstm_2m_wqi.toFixed(1) + '</td><td>' + d.lstm_6m_wqi.toFixed(1) + '</td><td>' + d.lstm_1y_wqi.toFixed(1) + '</td></tr>' +
          '<tr><td>GW (mbgl)</td><td>' + d.gw_depth.toFixed(2) + '</td><td>' + d.gw_1m.toFixed(2) + '</td><td>' + d.gw_2m.toFixed(2) + '</td><td>' + d.gw_6m.toFixed(2) + '</td><td>' + d.gw_1y.toFixed(2) + '</td></tr>' +
          '<tr><td>Reservoir</td><td>' + d.res_pct.toFixed(1) + '%</td><td>' + d.res_1m.toFixed(1) + '%</td><td>' + d.res_2m.toFixed(1) + '%</td><td>' + d.res_6m.toFixed(1) + '%</td><td>' + d.res_1y.toFixed(1) + '%</td></tr>' +
          '<tr><td>Rainfall</td><td>' + d.rain.toFixed(1) + '</td><td>' + d.rain_1m.toFixed(1) + '</td><td>' + d.rain_2m.toFixed(1) + '</td><td>' + d.rain_6m.toFixed(1) + '</td><td>' + d.rain_1y.toFixed(1) + '</td></tr>' +
        '</tbody></table>';
    }

    var gwEl = document.getElementById('at-gw-card');
    if (gwEl) {
      var stressPct = Math.max(8, Math.min(100, Math.round((d.gw_depth / 18.0) * 100)));
      gwEl.innerHTML =
        '<div class="dash-sec-title"><span>Groundwater Aquifer (' + window.atEscapeHtml(d.district) + ')</span><span class="tag ' + (d.gw_status === 'Safe' ? 'Normal' : 'High') + '">' + window.atEscapeHtml(d.gw_status) + '</span></div>' +
        '<div class="at-gw-grid">' +
          '<div class="at-gw-cell"><span class="at-gw-lbl">Depth</span><b class="at-gw-val tabular">' + d.gw_depth.toFixed(2) + ' m</b></div>' +
          '<div class="at-gw-cell"><span class="at-gw-lbl">Extraction</span><b class="at-gw-val tabular">' + d.gw_ext.toFixed(1) + '%</b></div>' +
          '<div class="at-gw-cell"><span class="at-gw-lbl">Recharge</span><b class="at-gw-val tabular">' + d.gw_rech.toFixed(1) + ' mm</b></div>' +
        '</div>' +
        '<div class="at-top-livebar" style="margin-top:10px;padding-top:8px;">' +
          '<div class="at-top-livebar-head"><span>Aquifer Depth Stress</span><b class="tabular">' + d.gw_depth.toFixed(2) + ' / 18.0 mbgl</b></div>' +
          '<div class="at-top-livebar-track"><div class="at-top-livebar-fill" style="width:' + stressPct + '%;background:linear-gradient(90deg,#30D158,#FF9F0A,#FF453A);"></div></div>' +
        '</div>';
    }
  }

  /* ------------------------------------------------------------------------
     13. CSV Data Collection Import, Deduplication & Merge into 33 Districts
     ------------------------------------------------------------------------ */
  function parseAndMergeCsv(csvText) {
    var lines = String(csvText || '').trim().split(/\r?\n/).filter(Boolean);
    if (lines.length < 2) return { error: 'CSV must contain a header row and at least one data row.' };
    var headers = lines[0].split(',').map(function (h) { return h.trim().toLowerCase().replace(/^"|"$/g, ''); });
    var idxDist = headers.indexOf('district');
    var idxDate = headers.indexOf('date');
    if (idxDist === -1) return { error: 'CSV must include a "district" column.' };

    var existing = loadMergedOverrides();
    var seenKeys = {};
    existing.forEach(function (r) {
      seenKeys[(normDistrictKey(r.district) + '::' + String(r.date || '')).trim()] = true;
    });

    var originalRows = lines.length - 1;
    var duplicatesRemoved = 0;
    var mergedNew = [];

    for (var i = 1; i < lines.length; i++) {
      var cols = lines[i].split(',').map(function (c) { return c.trim().replace(/^"|"$/g, ''); });
      var dist = cols[idxDist];
      if (!dist) continue;
      var dateVal = idxDate !== -1 ? (cols[idxDate] || 'latest') : 'latest';
      var key = normDistrictKey(dist) + '::' + dateVal;
      if (seenKeys[key]) {
        duplicatesRemoved++;
        continue;
      }
      seenKeys[key] = true;
      var rec = { district: dist, date: dateVal };
      headers.forEach(function (h, ci) {
        if (ci === idxDist || ci === idxDate || !cols[ci]) return;
        var v = Number(cols[ci]);
        rec[h] = isFinite(v) ? v : cols[ci];
      });
      mergedNew.push(rec);
    }

    var combined = existing.concat(mergedNew);
    try { localStorage.setItem(MERGED_STORAGE_KEY, JSON.stringify(combined)); } catch (e) {}
    vaultPut('merged_csv_records', combined);

    // Rebuild live districts and refresh every view + AI Recommendation
    var curName = selected ? selected.district : 'Hyderabad';
    districts = buildDistrictList();
    selected = districts.find(function (d) { return d.district.toLowerCase() === curName.toLowerCase(); }) || districts[0];
    refreshAllStatsAndViews();

    return {
      originalRows: originalRows,
      duplicatesRemoved: duplicatesRemoved,
      addedRows: mergedNew.length,
      totalStored: combined.length
    };
  }
  window.atMergeCsvText = parseAndMergeCsv;

  function refreshAllStatsAndViews() {
    var sel = document.getElementById('simSelect');
    if (sel && selected) sel.value = selected.district;
    var avg = districts.length ? (districts.reduce(function (a, b) { return a + b.xgb_wqi; }, 0) / districts.length).toFixed(1) : '-';
    document.getElementById('avgWqi').textContent = avg;
    document.getElementById('normalCount').textContent = districts.filter(function (d) { return d.status === 'Normal'; }).length;
    document.getElementById('highCount').textContent = districts.filter(function (d) { return d.status === 'High Turbidity'; }).length;
    document.getElementById('lowCount').textContent = districts.filter(function (d) { return d.status === 'Low Water'; }).length;

    var stressedCount = districts.filter(function (d) { return d.status !== 'Normal'; }).length;
    document.querySelectorAll('[data-alert-badge="1"]').forEach(function (el) {
      el.textContent = String(stressedCount);
      el.style.display = stressedCount ? 'flex' : 'none';
    });

    renderList();
    updateMapHudAndSheet();
    syncDashboard();
    runSim();
    renderMultiModalPanels();
  }

  function openDataImportSheet() {
    triggerHaptic('LIGHT');
    var stored = loadMergedOverrides();
    var html =
      '<div class="ios-card">' +
        '<div style="font-size:13px;font-weight:700;margin-bottom:6px;">Merge &amp; Deduplicate Data Collection</div>' +
        '<p style="font-size:12px;color:var(--label-secondary);line-height:1.45;">Upload a CSV file with <code>district, date, rainfall_mm, groundwater_level_m, reservoir_capacity_percent, turbidity_index</code>. Duplicates matching <b>district + date</b> are removed automatically and fed into the AI Recommendations engine.</p>' +
        '<input id="at-csv-file" type="file" accept=".csv,text/csv" style="margin-top:10px;width:100%;font-size:12.5px;color:#fff;" />' +
      '</div>' +
      '<div class="ios-card">' +
        '<div class="dash-sec-title" style="margin-bottom:6px;"><span>Or Paste CSV Rows</span><button type="button" id="at-csv-sample-btn" style="background:none;border:none;color:var(--ios-aqua);font-size:11.5px;font-weight:600;">Load Sample CSV</button></div>' +
        '<textarea id="at-csv-paste" rows="4" placeholder="district,date,rainfall_mm,groundwater_level_m,reservoir_capacity_percent,turbidity_index&#10;Hyderabad,2026-11-28,34.5,9.4,72,1.02" style="width:100%;border-radius:14px;border:1px solid rgba(255,255,255,0.18);background:rgba(255,255,255,0.06);color:#fff;padding:10px;font-size:12px;outline:none;"></textarea>' +
      '</div>' +
      '<div id="at-csv-result" class="ios-card" style="display:none;"></div>' +
      '<div class="at-sheet-actions">' +
        '<button type="button" class="at-btn-ios-primary lg-press" id="at-csv-merge-btn">Merge &amp; Run AI</button>' +
        '<button type="button" class="at-btn-ios-secondary lg-press" id="at-csv-clear-btn">Reset Merged (' + stored.length + ')</button>' +
      '</div>';

    openSystemSheet('Data Collection & AI Merge', 'Auto-Deduplicate • Persistent Vault', html);

    var fileInp = document.getElementById('at-csv-file');
    var pasteEl = document.getElementById('at-csv-paste');
    var sampleBtn = document.getElementById('at-csv-sample-btn');
    if (sampleBtn) {
      sampleBtn.addEventListener('click', function () {
        pasteEl.value =
          'district,date,rainfall_mm,groundwater_level_m,reservoir_capacity_percent,turbidity_index\n' +
          'Hyderabad,2026-11-28,38.0,9.2,74,0.98\n' +
          'Hyderabad,2026-11-28,38.0,9.2,74,0.98\n' +
          'Khammam,2026-11-28,52.4,6.4,68,0.89';
        triggerHaptic('LIGHT');
      });
    }
    fileInp.addEventListener('change', function () {
      var f = fileInp.files && fileInp.files[0];
      if (!f) return;
      var reader = new FileReader();
      reader.onload = function (ev) { pasteEl.value = ev.target.result || ''; };
      reader.readAsText(f);
    });

    document.getElementById('at-csv-merge-btn').addEventListener('click', function () {
      var res = parseAndMergeCsv(pasteEl.value);
      var out = document.getElementById('at-csv-result');
      out.style.display = 'block';
      if (res.error) {
        out.innerHTML = '<span style="color:var(--ios-coral);font-weight:600;">' + window.atEscapeHtml(res.error) + '</span>';
        return;
      }
      triggerHaptic('MEDIUM');
      out.innerHTML =
        '<div style="color:var(--ios-mint);font-weight:700;margin-bottom:4px;">Merged &amp; AI Updated</div>' +
        '<div class="tabular" style="font-size:12px;color:var(--label-secondary);">Original rows: <b>' + res.originalRows + '</b> &bull; Duplicates removed: <b>' + res.duplicatesRemoved + '</b> &bull; Added: <b>' + res.addedRows + '</b> (Total stored: ' + res.totalStored + ')</div>';
      var clrBtn = document.getElementById('at-csv-clear-btn');
      if (clrBtn) clrBtn.textContent = 'Reset Merged (' + res.totalStored + ')';
      showToast('Merged ' + res.addedRows + ' rows into AI');
    });

    document.getElementById('at-csv-clear-btn').addEventListener('click', function () {
      var curName = selected ? selected.district : 'Hyderabad';
      localStorage.removeItem(MERGED_STORAGE_KEY);
      vaultPut('merged_csv_records', []);
      districts = buildDistrictList();
      selected = districts.find(function (d) { return d.district.toLowerCase() === curName.toLowerCase(); }) || districts[0];
      refreshAllStatsAndViews();
      showToast('Restored baseline 33-district dataset');
      closeSystemSheet();
    });
  }

  /* ------------------------------------------------------------------------
     14. System Sheets: District Picker, Alerts, Report
     ------------------------------------------------------------------------ */
  function openSystemSheet(title, subtitle, bodyHtml) {
    var bd = document.getElementById('at-backdrop');
    var sh = document.getElementById('at-sheet');
    if (!bd || !sh) return;
    sh.innerHTML =
      '<div class="at-modal-head">' +
        '<div class="at-grabber" aria-hidden="true"></div>' +
        '<div class="at-modal-head-row">' +
          '<div><div class="at-modal-title">' + window.atEscapeHtml(title) + '</div>' +
          (subtitle ? '<div class="at-modal-sub">' + window.atEscapeHtml(subtitle) + '</div>' : '') + '</div>' +
          '<button type="button" class="at-modal-close lg-press" id="at-sh-close">Done</button>' +
        '</div>' +
      '</div>' +
      '<div class="at-modal-body">' + bodyHtml + '</div>';
    bd.classList.add('open');
    bd.setAttribute('aria-hidden', 'false');
    var cBtn = document.getElementById('at-sh-close');
    if (cBtn) cBtn.addEventListener('click', closeSystemSheet);
  }

  function closeSystemSheet() {
    var bd = document.getElementById('at-backdrop');
    if (!bd) return;
    bd.classList.remove('open');
    bd.setAttribute('aria-hidden', 'true');
  }

  function openDistrictPicker() {
    triggerHaptic('LIGHT');
    var rows = districts.map(function (d) {
      var act = selected && d.district === selected.district;
      var col = statusColor(d.status);
      return '<button type="button" class="at-picker-row' + (act ? ' active' : '') + '" data-pick-dist="' + window.atEscapeHtml(d.district) + '">' +
        '<span>' + window.atEscapeHtml(d.district) + '</span>' +
        '<span class="tabular" style="font-size:12.5px;color:' + col + ';font-weight:700;">' + d.xgb_wqi.toFixed(1) + '</span>' +
      '</button>';
    }).join('');
    openSystemSheet('Select District', '33 Telangana Digital Twins', rows);

    document.querySelectorAll('[data-pick-dist]').forEach(function (row) {
      row.addEventListener('click', function () {
        triggerHaptic('LIGHT');
        selectDistrict(row.getAttribute('data-pick-dist'), { fly: activeView === 'map', expandSheet: true });
        closeSystemSheet();
      });
    });
  }

  function openAlertsSheet() {
    triggerHaptic('LIGHT');
    var stressed = districts.filter(function (d) { return d.status !== 'Normal'; })
      .sort(function (a, b) { return a.xgb_wqi - b.xgb_wqi; });
    var html = stressed.length ? stressed.map(function (d) {
      var col = statusColor(d.status);
      return '<div class="ios-row" data-alert-dist="' + window.atEscapeHtml(d.district) + '">' +
        '<div><div class="d-name">' + window.atEscapeHtml(d.district) + '</div>' +
        '<div class="d-meta tabular">WQI ' + d.xgb_wqi.toFixed(1) + '/100 &bull; Turb ' + d.turb.toFixed(2) + ' &bull; GW ' + d.gw_depth.toFixed(1) + 'm</div></div>' +
        '<span class="tag" style="background:rgba(255,255,255,0.08);color:' + col + '">' + window.atEscapeHtml(d.status) + '</span>' +
      '</div>';
    }).join('') : '<div class="ios-card">All 33 Telangana districts are within normal thresholds.</div>';

    openSystemSheet('Water Risk Alerts (' + stressed.length + ')', 'Sentinel-2 & Groundwater Watchlist', html);
    document.querySelectorAll('[data-alert-dist]').forEach(function (el) {
      el.addEventListener('click', function () {
        selectDistrict(el.getAttribute('data-alert-dist'), { fly: true, expandSheet: true });
        closeSystemSheet();
        switchTab('map');
      });
    });
  }

  function openReportSheet() {
    triggerHaptic('LIGHT');
    var safe = districts.filter(function (d) { return d.status === 'Normal'; });
    var mod = districts.filter(function (d) { return d.status === 'Low Water'; });
    var high = districts.filter(function (d) { return d.status === 'High Turbidity'; });
    var avg = (districts.reduce(function (s, d) { return s + d.xgb_wqi; }, 0) / districts.length).toFixed(1);
    var watch = districts.slice().sort(function (a, b) { return a.xgb_wqi - b.xgb_wqi; }).slice(0, 5)
      .map(function (d, i) { return (i + 1) + '. ' + d.district + ' (' + d.status + ', WQI ' + d.xgb_wqi.toFixed(1) + ')'; }).join('\n');

    var reportText =
      'AQUATWIN AI - TELANGANA WATER INTELLIGENCE REPORT\n' +
      'Generated: ' + new Date().toLocaleString() + '\n' +
      'Data Source: Sentinel-2 GEE Satellite + 3Y LSTM/XGBoost\n' +
      '----------------------------------------\n' +
      'Districts Monitored: ' + districts.length + '\n' +
      'State Avg WQI: ' + avg + ' / 100\n' +
      'Normal: ' + safe.length + ' | Low Water: ' + mod.length + ' | High Turbidity: ' + high.length + '\n\n' +
      'Priority Watchlist:\n' + watch + '\n\n' +
      'AI Recommendation:\nPrioritize turbidity filtration, groundwater recharge pits, and drought stress simulations.';

    var html =
      '<div class="ios-card" style="white-space:pre-wrap;font-size:12.5px;line-height:1.5;color:var(--label-secondary);">' + window.atEscapeHtml(reportText) + '</div>' +
      '<div class="at-sheet-actions">' +
        '<button type="button" class="at-btn-ios-primary lg-press" id="at-copy-rep">Copy Report</button>' +
        '<button type="button" class="at-btn-ios-secondary lg-press" id="at-share-rep">Share</button>' +
      '</div>';

    openSystemSheet('Submission Report', 'Exportable Intelligence Brief', html);
    document.getElementById('at-copy-rep').addEventListener('click', function () {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(reportText).then(function () { showToast('Report copied'); }).catch(function () {});
      } else { showToast('Report ready'); }
    });
    document.getElementById('at-share-rep').addEventListener('click', function () {
      if (navigator.share) navigator.share({ title: 'AquaTwin AI Report', text: reportText }).catch(function () {});
      else document.getElementById('at-copy-rep').click();
    });
  }

  /* ------------------------------------------------------------------------
     15. Boot Application
     ------------------------------------------------------------------------ */
  function boot() {
    requestPersistentStorage();
    vaultPut('ml_33_districts', districts);
    if (!loadMergedOverrides().length) {
      vaultGet('merged_csv_records').then(function (saved) {
        if (Array.isArray(saved) && saved.length) {
          try { localStorage.setItem(MERGED_STORAGE_KEY, JSON.stringify(saved)); } catch (e) {}
          var curName = selected ? selected.district : 'Hyderabad';
          districts = buildDistrictList();
          selected = districts.find(function (d) { return d.district.toLowerCase() === curName.toLowerCase(); }) || districts[0];
          refreshAllStatsAndViews();
        }
      });
    }

    var sel = document.getElementById('simSelect');
    if (sel) {
      districts.forEach(function (d) {
        var opt = document.createElement('option');
        opt.value = d.district;
        opt.textContent = d.district;
        sel.appendChild(opt);
      });
      sel.value = selected.district;
      sel.addEventListener('change', function () { selectDistrict(sel.value, { fly: false }); });
      sel.addEventListener('mousedown', function (e) { e.preventDefault(); openDistrictPicker(); });
      sel.addEventListener('click', function (e) { e.preventDefault(); openDistrictPicker(); });
    }

    ['rainSlider', 'tempSlider', 'pollSlider'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.addEventListener('input', runSim);
    });
    document.getElementById('searchBox').addEventListener('input', renderList);
    document.getElementById('statusFilter').addEventListener('change', renderList);

    document.getElementById('at-map-district-pill').addEventListener('click', openDistrictPicker);
    document.getElementById('sheet-open-sim').addEventListener('click', function () { switchTab('sim'); });
    document.getElementById('sheet-ask-ai').addEventListener('click', function () {
      if (window.atOpenAssistantForDistrict) window.atOpenAssistantForDistrict('Recommend best action for ' + selected.district);
    });
    document.getElementById('dash-ask-best').addEventListener('click', function () {
      if (window.atOpenAssistantForDistrict) window.atOpenAssistantForDistrict('Best AI recommendations across 33 districts');
    });
    document.getElementById('sim-apply-best').addEventListener('click', applyOptimalPlan);
    document.getElementById('dash-see-all').addEventListener('click', function () { switchTab('list'); });
    document.getElementById('dash-go-map').addEventListener('click', function () { switchTab('map'); });
    document.getElementById('dash-go-sim').addEventListener('click', function () { switchTab('sim'); });

    document.getElementById('at-backdrop').addEventListener('click', function (e) {
      if (e.target.id === 'at-backdrop') closeSystemSheet();
    });

    document.addEventListener('click', function (e) {
      var al = e.target.closest ? e.target.closest('[data-open-alerts="1"]') : null;
      if (al) { openAlertsSheet(); return; }
      var rp = e.target.closest ? e.target.closest('[data-open-report="1"]') : null;
      if (rp) {
        var pop = document.getElementById('at-glass-popover');
        if (pop) pop.classList.remove('open');
        openReportSheet();
        return;
      }
      var di = e.target.closest ? e.target.closest('[data-open-data-import="1"]') : null;
      if (di) {
        var pop2 = document.getElementById('at-glass-popover');
        if (pop2) pop2.classList.remove('open');
        openDataImportSheet();
      }
    });

    initGlassAndMapControls();
    initBottomSheetDrag();
    bindHorizonControls();
    initFloatingDock();
    initDemoToggle();
    initMap();
    refreshAllStatsAndViews();
    updateStorageStatusUI();

    setTimeout(function () { prewarmTileStorage(false); }, 1800);

    if (window.AQUATWIN_ML_DATA) deepFreeze(window.AQUATWIN_ML_DATA);
    if (window.TELANGANA_DATA) deepFreeze(window.TELANGANA_DATA);
    verifyTelemetryFingerprint();

    window.addEventListener('popstate', function () {
      var bd = document.getElementById('at-backdrop');
      if (bd && bd.classList.contains('open')) { closeSystemSheet(); return; }
      if (activeView !== 'map') switchTab('map');
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
