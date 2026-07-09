(() => {
  const $ = (selector) => document.querySelector(selector);

  // DOM references
  const form = $('#analysis-form');
  if (!form) return;

  const query = $('#stock-query');
  const select = $('#stock-select');
  const button = $('#analyze-button');
  const entry = $('#analysis-entry');
  const processing = $('#processing-state');
  const resultState = $('#result-state');
  const status = $('#form-status');
  const sectorSummary = $('#sector-summary');
  const downloadReportButton = $('#download-report-button');
  const reportStatus = $('#report-status');
  const ANALYSIS_SESSION_KEY = 'sda:lastAnalysisPayload';

  if (!query || !select || !button) return;

  let processTimer = null;
  let activeProcessStep = -1;
  let lastAnalysisPayload = null;
  let currentState = 'entry';
  let stateTransitionTimer = null;

  // Button icons
  const SEND_ICON = `
    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18"
      viewBox="0 0 24 24" fill="none" stroke="currentColor"
      stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"
      aria-hidden="true">
      <line x1="12" y1="19" x2="12" y2="5"></line>
      <polyline points="5 12 12 5 19 12"></polyline>
    </svg>
  `;

  const LOADING_ICON = `<span class="spinner" aria-hidden="true"></span>`;

  // Formatter utilities
  const text = (value, fallback = '—') => (
    value === null || value === undefined || value === '' ? fallback : String(value)
  );

  const percent = (value) => (
    Number.isFinite(Number(value)) ? `${Number(value).toFixed(2)}%` : '—'
  );

  const number = (value) => (
    Number.isFinite(Number(value))
      ? new Intl.NumberFormat('id-ID', { maximumFractionDigits: 2 }).format(Number(value))
      : '—'
  );

  const money = (value) => (
    Number.isFinite(Number(value))
      ? new Intl.NumberFormat('id-ID', {
          style: 'currency',
          currency: 'IDR',
          maximumFractionDigits: 0
        }).format(Number(value))
      : '—'
  );

  const escapeHtml = (value) => {
    const node = document.createElement('div');
    node.textContent = text(value, '');
    return node.innerHTML;
  };

  const signalClass = (signal) => `signal-${String(signal || 'HOLD').toLowerCase()}`;

  const toneClass = (signal) => {
    const normalized = String(signal || 'HOLD').toUpperCase();

    if (normalized === 'BUY') return 'tone-buy';
    if (normalized === 'SELL') return 'tone-sell';
    return 'tone-hold';
  };

  const lastActiveSignalToneClass = (analysis) => {
    const item = (analysis || {}).last_active_signal;
    return toneClass(item && item.signal ? item.signal : 'HOLD');
  };


  const show = (element, visible) => {
    if (!element) return;
    element.hidden = !visible;
  };

  const prefersReducedMotion = () => (
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );

  const stateMap = {
    entry,
    processing,
    result: resultState
  };

  function setLoading(active) {
    button.disabled = active;
    button.innerHTML = active ? LOADING_ICON : SEND_ICON;
    button.setAttribute('aria-label', active ? 'Analisis sedang diproses' : 'Kirim analisis');
    button.setAttribute('title', active ? 'Analisis sedang diproses' : 'Kirim analisis');
  }

  // API loading
  async function loadStocks() {
    try {
      const response = await fetch('/api/stocks');
      const body = await response.json();

      if (!body.success) throw new Error('stocks unavailable');

      select.innerHTML =
        '<option value="">Pilih saham dari daftar</option>' +
        body.data.map((stock) => {
          const ticker = escapeHtml(text(stock.ticker, ''));
          const labelParts = [
            ticker,
            stock.stock_name ? escapeHtml(stock.stock_name) : '',
            stock.sektor ? escapeHtml(stock.sektor) : ''
          ].filter(Boolean);
          return `<option value="${ticker}">${labelParts.join(' - ')}</option>`;
        }).join('');
    } catch {
      select.innerHTML = '<option value="">Daftar saham belum tersedia</option>';
    }
  }

  async function loadSectors() {
    try {
      const response = await fetch('/api/sectors');
      const body = await response.json();

      if (!body.success || !sectorSummary) return;

      const sectors = body.data.length;
      const stocks = body.data.reduce(
        (total, item) => total + Number(item.jumlah_saham || 0),
        0
      );

      sectorSummary.textContent = `${sectors} sektor dan ${stocks} saham sampel tersedia.`;
    } catch {
      /* Ringkasan sektor bukan prasyarat analisis. */
    }
  }

  // State transition and processing progress
  function clearProcessTimer() {
    if (processTimer) {
      clearInterval(processTimer);
      processTimer = null;
    }
  }

  function resetProcessSteps() {
    clearProcessTimer();
    const steps = [...document.querySelectorAll('.process-steps li')];
    steps.forEach((item) => item.classList.remove('is-active'));
    activeProcessStep = -1;
    return steps;
  }

  function startProcessSteps(steps) {
    if (!steps.length) return;

    activeProcessStep = 0;
    steps[activeProcessStep].classList.add('is-active');

    processTimer = setInterval(() => {
      if (activeProcessStep >= steps.length - 1) {
        clearProcessTimer();
        return;
      }

      steps[activeProcessStep].classList.remove('is-active');
      activeProcessStep += 1;
      steps[activeProcessStep].classList.add('is-active');
    }, 750);
  }

  function setState(name) {
    if (!stateMap[name]) return;

    clearTimeout(stateTransitionTimer);

    const steps = resetProcessSteps();
    const next = stateMap[name];

    Object.values(stateMap).forEach((element) => {
      if (!element) return;
      element.classList.remove('is-entering', 'is-leaving');
      show(element, element === next);
    });

    if (!prefersReducedMotion()) {
      next.classList.add('is-entering');
      stateTransitionTimer = setTimeout(() => {
        next.classList.remove('is-entering');
      }, 240);
    }

    currentState = name;

    if (name === 'processing') {
      startProcessSteps(steps);
    }
  }

  function completeLoadingSteps() {
    // Finish remaining process steps before revealing the result state.
    const steps = [...document.querySelectorAll('.process-steps li')];

    if (!steps.length) return Promise.resolve();

    clearProcessTimer();

    if (activeProcessStep < 0) {
      activeProcessStep = 0;
      steps[activeProcessStep].classList.add('is-active');
    }

    const advance = () => {
      if (activeProcessStep >= steps.length - 1) {
        return Promise.resolve();
      }

      steps[activeProcessStep].classList.remove('is-active');
      activeProcessStep += 1;
      steps[activeProcessStep].classList.add('is-active');

      return new Promise((resolve) => setTimeout(resolve, 180)).then(advance);
    };

    return advance();
  }

  // Form status and text rendering helpers
  function clearStatus() {
    status.textContent = '';
    status.classList.remove('error');
  }

  function showError(message) {
    status.textContent = message;
    status.classList.add('error');
    setState('entry');
  }

  function formatExplanation(value) {
    return escapeHtml(text(value, 'Penjelasan belum tersedia.'))
      .split(/\n{2,}/)
      .map((paragraph) => `<p>${paragraph.replace(/\n/g, '<br>')}</p>`)
      .join('');
  }

  function formatStructuredExplanation(value) {
  const paragraphs = escapeHtml(text(value, 'Penjelasan belum tersedia.'))
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean);

  if (!paragraphs.length) {
    return `
      <section class="explanation-block">
        <h3>Ringkasan</h3>
        <p>Penjelasan belum tersedia.</p>
      </section>
    `;
  }

  const labels = [
    'Ringkasan utama',
    'Alasan sinyal',
    'Evaluasi indikator terbaik',
    'Perbandingan indikator',
    'Catatan risiko'
  ];

  if (paragraphs.length === 1) {
    return `
      <section class="explanation-block">
        <h3>Ringkasan utama</h3>
        <p>${paragraphs[0].replace(/\n/g, '<br>')}</p>
      </section>
    `;
  }

  return paragraphs.map((paragraph, index) => {
    const title = labels[index] || 'Informasi tambahan';

    return `
      <section class="explanation-block">
        <h3>${title}</h3>
        <p>${paragraph.replace(/\n/g, '<br>')}</p>
      </section>
    `;
  }).join('');
}

  function chart(points) {
    const valid = (Array.isArray(points) ? points : [])
      .filter((point) => Number.isFinite(Number(point.close)));

    if (!valid.length) {
      return '<p class="muted">Data grafik belum tersedia.</p>';
    }

    const values = valid.map((point) => Number(point.close));
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;

    const w = 700;
    const h = 240;
    const pad = 30;

    const path = valid.map((point, index) => {
      const x = pad + index * ((w - pad * 2) / Math.max(valid.length - 1, 1));
      const y = h - pad - ((Number(point.close) - min) / range) * (h - pad * 2);
      return `${index ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');

    return `
      <div class="chart-wrap">
        <svg class="price-chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Grafik harga penutupan terbaru">
          <line x1="${pad}" x2="${w - pad}" y1="${h - pad}" y2="${h - pad}" stroke="#E2E8F0"></line>
          <path class="chart-line" d="${path}"></path>
          <text class="chart-label" x="${pad}" y="16">${number(max)}</text>
          <text class="chart-label" x="${pad}" y="${h - 7}">${number(min)}</text>
          <text class="chart-label" x="${w - pad - 70}" y="${h - 7}">${escapeHtml(valid[valid.length - 1].date)}</text>
        </svg>
      </div>
    `;
  }



  function formatValidationStatus(status) {
    const labels = {
      MATCH: 'Sesuai arah',
      NOT_MATCH: 'Tidak sesuai arah',
      NOT_MATCH_FLAT: 'Harga tidak berubah',
      NOT_EVALUATED_HOLD: 'Tidak dievaluasi karena HOLD',
      UNAVAILABLE: 'Data belum tersedia'
    };
    return labels[String(status || '').toUpperCase()] || 'Data belum tersedia';
  }

  function validationStatusClass(status) {
    return `validation-${String(status || 'unavailable').toLowerCase()}`;
  }

  function nullable(value) {
    if (value === null || value === undefined || value === '') return '-';
    if (typeof value === 'number' && !Number.isFinite(value)) return '-';
    if (String(value).toLowerCase() === 'nan') return '-';
    return escapeHtml(value);
  }

  function validationMessage(item) {
    const status = String((item || {}).status || '').toUpperCase();
    const signal = String((item || {}).signal || '').toUpperCase();
    const label = text((item || {}).label, 'horizon ini');

    if (status === 'NOT_EVALUATED_HOLD' && signal === 'HOLD') {
      return 'Sinyal HOLD tidak dievaluasi karena bukan sinyal aktif.';
    }
    if (status === 'MATCH' && (signal === 'BUY' || signal === 'SELL')) {
      return `Arah harga sesuai dengan sinyal ${signal} pada ${label}.`;
    }
    if (status === 'UNAVAILABLE') {
      return 'Data setelah tanggal sinyal belum tersedia.';
    }
    return text((item || {}).message, '-');
  }
  function formatTechnicalCondition(value) {
    const raw = text(value, '');
    if (!raw) return '—';

    const normalized = raw
      .replace(/;\s*/g, '\n')
      .replace(/\.\s+(?=SMA|Sinyal|Close|RSI|MACD)/g, '.\n');

    return escapeHtml(normalized)
      .split(/\n+/)
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => `<span>${line}</span>`)
      .join('');
  }

  function saveAnalysisSession(payload) {
  try {
    sessionStorage.setItem(ANALYSIS_SESSION_KEY, JSON.stringify(payload));
  } catch {
    /* Penyimpanan session bukan prasyarat analisis. */
  }
}

function loadAnalysisSession() {
  try {
    const raw = sessionStorage.getItem(ANALYSIS_SESSION_KEY);
    if (!raw) return null;

    const payload = JSON.parse(raw);
    if (!payload || !payload.success || !payload.analysis) return null;

    return payload;
  } catch {
    return null;
  }
}

function clearAnalysisSession() {
  try {
    sessionStorage.removeItem(ANALYSIS_SESSION_KEY);
  } catch {
    /* Abaikan kegagalan pembersihan session. */
  }
}

  function formatCompactTechnicalCondition(analysis) {
    const signal = text((analysis || {}).latest_signal, 'HOLD').toUpperCase();
    const condition = text((analysis || {}).latest_condition, '');

    let detail = 'Kondisi teknikal terbaru mengikuti aturan indikator terbaik.';

    if (/tidak ada crossover baru/i.test(condition)) {
      detail = 'Belum ada crossover baru pada data terakhir.';
    } else if (/crossover baru/i.test(condition)) {
      detail = 'Terdapat crossover baru pada data terakhir.';
    } else if (/oversold/i.test(condition)) {
      detail = 'Kondisi berkaitan dengan area oversold RSI.';
    } else if (/overbought/i.test(condition)) {
      detail = 'Kondisi berkaitan dengan area overbought RSI.';
    } else if (/MACD/i.test(condition)) {
      detail = 'Kondisi mengikuti perubahan garis MACD dan signal line.';
    }

    return `
      <span class="condition-signal ${signalClass(signal)}">${escapeHtml(signal)}</span>
      <span>${escapeHtml(detail)}</span>
    `;
  }

  function formatLastActiveSignal(analysis) {
    const item = (analysis || {}).last_active_signal;

  if (!item || !item.signal || !item.date) {
    return `
      <span class="last-signal-empty">
        Belum ada sinyal aktif BUY/SELL pada periode data yang tersedia.
      </span>
    `;
  }

  const signal = String(item.signal).toUpperCase();

  if (signal !== 'BUY' && signal !== 'SELL') {
    return `
      <span class="last-signal-empty">
        Belum ada sinyal aktif BUY/SELL pada periode data yang tersedia.
      </span>
    `;
  }

  return `
    <span class="last-signal-wrap">
      <span class="signal mini-signal ${signalClass(signal)}">${escapeHtml(signal)}</span>
      <span class="last-signal-date">${escapeHtml(item.date)}</span>
    </span>
  `;
}

  function formatLastActiveSignalNote(analysis) {
  const item = (analysis || {}).last_active_signal;
  const indicator = String((analysis || {}).best_indicator || '').trim();

  if (!item || !item.signal || !item.date) {
    return 'Sistem belum menemukan sinyal aktif BUY atau SELL pada periode data yang tersedia.';
  }

  const signal = String(item.signal).toUpperCase();

  if (indicator === 'MA Crossover') {
    return `Sinyal ${signal} terakhir muncul ketika SMA10 memotong SMA50.`;
  }

  if (indicator === 'MACD') {
    return `Sinyal ${signal} terakhir muncul ketika MACD Line memotong Signal Line.`;
  }

  if (indicator === 'RSI') {
    return `Sinyal ${signal} terakhir muncul ketika RSI keluar dari area ekstrem.`;
  }

  return `Sinyal ${signal} terakhir muncul berdasarkan aturan indikator terbaik sektor.`;
}

  function renderPostSignalValidation(analysis) {
    const validations = Array.isArray((analysis || {}).post_signal_validation)
      ? analysis.post_signal_validation
      : [];

    const items = validations.length ? validations : [1, 3, 5, 10].map((horizon) => ({
      horizon,
      label: `T+${horizon}`,
      status: 'UNAVAILABLE',
      message: 'Data setelah tanggal sinyal belum tersedia.'
    }));
    const latestSignal = String((analysis || {}).latest_signal || '').toUpperCase();
      const isHoldSignal = latestSignal === 'HOLD';
      const allHoldNotEvaluated = items.every((item) => (
        String((item || {}).status || '').toUpperCase() === 'NOT_EVALUATED_HOLD'
      ));

      if (isHoldSignal && allHoldNotEvaluated) {
        return `
          <section class="result-card validation-card validation-card-compact">
            <h3 class="metrics-title">Validasi Lanjutan Sinyal Terbaru</h3>
            <div class="hold-validation-summary">
              <span class="validation-status validation-not_evaluated_hold">Tidak dievaluasi</span>
              <div>
                <strong>Sinyal terbaru adalah HOLD.</strong>
                <p>
                  Validasi lanjutan tidak dilakukan karena HOLD bukan sinyal aktif BUY atau SELL.
                  Validasi ini tidak digunakan untuk mengubah indikator terbaik atau sinyal utama.
                </p>
              </div>
            </div>
          </section>
        `;
      }    

    const rows = items.map((item) => {
      const status = String((item || {}).status || '').toUpperCase();
      const isHoldValidation = status === 'NOT_EVALUATED_HOLD';
      const detailRows = [
        `<div><dt>Sinyal</dt><dd>${nullable(item.signal)}</dd></div>`,
        `<div><dt>Tanggal sinyal</dt><dd>${nullable(item.signal_date)}</dd></div>`
      ];

      if (!isHoldValidation) {
        detailRows.push(
          `<div><dt>Tanggal target</dt><dd>${nullable(item.target_date)}</dd></div>`,
          `<div><dt>Close sinyal</dt><dd>${item.close_t === null || item.close_t === undefined ? '-' : money(item.close_t)}</dd></div>`,
          `<div><dt>Close target</dt><dd>${item.close_future === null || item.close_future === undefined ? '-' : money(item.close_future)}</dd></div>`,
          `<div><dt>Return</dt><dd>${item.return_pct === null || item.return_pct === undefined ? '-' : percent(item.return_pct)}</dd></div>`
        );
      }

      return `
        <article class="validation-item">
          <div class="validation-item-head">
            <strong>${nullable(item.label)}</strong>
            <span class="validation-status ${validationStatusClass(item.status)}">
              ${escapeHtml(formatValidationStatus(item.status))}
            </span>
          </div>
          <dl class="validation-details">
            ${detailRows.join('')}
          </dl>
          <p>${escapeHtml(validationMessage(item))}</p>
        </article>
      `;
    }).join('');

    return `
      <section class="result-card validation-card">
        <h3 class="metrics-title">Validasi Lanjutan Sinyal Terbaru</h3>
        <p class="metrics-description">
          Validasi ini membandingkan sinyal terbaru dengan arah harga pada T+1, T+3, T+5, dan T+10 hari perdagangan bursa saham. Validasi ini tidak digunakan untuk mengubah indikator terbaik atau sinyal utama.
        </p>
        <div class="validation-grid">${rows}</div>
      </section>
    `;
  }

  function renderSignalRiskNote(analysis) {
  const signal = String((analysis || {}).latest_signal || '').toUpperCase();

  if (signal !== 'BUY' && signal !== 'SELL') {
    return '';
  }

  const signalText = signal === 'BUY'
    ? 'Sinyal BUY menunjukkan kondisi teknikal yang mengarah pada potensi penguatan harga.'
    : 'Sinyal SELL menunjukkan kondisi teknikal yang mengarah pada potensi pelemahan harga.';

  return `
    <section class="result-card signal-risk-card">
      <div class="signal-risk-head">
        <span class="signal ${signalClass(signal)}">${escapeHtml(signal)}</span>
        <h3>Catatan Risiko Sinyal</h3>
      </div>

      <p>
        ${escapeHtml(signalText)}
        Hasil ini tidak menjamin arah harga berikutnya dan bukan rekomendasi investasi final.
        Interpretasi sinyal perlu dibaca bersama metrik evaluasi, jumlah sinyal, kondisi pasar,
        serta risiko lain seperti volatilitas, likuiditas, berita, biaya transaksi, dan slippage.
      </p>

      <p class="signal-risk-disclaimer">
        Disclaimer: Sistem ini hanya berfungsi sebagai alat bantu analisis teknikal.
        Keputusan investasi sepenuhnya berada pada pengguna.
      </p>
    </section>
  `;
}

  function setReportStatus(message = '', isError = false) {
    if (!reportStatus) return;
    reportStatus.textContent = message;
    reportStatus.classList.toggle('error', isError);
  }

  function hintTermClass(term) {
  const normalized = String(term || '').trim().toUpperCase();

  if (normalized === 'BUY') return 'hint-buy';
  if (normalized === 'SELL') return 'hint-sell';
  if (normalized === 'HOLD') return 'hint-hold';
  if (normalized === 'DIRECTIONAL ACCURACY') return 'hint-primary';
  if (normalized === 'AVERAGE FORWARD RETURN') return 'hint-primary';

  return '';
}

function renderHintList(items) {
  return `
    <dl class="hint-list">
      ${items.map((item) => `
        <div class="hint-item ${hintTermClass(item.term)}">
          <dt class="hint-term">${escapeHtml(text(item.term))}</dt>
          <dd class="hint-description">${escapeHtml(text(item.description, ''))}</dd>
        </div>
      `).join('')}
    </dl>
  `;
}

  function renderTechnicalHint(hint) {
    const target = $('#technical-hint');
    const items = Array.isArray((hint || {}).items) ? hint.items : [];
    const metricItems = Array.isArray((hint || {}).metric_items) ? hint.metric_items : [];

    if (!target) return;

    if (!items.length && !metricItems.length) {
      target.innerHTML = '';
      return;
    }

    target.innerHTML = `
      <p class="eyebrow">Hint Istilah Teknikal</p>
      <h3>${escapeHtml(text(hint.title, 'Hint istilah teknikal'))}</h3>
      ${items.length ? `
        <h4 class="hint-heading">Istilah indikator</h4>
        ${renderHintList(items)}
      ` : ''}
      ${metricItems.length ? `
        <h4 class="hint-heading">Metrik evaluasi</h4>
        ${renderHintList(metricItems)}
      ` : ''}
    `;
  }

  

  // PDF download
  function reportFilename(analysis) {
    const ticker = text((analysis || {}).ticker, 'saham').replace(/[^a-z0-9_-]/gi, '') || 'saham';
    const latestDate = text((analysis || {}).latest_date, 'terbaru').replace(/[^a-z0-9_-]/gi, '') || 'terbaru';
    return `laporan-analisis-${ticker}-${latestDate}.pdf`;
  }

  async function downloadReport() {
    // Build the PDF from the latest API payload already displayed on screen.
    if (!lastAnalysisPayload || !lastAnalysisPayload.analysis) {
      setReportStatus('Hasil analisis belum tersedia untuk diunduh.', true);
      return;
    }

    if (downloadReportButton) downloadReportButton.disabled = true;
    setReportStatus('Menyiapkan laporan PDF...');

    try {
      const response = await fetch('/api/report/pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          analysis: lastAnalysisPayload.analysis,
          explanation: lastAnalysisPayload.explanation
        })
      });

      if (!response.ok) {
        setReportStatus('Laporan PDF belum dapat dibuat. Silakan coba lagi.', true);
        return;
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = reportFilename(lastAnalysisPayload.analysis);
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setReportStatus('Laporan PDF berhasil diunduh.');
    } catch {
      setReportStatus('Koneksi ke server bermasalah saat membuat PDF.', true);
    } finally {
      if (downloadReportButton) downloadReportButton.disabled = false;
    }
  }

  // Result rendering
  function render(body) {
    // Render only the API payload; no frontend recalculation is performed.
    const analysis = body.analysis || {};
    const metrics = analysis.metrics || {};
    const comparison = Array.isArray(analysis.indicator_comparison)
      ? analysis.indicator_comparison
      : [];

    const signal = text(analysis.latest_signal, 'HOLD');
    const analysisSector = text(analysis.sector || analysis.sektor, '').trim();
    const comparisonTitle = `Perbandingan indikator sektor${analysisSector ? ` ${analysisSector}` : ''}`;

    const comparisonDescription =
      text(
        analysis.best_indicator_basis,
        'Indikator terbaik dipilih dari hasil gabungan pengujian Out-of-Sample pada window WFA ketika indikator tersebut terpilih dari In-Sample.'
      ) +
      ' Hit Rate, Active, dan Correct digunakan sebagai metrik pendukung untuk membaca rata-rata keberhasilan dan jumlah sinyal.';

    renderTechnicalHint(analysis.technical_hint);
    setReportStatus();

    const bestIndicator = String(analysis.best_indicator || '').trim().toLowerCase();

const rows = comparison.map((item) => {
  const indicatorName = text(item.indicator, '');
  const isBestIndicator = String(indicatorName).trim().toLowerCase() === bestIndicator;

  return `
    <tr class="${isBestIndicator ? 'is-best-indicator' : ''}">
      <td>
        <div class="indicator-cell">
          <span>${escapeHtml(indicatorName)}</span>
          ${isBestIndicator ? '<span class="best-indicator-badge">Terbaik</span>' : ''}
        </div>
      </td>
      <td>${percent(item.directional_accuracy)}</td>
      <td>${percent(item.hit_rate)}</td>
      <td>${number(item.total_active_signals)}</td>
      <td>${number(item.correct_signals)}</td>
    </tr>
  `;
}).join('') || '<tr><td colspan="5">Data perbandingan belum tersedia.</td></tr>';

    $('#result-numerical').innerHTML = `
      <div class="result-stack">
        <section class="result-card">
          <div class="result-top">
            <div>
              <h2>
                ${escapeHtml(text(analysis.ticker))}
                <span class="signal ${signalClass(signal)}">${escapeHtml(signal)}</span>
              </h2>
              <p class="result-meta">
                ${escapeHtml(text(analysis.stock_name, analysis.sector))} · Sektor ${escapeHtml(text(analysis.sector))}
              </p>
            </div>
            <p class="result-meta">
              Data terakhir<br>
              <strong>${escapeHtml(text(analysis.latest_date))}</strong>
            </p>
          </div>

          <div class="summary-grid">
            <div class="summary-item summary-item-price">
              <span>Harga penutupan terakhir</span>
              <strong>${money(analysis.latest_close)}</strong>
            </div>
            <div class="summary-item summary-item-best-indicator">
              <span>Indikator terbaik sektor</span>
              <strong>${escapeHtml(text(analysis.best_indicator))}</strong>
            </div>
            <div class="summary-item summary-item-last-signal ${lastActiveSignalToneClass(analysis)}">
              <span>Sinyal aktif terakhir</span>
              <strong>${formatLastActiveSignal(analysis)}</strong>
            </div>
            <div class="summary-item summary-item-condition ${toneClass(signal)}">
              <span>Kondisi teknikal</span>
              <strong class="condition-lines condition-compact">
                ${formatCompactTechnicalCondition(analysis)}
              </strong>
            </div>
          </div>
        </section>

        <section class="result-card">
          <h3 class="metrics-title">Metrik evaluasi indikator terbaik</h3>
          <div class="metric-grid">
            ${analysis.metric_quality_note && analysis.metric_quality_note.message ? `
            <p class="metrics-description metric-quality-note">
              ${escapeHtml(analysis.metric_quality_note.message)}
            </p>
          ` : ''}
            <div class="metric metric-primary">
              <span>Directional Accuracy</span>
              <strong>${percent(metrics.directional_accuracy)}</strong>
              <small>Dasar pemilihan indikator terbaik</small>
            </div>
            <div class="metric">
              <span>Hit Rate</span>
              <strong>${percent(metrics.hit_rate)}</strong>
            </div>
            <div class="metric">
              <span>Total Active Signals</span>
              <strong>${number(metrics.total_active_signals)}</strong>
            </div>
            <div class="metric">
              <span>Correct Signals</span>
              <strong>${number(metrics.correct_signals)}</strong>
            </div>
          </div>
        </section>

        ${renderPostSignalValidation(analysis)}

        ${renderSignalRiskNote(analysis)}

        <section class="result-card">
          <h3 class="metrics-title">Grafik harga penutupan</h3>
          ${chart(analysis.chart_data)}
        </section>

        <section class="result-card">
          <h3 class="metrics-title">${escapeHtml(comparisonTitle)}</h3>
          <p class="metrics-description">${escapeHtml(comparisonDescription)}</p>
          <div class="chart-wrap">
            <table class="comparison-table">
              <thead>
                <tr>
                  <th>Indikator</th>
                  <th>Directional Accuracy</th>
                  <th>Hit Rate</th>
                  <th>Active</th>
                  <th>Correct</th>
                </tr>
              </thead>
              <tbody>${rows}</tbody>
            </table>
          </div>
        </section>
      </div>
    `;
  $('#assistant-explanation').innerHTML = `
    <p class="eyebrow">Penjelasan Asisten</p>
    <h2>Memahami hasil analisis</h2>
    <div class="explanation explanation-structured">
      ${formatStructuredExplanation(body.explanation)}
    </div>
    <p class="disclaimer-box">
      ${escapeHtml(text(
        analysis.disclaimer || (body.llm || {}).disclaimer,
        'Hasil ini merupakan sinyal analisis teknikal, bukan rekomendasi investasi final.'
      ))}
    </p>
  `;
  }

  // Analysis request flow
  async function analyze(value) {
    // Keep /api/analyze contract unchanged: send the user query as JSON.
    clearStatus();
    lastAnalysisPayload = null;
    clearAnalysisSession();

    if (!value) {
      showError('Masukkan kode saham atau pilih saham dari daftar terlebih dahulu.');
      query.focus();
      return;
    }

    setLoading(true);
    setState('processing');

    try {
      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: value })
      });

      const body = await response.json();

      if (!body.success) {
        showError(text(body.message, 'Analisis belum dapat dibuat.'));
        return;
      }

      await completeLoadingSteps();
      await new Promise((resolve) => setTimeout(resolve, 220));

      lastAnalysisPayload = body;
      saveAnalysisSession(body);
      render(body);
      setState('result');

      window.scrollTo({
        top: 0,
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'
      });
    } catch (error) {
      console.error('Analyze/render error:', error);
      showError('Analisis belum dapat ditampilkan. Silakan cek console browser.');
    } finally {
      setLoading(false);
    }
  }

  // Event listeners
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    analyze(query.value.trim() || select.value);
  });

  select.addEventListener('change', () => {
    const value = select.value.trim();
    if (!value) return;
    if (button.disabled) return;

    query.value = '';
    analyze(value);
  });

  if (downloadReportButton) {
    downloadReportButton.addEventListener('click', downloadReport);
  }

  const followupForm = $('#followup-form');
  if (followupForm) {
    followupForm.addEventListener('submit', (event) => {
      event.preventDefault();

      const input = $('#followup-query');
      const value = input.value.trim();

      if (!value) return;

      query.value = value;
      input.value = '';
      analyze(value);
    });
  }

  setLoading(false);
  loadStocks();
  loadSectors();

const restoredPayload = loadAnalysisSession();

if (restoredPayload) {
  lastAnalysisPayload = restoredPayload;
  render(restoredPayload);
  setState('result');
}
})();








