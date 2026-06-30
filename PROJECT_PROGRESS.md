# Project Progress

## Konfigurasi Metode Terkunci

- Periode data: 2024-10-20 sampai 2026-06-23 (exclusive); data efektif terakhir: 2026-06-22.
- WFA: 6,3,3 (`in_sample_months = 6`, `out_sample_months = 3`, `shift_months = 3`).
- Horizon evaluasi: 3 trading days. Cooldown tidak digunakan.
- Indikator final: MA Crossover SMA20/SMA50; MACD 12/26/9 dengan SMA50 trend filter; RSI14 exit ekstrem dengan SMA50 trend filter.
- Metrik: Directional Accuracy, Hit Rate, Total Active Signals, dan Correct Signals.
- HOLD tidak dihitung sebagai active signal.
- Sistem menghasilkan sinyal analisis teknikal, bukan rekomendasi investasi final.

## Ringkasan Hasil WFA Utama

| Sektor | Indikator terbaik |
| --- | --- |
| Energi | RSI |
| Finansial | MA Crossover |
| Industri | MA Crossover |
| Teknologi | MA Crossover |

- Average Best Accuracy: 57.61%.
- Weighted Best Accuracy: 57.56%.
- Total Active Signals: 172.
- Correct Signals: 99.
- Sectors Above 50: 4.
- Window per saham: 4.

## Tahap yang Sudah Selesai

- [x] Tahap 0: Setup Project
- [x] Tahap 1: Mapping Service
- [x] Tahap 2: Data Service
- [x] Tahap 3: Indicator Service
- [x] Tahap 4: Signal Service
- [x] Tahap 5: Metric Service
- [x] Tahap 5.5: Data Collection / Price Cache Builder
- [x] Tahap 6: WFA Service
- [x] Tahap 7: Sector Service
- [x] Tahap 8: Analysis Service
- [x] Tahap 9: LLM Service
- [x] Tahap 10: Flask Routes
- [x] Tahap 11: Frontend
- [ ] Tahap 12: Testing dan Dokumentasi

## File Utama Project

- `app.py`, `requirements.txt`, `README.md`, `.env.example`, `.gitignore`, `PROJECT_PROGRESS.md`, `pytest.ini`.
- `routes/__init__.py`, `routes/main_routes.py`, `routes/api_routes.py`.
- `templates/index.html`, `templates/analysis.html`, `static/css/style.css`, `static/js/main.js`.
- `data/mapping_saham_final.xlsx`.
- `data/price_fetch_report_2024-10-20_2026-06-23.csv`.
- `data/wfa_stock_results_2024-10-20_2026-06-23.csv`.
- `data/wfa_sector_aggregate_2024-10-20_2026-06-23.csv`.
- `data/wfa_best_indicator_by_sector_2024-10-20_2026-06-23.csv`.
- `data/wfa_summary_2024-10-20_2026-06-23.csv`.
- `data/wfa_window_count_2024-10-20_2026-06-23.csv`.
- `services/__init__.py`, `services/mapping_service.py`, `services/data_service.py`, `services/indicator_service.py`, `services/signal_service.py`, `services/metric_service.py`, `services/wfa_service.py`, `services/sector_service.py`, `services/analysis_service.py`, `services/llm_service.py`.
- `scripts/collect_sample_price_data.py`, `scripts/run_wfa_analysis.py`, `scripts/verify_ready_for_stage_8.py`, `scripts/cleanup_experiment_artifacts.py`.
- `tests/test_mapping_service.py`, `tests/test_data_service.py`, `tests/test_indicator_service.py`, `tests/test_signal_service.py`, `tests/test_metric_service.py`, `tests/test_collect_sample_price_data.py`, `tests/test_wfa_service.py`, `tests/test_sector_service.py`, `tests/test_analysis_service.py`, `tests/test_llm_service.py`, `tests/test_flask_routes.py`, `tests/test_frontend_routes.py`.
- `templates/loading.html`, `templates/result.html`.
## Cara Menjalankan Project

