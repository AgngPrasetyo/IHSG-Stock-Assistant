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


  function setReportStatus(message = '', isError = false) {
    if (!reportStatus) return;
    reportStatus.textContent = message;
    reportStatus.classList.toggle('error', isError);
  }

  function renderHintList(items) {
    return `
      <dl class="hint-list">
        ${items.map((item) => `
          <div class="hint-item">
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
    const analysisTicker = text(analysis.ticker, '').trim();
    const comparisonTitle = `Perbandingan indikator sektor${analysisSector ? ` ${analysisSector}` : ''}`;
    const comparisonDescription = `Indikator terbaik ditentukan dari hasil evaluasi sektor ${analysisSector || 'terkait'}, sehingga hasil ini tidak hanya merepresentasikan performa individual saham ${analysisTicker || 'ini'}.`;
    renderTechnicalHint(analysis.technical_hint);
    setReportStatus();

    const rows = comparison.map((item) => `
      <tr>
        <td>${escapeHtml(text(item.indicator))}</td>
        <td>${percent(item.directional_accuracy)}</td>
        <td>${percent(item.hit_rate)}</td>
        <td>${number(item.total_active_signals)}</td>
        <td>${number(item.correct_signals)}</td>
      </tr>
    `).join('') || '<tr><td colspan="5">Data perbandingan belum tersedia.</td></tr>';

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
            <div class="summary-item">
              <span>Harga penutupan terakhir</span>
              <strong>${money(analysis.latest_close)}</strong>
            </div>
            <div class="summary-item">
              <span>Indikator terbaik sektor</span>
              <strong>${escapeHtml(text(analysis.best_indicator))}</strong>
            </div>
            <div class="summary-item">
              <span>Kondisi teknikal</span>
              <strong>${escapeHtml(text(analysis.latest_condition))}</strong>
            </div>
          </div>
        </section>

        <section class="result-card">
          <h3 class="metrics-title">Metrik evaluasi indikator terbaik</h3>
          <div class="metric-grid">
            <div class="metric">
              <span>Directional Accuracy</span>
              <strong>${percent(metrics.directional_accuracy)}</strong>
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
      <div class="explanation">${formatExplanation(body.explanation)}</div>
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
      render(body);
      setState('result');

      window.scrollTo({
        top: 0,
        behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'
      });
    } catch {
      showError('Koneksi ke server bermasalah. Silakan coba lagi.');
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
    if (select.value) query.value = '';
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
})();









