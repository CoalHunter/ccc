let currentLang = 'id';

const i18n = {
  id: {
    hero_title: "The 10-Point Confluence System",
    hero_desc: "Analisis konfluensi 10 indikator • Deteksi akumulasi bandar • ATR-based risk management",
    disclaimer: "⚠️ Ini bukan nasihat keuangan. Riset mandiri, kelola risiko, jangan all-in.",
    entry_zone: "Entry Zone",
    stop_loss: "Stop Loss",
    target: "Target",
    risk_reward: "Risk:Reward",
    max_loss: "Max Loss",
    score_breakdown: "Breakdown Skor",
    reasons: "Alasan Entry",
    indicators: "Indikator Detail",
    accumulation: "Akumulasi Bandar",
    last_update: "Update terakhir",
    no_data: "⚠️ Belum ada data. Jalankan analyzer.py atau tunggu GitHub Actions selesai.",
    fetch_error: "⚠️ Gagal memuat data. Cek Console (F12) untuk detail.",
    loading: "⏳ Memuat data...",
    stale_banner: "⚠️ Data sedang di-cache (fetch terakhir gagal). Angka mungkin tidak 100% real-time."
  },
  en: {
    hero_title: "The 10-Point Confluence System",
    hero_desc: "10-indicator confluence analysis • Bandit accumulation detection • ATR-based risk management",
    disclaimer: "⚠️ This is not financial advice. Do your own research, manage risk, never all-in.",
    entry_zone: "Entry Zone",
    stop_loss: "Stop Loss",
    target: "Target",
    risk_reward: "Risk:Reward",
    max_loss: "Max Loss",
    score_breakdown: "Score Breakdown",
    reasons: "Entry Reasons",
    indicators: "Indicator Details",
    accumulation: "Bandit Accumulation",
    last_update: "Last update",
    no_data: "⚠️ No data yet. Run analyzer.py or wait for GitHub Actions.",
    fetch_error: "⚠️ Failed to load data. Check Console (F12) for details.",
    loading: "⏳ Loading data...",
    stale_banner: "⚠️ Data is cached (last fetch failed). Numbers may not be 100% real-time."
  }
};

function getBasePath() {
  const path = window.location.pathname;
  const parts = path.split('/').filter(p => p && !p.endsWith('.html'));
  return '/' + parts.join('/') + (parts.length ? '/' : '');
}

const BASE_PATH = getBasePath();
console.log('📁 Base path:', BASE_PATH);

function toggleLang() {
  currentLang = currentLang === 'id' ? 'en' : 'id';
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    if (i18n[currentLang][key]) el.textContent = i18n[currentLang][key];
  });
  if (window._cachedData) render(window._cachedData);
}

function formatRp(n) {
  if (n === null || n === undefined) return '-';
  return 'Rp' + Number(n).toLocaleString('id-ID');
}

function formatVol(n) {
  if (!n) return '-';
  if (n >= 1e9) return (n/1e9).toFixed(2) + 'B';
  if (n >= 1e6) return (n/1e6).toFixed(2) + 'M';
  if (n >= 1e3) return (n/1e3).toFixed(1) + 'K';
  return n;
}

