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
    last_update: "Update terakhir"
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
    last_update: "Last update"
  }
};

function toggleLang() {
  currentLang = currentLang === 'id' ? 'en' : 'id';
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    if (i18n[currentLang][key]) el.textContent = i18n[currentLang][key];
  });
}

function formatRp(n) {
  return 'Rp' + Number(n).toLocaleString('id-ID');
}

function formatVol(n) {
  if (n >= 1e9) return (n/1e9).toFixed(2) + 'B';
  if (n >= 1e6) return (n/1e6).toFixed(2) + 'M';
  if (n >= 1e3) return (n/1e3).toFixed(1) + 'K';
  return n;
}

async function loadData() {
  try {
    const res = await fetch('data/result.json?t=' + Date.now());
    const data = await res.json();
    render(data);
    document.getElementById('lastUpdate').textContent = 
      i18n[currentLang].last_update + ': ' + new Date(data.generated_at).toLocaleString('id-ID');
  } catch (e) {
    document.getElementById('stockGrid').innerHTML = 
      '<p style="color:var(--red);text-align:center;grid-column:1/-1">⚠️ Gagal memuat data. Pastikan data/result.json tersedia.</p>';
  }
}

function render(data) {
  const grid = document.getElementById('stockGrid');
  grid.innerHTML = data.stocks.map(s => cardHTML(s)).join('');
}

function cardHTML(s) {
  const plan = s.plan;
  const changeClass = s.change_pct >= 0 ? 'up' : 'down';
  const changeSign = s.change_pct >= 0 ? '+' : '';
  const accumBadge = s.accumulation.score >= 40 
    ? `<div class="accumulation-badge">🔥 Akumulasi Terdeteksi (${s.accumulation.score}/100)</div>`
    : '';
  
  return `
    <div class="card" onclick='showModal(${JSON.stringify(s).replace(/'/g, "&apos;")})'>
      <div class="card-header">
        <div class="symbol-block">
          <div class="symbol">${s.symbol}</div>
          <div class="name">${s.name}</div>
        </div>
        <div class="price-block">
          <div class="price">${formatRp(s.price)}</div>
          <div class="change ${changeClass}">${changeSign}${s.change_pct}%</div>
        </div>
      </div>
      
      <div class="score-section">
        <div class="score-header">
          <span class="score-label">Confluence Score</span>
          <span class="score-value">${s.score}/100</span>
        </div>
        <div class="score-bar">
          <div class="score-fill" style="width:${s.score}%; background: linear-gradient(90deg, ${plan.color}88, ${plan.color})"></div>
        </div>
      </div>
      
      <div class="recommendation" style="background:${plan.color}22; color:${plan.color}; border:1px solid ${plan.color}55">
        ${plan.recommendation}
      </div>
      
      ${accumBadge}
      
      <div class="quick-info">
        <div><span class="label">Entry</span><span class="value">${formatRp(plan.entry_zone.low)}</span></div>
        <div><span class="label">Stop Loss</span><span class="value" style="color:var(--red)">${formatRp(plan.stop_loss)}</span></div>
        <div><span class="label">Target 2</span><span class="value" style="color:var(--gold-bright)">${formatRp(plan.targets.T2.price)}</span></div>
        <div><span class="label">R:R</span><span class="value">1:${plan.risk_reward}</span></div>
      </div>
    </div>
  `;
}

function showModal(s) {
  const plan = s.plan;
  const body = document.getElementById('modalBody');
  
  const signalsHTML = Object.entries(s.signals).map(([k, v]) => {
    const maxPts = {rsi:12, divergence:10, bb:12, macd:10, accumulation:15, atr_squeeze:8, ma:10, pivot:10, fib:8, weekly:5}[k] || 10;
    const cls = v === 0 ? 'zero' : '';
    return `<div class="signal-item ${cls}"><span class="name">${k.toUpperCase()}</span><span class="pts">${v}/${maxPts}</span></div>`;
  }).join('');
  
  const reasonsHTML = s.reasons.map(r => `<li>${r}</li>`).join('');
  
  body.innerHTML = `
    <div class="modal-header">
      <div>
        <div class="modal-symbol">${s.symbol}</div>
        <div class="modal-name">${s.name} • ${s.sector} • ${s.industry}</div>
      </div>
      <div class="price-block">
        <div class="price">${formatRp(s.price)}</div>
        <div class="change ${s.change_pct >= 0 ? 'up' : 'down'}">${s.change_pct >= 0 ? '+' : ''}${s.change_pct}%</div>
      </div>
    </div>
    
    <div class="plan-grid">
      <div class="plan-box entry">
        <div class="label">${i18n[currentLang].entry_zone}</div>
        <div class="value">${formatRp(plan.entry_zone.low)} - ${formatRp(plan.entry_zone.high)}</div>
      </div>
      <div class="plan-box stop">
        <div class="label">${i18n[currentLang].stop_loss}</div>
        <div class="value">${formatRp(plan.stop_loss)} (-${plan.max_loss_pct}%)</div>
      </div>
      <div class="plan-box target">
        <div class="label">${i18n[currentLang].target} 1 (R:R 1:${plan.risk_reward/2})</div>
        <div class="value">${formatRp(plan.targets.T1.price)} (+${plan.targets.T1.pct}%)</div>
      </div>
      <div class="plan-box target">
        <div class="label">${i18n[currentLang].target} 2 (R:R 1:${plan.risk_reward})</div>
        <div class="value">${formatRp(plan.targets.T2.price)} (+${plan.targets.T2.pct}%)</div>
      </div>
      <div class="plan-box target">
        <div class="label">${i18n[currentLang].target} 3 (Aggressive)</div>
        <div class="value">${formatRp(plan.targets.T3.price)} (+${plan.targets.T3.pct}%)</div>
      </div>
      <div class="plan-box">
        <div class="label">ATR (Volatilitas)</div>
        <div class="value">${formatRp(plan.atr)}</div>
      </div>
    </div>
    
    <div class="section-title">${i18n[currentLang].score_breakdown} — ${s.score}/100</div>
    <div class="signal-grid">${signalsHTML}</div>
    
    <div class="section-title">${i18n[currentLang].reasons}</div>
    <ul class="reasons-list">${reasonsHTML || '<li style="opacity:0.5">Belum ada alasan kuat untuk entry</li>'}</ul>
    
    <div class="section-title">${i18n[currentLang].accumulation}</div>
    <div class="plan-box" style="margin-bottom:16px">
      <div class="label">Accumulation Score</div>
      <div class="value" style="color:${s.accumulation.score >= 60 ? 'var(--green)' : 'var(--text-secondary)'}">${s.accumulation.score}/100 • Vol Ratio: ${s.accumulation.vol_ratio}x</div>
    </div>
    
    <div class="section-title">Data Pasar</div>
    <div class="quick-info" style="border:none;padding:0">
      <div><span class="label">Volume</span><span class="value">${formatVol(s.volume)}</span></div>
      <div><span class="label">Avg Vol 20D</span><span class="value">${formatVol(s.avg_volume_20d)}</span></div>
      <div><span class="label">52W High</span><span class="value">${formatRp(s.high_52w)}</span></div>
      <div><span class="label">52W Low</span><span class="value">${formatRp(s.low_52w)}</span></div>
    </div>
    
    <div class="disclaimer">${s.disclaimer}</div>
    <div style="text-align:center;color:var(--text-muted);font-size:11px;margin-top:16px">
      Analisis: ${s.analysis_date}
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
setInterval(loadData, 5 * 60 * 1000); // refresh tiap 5 menit
