# Stock Decision Assistant

Aplikasi web untuk skripsi:

**Rancang Bangun Asisten Pendukung Keputusan Analisis Teknikal Saham Sektoral menggunakan Fixed-Length Rolling Walk-Forward Analysis dan LLM**

Stock Decision Assistant adalah aplikasi web berbasis Flask yang membantu pengguna memahami hasil analisis teknikal saham secara lebih terstruktur. Sistem menyajikan indikator teknikal terbaik berdasarkan evaluasi sektoral, sinyal analisis BUY/SELL/HOLD, metrik evaluasi, grafik harga penutupan, ringkasan hasil analisis, hint istilah teknikal, dan laporan PDF.

Output BUY, SELL, atau HOLD harus dipahami sebagai sinyal analisis teknikal, bukan rekomendasi investasi final.

## Status Project

Versi saat ini sudah mencakup:

- Web app Flask dengan landing page dan halaman analisis.
- Input saham melalui kode, nama emiten, atau alias saham.
- Mapping saham untuk 40 sampel dari 4 sektor BEI.
- Analisis teknikal menggunakan MA Crossover, MACD, dan RSI.
- Evaluasi indikator menggunakan Fixed-Length Rolling Walk-Forward Analysis.
- Pemilihan indikator terbaik berdasarkan evaluasi sektoral.
- Dashboard hasil analisis.
- Ringkasan hasil berbasis LLM atau fallback deterministik.
- Hint istilah teknikal dan metrik evaluasi.
- Unduh laporan hasil analisis dalam format PDF.


173 passed