async function loadData() {
  const grid = document.getElementById('stockGrid');
  grid.innerHTML = `<p style="color:var(--text-muted);text-align:center;grid-column:1/-1;padding:40px">${i18n[currentLang].loading}</p>`;

  // Hapus banner stale lama
  document.querySelectorAll('.stale-banner').forEach(el => el.remove());

  try {
    const possiblePaths = [
      BASE_PATH + 'data/result.json',
      './data/result.json',
      'data/result.json'
    ];

    console.log('🔍 Mencoba path:', possiblePaths);

    let data = null;
    let usedPath = '';

    for (const path of possiblePaths) {
      try {
        const res = await fetch(path + '?t=' + Date.now(), { cache: 'no-store' });
        if (res.ok) {
          data = await res.json();
          usedPath = path;
          break;
        }
        console.warn(`❌ ${path} → ${res.status}`);
      } catch (e) {
        console.warn(`❌ ${path} → ${e.message}`);
      }
    }

    if (!data) {
      grid.innerHTML = `<p style="color:var(--red);text-align:center;grid-column:1/-1;padding:40px">${i18n[currentLang].fetch_error}</p>`;
      return;
    }

    console.log('✅ Data loaded from:', usedPath);
    console.log('📊 Stocks count:', data.stocks?.length || 0);
    if (data.errors) console.warn('⚠️ Analyzer errors:', data.errors);

    if (!data.stocks || data.stocks.length === 0) {
      grid.innerHTML = `<p style="color:var(--orange);text-align:center;grid-column:1/-1;padding:40px">${i18n[currentLang].no_data}</p>`;
      return;
    }

    // Banner stale
    if (data.stale) {
      const banner = document.createElement('div');
      banner.className = 'stale-banner';
      banner.style.cssText = 'background:rgba(255,152,0,0.12);border:1px solid #ff9800;color:#ff9800;padding:12px;border-radius:10px;margin-bottom:20px;text-align:center;font-size:13px';
      banner.textContent = i18n[currentLang].stale_banner;
      document.querySelector('.hero').after(banner);
    }

    window._cachedData = data;
    render(data);

    const updateEl = document.getElementById('lastUpdate');
    if (updateEl) {
      updateEl.textContent = i18n[currentLang].last_update + ': ' + new Date(data.generated_at).toLocaleString('id-ID');
    }

  } catch (e) {
    console.error('💥 Fatal error:', e);
    grid.innerHTML = `<p style="color:var(--red);text-align:center;grid-column:1/-1;padding:40px">💥 ${e.message}</p>`;
  }
}

function render(data) {
  const grid = document.getElementById('stockGrid');
  if (!data.stocks || data.stocks.length === 0) {
    grid.innerHTML = `<p style="color:var(--orange);text-align:center;grid-column:1/-1">${i18n[currentLang].no_data}</p>`;
    return;
  }
  grid.innerHTML = data.stocks.map(s => cardHTML(s)).join('');
}

function cardHTML(s) {
  const plan = s.plan;
  if (!plan) return '';

  const changeClass = s.change_pct >= 0 ? 'up' : 'down';
  const changeSign = s.change_pct >= 0 ? '+' : '';

  const accumBadge = s.accumulation && s.accumulation.score >= 40
    ? `<div class="accumulation-badge">🔥 Akumulasi Terdeteksi (${s.accumulation.score}/100)</div>`
    : '';

  const entryLow = plan.entry_zone?.low || s.price;
  const stopLoss = plan.stop_loss || s.price * 0.95;
  const t2Price = plan.targets?.T2?.price || s.price * 1.1;
  const rr = plan.risk_reward || 0;

  return `
    <div class="card" onclick='showModal(${JSON.stringify(s).replace(/'/g, "&#39;")})'>
      <div class="card-header">
        <div class="symbol-block">
          <div class="symbol">${s.symbol}</div>
          <div class="name">${s.name || ''}</div>
        </div>
        <div class="price-block">
          <div class="price">${formatRp(s.price)}</div>
          <div class="change ${changeClass}">${changeSign}${s.change_pct}%</div>
        </div>
      </div>

      <div class="score-section">
        <div class="score-header">
          <span class="score-label">Confluence Score</span>
          <span class="score-value">${s.score || 0}/100</span>
        </div>
        <div class="score-bar">
          <div class="score-fill" style="width:${s.score || 0}%; background: linear-gradient(90deg, ${plan.color}88, ${plan.color})"></div>
        </div>
      </div>

      <div class="recommendation" style="background:${plan.color}22; color:${plan.color}; border:1px solid ${plan.color}55">
        ${plan.recommendation}
      </div>

      ${accumBadge}

      <div class="quick-info">
        <div><span class="label">Entry</span><span class="value">${formatRp(entryLow)}</span></div>
        <div><span class="label">Stop Loss</span><span class="value" style="color:var(--red)">${formatRp(stopLoss)}</span></div>
        <div><span class="label">Target 2</span><span class="value" style="color:var(--gold-bright)">${formatRp(t2Price)}</span></div>
        <div><span class="label">R:R</span><span class="value">1:${rr}</span></div>
      </div>
    </div>
  `;
}

