# Stock Decision Assistant

Aplikasi web untuk demo skripsi:

**Rancang Bangun Asisten Pendukung Keputusan untuk Analisis Teknikal Saham Berbasis Large Language Model menggunakan Fixed-Length Rolling Walk-Forward Analysis**

Sistem ini adalah asisten pendukung keputusan untuk analisis teknikal saham. Output BUY, SELL, atau HOLD harus dipahami sebagai sinyal analisis teknikal, bukan rekomendasi investasi final.

## Status

Tahap 0 selesai: setup project awal, struktur folder, virtual environment, dependency list, konfigurasi contoh, dan halaman Flask kosong.

## Teknologi

- Backend: Python Flask
- Frontend: HTML, CSS, JavaScript
- Data saham: Yahoo Finance melalui `yfinance`
- Analisis data: pandas, numpy
- Chart: Plotly
- LLM: OpenAI API

## Cara Menjalankan

Masuk ke folder project:

```bash
cd stock_decision_assistant
```

Aktifkan virtual environment di Windows PowerShell:

```bash
.\.venv\Scripts\Activate.ps1
```

Install dependency:

```bash
pip install -r requirements.txt
```

Jalankan Flask:

```bash
python app.py
```

Buka browser ke:

```text
http://127.0.0.1:5000
```

## Catatan Batasan

- Sistem tidak melakukan prediksi harga saham.
- Sistem tidak melakukan trading otomatis.
- Sistem tidak melakukan eksekusi order.
- Sistem tidak memberi rekomendasi investasi final.
- Perhitungan indikator teknikal akan dilakukan deterministik oleh kode Python, bukan oleh LLM.
- API key tidak boleh di-hardcode. Gunakan file `.env`.