```powershell
cd stock_decision_assistant
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

## Cara Menjalankan Analisis WFA

```powershell
python scripts\run_wfa_analysis.py
```

## Cara Verifikasi Kesiapan Tahap 8

```powershell
python scripts\verify_ready_for_stage_8.py
```

## Cara Testing

```powershell
pytest -q
python -m pytest tests/test_mapping_service.py -q
python -m pytest tests/test_data_service.py -q
python -m pytest tests/test_indicator_service.py -q
python -m pytest tests/test_signal_service.py -q
python -m pytest tests/test_metric_service.py -q
python -m pytest tests/test_collect_sample_price_data.py -q
python -m pytest tests/test_wfa_service.py -q
python -m pytest tests/test_sector_service.py -q
python -m pytest tests/test_analysis_service.py -q
python -m pytest tests/test_llm_service.py -q
python -m pytest tests/test_flask_routes.py -q
```

## Catatan Tahap 8

Analysis Service sudah menyatukan mapping, data, indikator, sinyal, hasil WFA sektor, indikator terbaik, sinyal terkini, chart data, dan disclaimer ke dalam output dictionary siap pakai oleh route dan LLM service.

## Catatan Tahap 9

- LLM Service sudah dibuat sebagai lapisan penjelasan bahasa alami di atas Analysis Service.
- Provider utama menggunakan OpenAI GPT-5.4 mini melalui Responses API; fallback deterministic tetap tersedia.
- Fallback digunakan bila API tidak aktif, API key kosong, provider bukan OpenAI, package OpenAI tidak tersedia, terjadi API error, atau output LLM tidak memenuhi guardrail.
- LLM Service hanya menjelaskan hasil deterministik dari Analysis Service: tidak menghitung ulang indikator, tidak mengubah sinyal, metrik, indikator terbaik, maupun hasil WFA.
- `chart_data` tidak dikirim ke LLM.
- Output dibatasi dengan `OPENAI_MAX_OUTPUT_TOKENS=700`.
- Output menggunakan bahasa natural dan tidak menampilkan istilah internal kode seperti `formatted_metrics`, `latest_condition`, `analysis_result`, `indicator_comparison`, `latest_signal`, `best_indicator`, `wfa_config`, `data_period`, atau `chart_data`.
- Output menyertakan disclaimer bahwa hasil adalah bantuan analisis teknikal dan bukan rekomendasi investasi final.
- Input prompt LLM sudah dioptimasi menjadi payload ringkas dan natural.
- Context LLM tidak lagi mengirim object mentah seperti `metrics`, `indicator_comparison`, `wfa_config`, `data_period`, atau `chart_data`.
- Prompt input smoke test turun dari sekitar 930 token menjadi sekitar 758 input token.
- Guardrail tetap dipertahankan agar LLM tidak mengubah sinyal, metrik, indikator terbaik, atau hasil WFA.

## Catatan Tahap 10

- Flask Routes sudah menghubungkan endpoint web/API dengan Analysis Service dan LLM Service.
- Endpoint `/api/analyze` menerima input `query` atau `ticker`.
- Untuk input valid, endpoint mengembalikan `analysis`, `llm`, `explanation`, `message`, dan `success`.
- Untuk input tidak valid atau kode saham tidak dikenali, endpoint mengembalikan `success: false` tanpa crash.
- Pada input analisis gagal, OpenAI tidak dipanggil dan sistem memakai deterministic fallback dengan `fallback_reason: analysis_failed`.
- Route tidak mengubah sinyal, metrik, indikator terbaik, hasil WFA, atau disclaimer.
- Route tidak menjalankan WFA ulang dan tidak melakukan refresh data otomatis.
- Endpoint `/api/stocks` menyediakan daftar saham sampel.
- Endpoint `/api/sectors` menyediakan daftar sektor dan jumlah saham per sektor.
- Endpoint `/api/health` menyediakan status backend.

## Catatan Tahap 11

- Frontend dibuat dengan Flask template, CSS, dan JavaScript vanilla menggunakan tema Light Professional Finance.
- Landing page dipisahkan dari halaman analisis melalui route `/analysis`.
- Halaman analisis dimulai dari full chatbot/input page dan memuat daftar saham dari endpoint Flask.
- Setelah input dikirim, frontend menampilkan processing state visual tanpa menjalankan WFA ulang.
- Setelah hasil tersedia, frontend menampilkan dashboard responsif: hasil numerik di kiri serta panel Penjelasan Asisten dan input lanjutan di kanan pada desktop.
- Frontend memakai endpoint `/api/stocks`, `/api/sectors`, dan `/api/analyze`; frontend tidak menghitung ulang atau mengubah hasil deterministik.
- Revisi visual memperkuat landing editorial dan conversational workspace, progress state, keterbacaan penjelasan, serta micro-interactions yang menghormati reduced motion.
- UI /analysis dipoles menjadi conversational workspace minimal dengan composer sebagai fokus utama.
- Loading state dan transisi hasil dibuat lebih halus; landing page memakai aksen Warm Editorial Finance yang tetap profesional.
- Frontend tetap tidak mengubah hasil deterministik, WFA, indikator, metrik, maupun LLM Service.
- Patch visual final menghapus dekorasi lingkaran outline dari landing dan workspace analisis, sambil mempertahankan background Warm Editorial Finance yang halus.
## Tahap Berikutnya

Tahap 12: Testing dan Dokumentasi.

Frontend akan menggunakan endpoint Flask untuk menampilkan halaman utama, input analisis saham, hasil analisis terstruktur, grafik, metrik evaluasi, sinyal teknikal, dan penjelasan bahasa alami dari LLM Service.









### Revisi Lanjutan Tahap 11

- Initial state /analysis disederhanakan menjadi conversational workspace: greeting, composer utama, dropdown compact, dan ringkasan sektor.
- Composer menjadi fokus utama dengan tombol kirim icon-only dan dukungan submit melalui Enter.
- Loading progress kini bergerak satu arah, berhenti pada langkah terakhir, lalu menampilkan hasil setelah jeda singkat.
- Background memakai Editorial Finance gradient dengan aurora halus yang mengikuti prefers-reduced-motion.
- Backend, API, service, WFA, indikator, metrik, serta kontrak JSON tidak diubah.
### Revisi Mapping dan Template Tahap 11

- State loading dan result dipisahkan menjadi partial template `loading.html` dan `result.html`, lalu dipanggil melalui `analysis.html`.
- Mapping Service diperluas dengan resolver deterministik untuk mengenali ticker, nama perusahaan, dan alias saham terkurasi.
- Endpoint `/api/stocks` sekarang mengembalikan `stock_name` agar dropdown dapat menampilkan format ticker, nama perusahaan, dan sektor.
- Dropdown saham pada frontend menampilkan format `BBCA — Bank Central Asia — Finansial`, dengan value tetap berupa ticker.
- Input seperti `analisis bank bca`, `Bank Central Asia`, `analisis bank mandiri`, `analisis goto`, dan `perusahaan gas negara` dapat dikenali tanpa melibatkan LLM.
- Perubahan ini tidak mengubah pipeline analisis teknikal, WFA, metrik, sinyal, LLM Service, maupun CSV hasil evaluasi.
- Verifikasi terakhir: `pytest -q` menghasilkan 155 passed.
### Revisi Final Hint dan PDF

- State loading dan result sudah dipisahkan menjadi partial template `loading.html` dan `result.html`.
- Sistem kini memiliki hint istilah teknikal deterministik sesuai indikator terbaik melalui `services/technical_hint_service.py`.
- Hint tidak dibuat oleh LLM dan hanya menampilkan istilah yang relevan dengan indikator terbaik.
- Sistem kini memiliki fitur download laporan PDF untuk hasil analisis offline melalui endpoint `/api/report/pdf` dan `services/report_service.py`.
- PDF dibuat dari hasil analisis yang sudah tersedia di frontend dan tidak menjalankan WFA ulang.
- PDF tidak memanggil Analysis Service, LLM Service, OpenAI, atau proses refresh data.
- Verifikasi terakhir setelah implementasi: `pytest -q` menghasilkan 164 passed.

### Polish Laporan PDF

- Laporan PDF dipoles menjadi format lebih formal dengan header, tanggal cetak, tabel rapi, disclaimer box, dan footer bernomor halaman.
- Tabel Informasi Saham, Ringkasan Hasil, Metrik Evaluasi, Perbandingan Indikator, dan Hint Istilah Teknikal tetap memakai data dari payload yang sudah tersedia.
- Report service tetap tidak memanggil Analysis Service, LLM Service, OpenAI, WFA, atau proses teknikal ulang.
- Verifikasi terakhir setelah polish PDF: `pytest -q` menghasilkan 166 passed.
- Dependency proyek dirapikan dengan pinning dependency turunan agar tidak muncul warning pada saat pengujian.
- Verifikasi terakhir: `pytest -q` menghasilkan 166 passed tanpa warning.
### Cleanup Kode dan Dokumentasi Alur

- Dependency runtime diselaraskan dengan pin `requirements.txt` sehingga warning dependency tidak muncul saat pengujian.
- Smooth transition antar state halaman analisis sudah ditambahkan dan dipertahankan tanpa mengubah kontrak frontend/API.
- `sector_service.py` dan `wfa_service.py` dirapikan agar alur agregasi sektor dan fixed-length rolling WFA lebih mudah dibaca.
- `llm_service.py`, `report_service.py`, `api_routes.py`, dan `main.js` diberi komentar/docstring alur pada fungsi penting tanpa mengubah behavior sistem.
- Cleanup kode dan dokumentasi alur fungsi dilakukan tanpa mengubah backend, API, WFA, indikator, metrik, sinyal, LLM, PDF, frontend output, atau data hasil evaluasi.
- Verifikasi terakhir setelah cleanup: `pytest -q` menghasilkan 166 passed tanpa warning dependency.