function showModal(s) {
  const plan = s.plan;
  if (!plan) return;

  const body = document.getElementById('modalBody');

  const maxPts = {rsi:12, divergence:10, bb:12, macd:10, accumulation:15, atr_squeeze:8, ma:10, pivot:10, fib:8, weekly:5};
  const signals = s.signals || {};

  const signalsHTML = Object.entries(signals).map(([k, v]) => {
    const mp = maxPts[k] || 10;
    const cls = v === 0 ? 'zero' : '';
    return `<div class="signal-item ${cls}"><span class="name">${k.toUpperCase()}</span><span class="pts">${v}/${mp}</span></div>`;
  }).join('');

  const reasons = s.reasons || [];
  const reasonsHTML = reasons.length ? reasons.map(r => `<li>${r}</li>`).join('') : '<li style="opacity:0.5">Belum ada alasan kuat untuk entry</li>';

  const accum = s.accumulation || {score: 0, vol_ratio: 0};

  body.innerHTML = `
    <div class="modal-header">
      <div>
        <div class="modal-symbol">${s.symbol}</div>
        <div class="modal-name">${s.name || ''} • ${s.sector || 'Materials'} • ${s.industry || 'Coal'}</div>
      </div>
      <div class="price-block">
        <div class="price">${formatRp(s.price)}</div>
        <div class="change ${s.change_pct >= 0 ? 'up' : 'down'}">${s.change_pct >= 0 ? '+' : ''}${s.change_pct}%</div>
      </div>
    </div>

    <div class="plan-grid">
      <div class="plan-box entry">
        <div class="label">${i18n[currentLang].entry_zone}</div>
        <div class="value">${formatRp(plan.entry_zone?.low)} - ${formatRp(plan.entry_zone?.high)}</div>
      </div>
      <div class="plan-box stop">
        <div class="label">${i18n[currentLang].stop_loss}</div>
        <div class="value">${formatRp(plan.stop_loss)} (-${plan.max_loss_pct}%)</div>
      </div>
      <div class="plan-box target">
        <div class="label">${i18n[currentLang].target} 1</div>
        <div class="value">${formatRp(plan.targets?.T1?.price)} (+${plan.targets?.T1?.pct}%)</div>
      </div>
      <div class="plan-box target">
        <div class="label">${i18n[currentLang].target} 2</div>
        <div class="value">${formatRp(plan.targets?.T2?.price)} (+${plan.targets?.T2?.pct}%)</div>
      </div>
      <div class="plan-box target">
        <div class="label">${i18n[currentLang].target} 3</div>
        <div class="value">${formatRp(plan.targets?.T3?.price)} (+${plan.targets?.T3?.pct}%)</div>
      </div>
      <div class="plan-box">
        <div class="label">ATR</div>
        <div class="value">${formatRp(plan.atr)}</div>
      </div>
    </div>

    <div class="section-title">${i18n[currentLang].score_breakdown} — ${s.score}/100</div>
    <div class="signal-grid">${signalsHTML}</div>

    <div class="section-title">${i18n[currentLang].reasons}</div>
    <ul class="reasons-list">${reasonsHTML}</ul>

    <div class="section-title">${i18n[currentLang].accumulation}</div>
    <div class="plan-box" style="margin-bottom:16px">
      <div class="label">Accumulation Score</div>
      <div class="value" style="color:${accum.score >= 60 ? 'var(--green)' : 'var(--text-secondary)'}">${accum.score}/100 • Vol Ratio: ${accum.vol_ratio}x</div>
    </div>

    <div class="section-title">Data Pasar</div>
    <div class="quick-info" style="border:none;padding:0">
      <div><span class="label">Volume</span><span class="value">${formatVol(s.volume)}</span></div>
      <div><span class="label">Avg Vol 20D</span><span class="value">${formatVol(s.avg_volume_20d)}</span></div>
      <div><span class="label">52W High</span><span class="value">${formatRp(s.high_52w)}</span></div>
      <div><span class="label">52W Low</span><span class="value">${formatRp(s.low_52w)}</span></div>
    </div>

    <div class="disclaimer">${s.disclaimer || i18n[currentLang].disclaimer}</div>
    <div style="text-align:center;color:var(--text-muted);font-size:11px;margin-top:16px">
      Analisis: ${s.analysis_date || '-'}
    </div>
  `;

  document.getElementById('modal').classList.remove('hidden');
}

function closeModal() {
  document.getElementById('modal').classList.add('hidden');
}

document.getElementById('modal').addEventListener('click', e => {
  if (e.target.id === 'modal') closeModal();
});

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeModal();
});

loadData();
setInterval(loadData, 5 * 60 * 1000);
