# 🏭 Coal Capital Club
Start Workflows: 
https://github.com/CoalHunter/ccc/actions/workflows/daily.yml

website: https://coalhunter.github.io/ccc

**Exclusive Swing Trading Intelligence for Indonesian Coal Giants**

Sistem analisis otomatis untuk **ITMG** dan **PTBA** menggunakan konfluensi 10 indikator teknikal + deteksi akumulasi bandar.

## 🎯 Filosofi

Entry hanya valid jika **minimal 6 dari 10 indikator** memberi sinyal bullish di area yang sama. Ini meningkatkan win-rate secara signifikan dan mengurangi false signal.

## 📊 10 Indikator Konfluensi

| # | Indikator | Bobot | Fungsi |
|---|-----------|-------|--------|
| 1 | RSI (14) | 12 | Oversold detection |
| 2 | RSI Divergence | 10 | Bullish divergence |
| 3 | Bollinger %B | 12 | Posisi dalam band |
| 4 | MACD Momentum | 10 | Percepatan bullish |
| 5 | Volume Accumulation | 15 | Deteksi bandar |
| 6 | ATR Squeeze | 8 | Volatilitas rendah |
| 7 | Multi-MA Ribbon | 10 | Dynamic support |
| 8 | Pivot Support | 10 | Support klasik |
| 9 | Fibonacci | 8 | Level kunci |
| 10 | Weekly Alignment | 5 | Konfirmasi trend |

## 🚀 Cara Deploy

1. Fork repo ini
2. Enable GitHub Actions
3. Workflow akan auto-run setiap hari jam 16:30 WIB (setelah market close)
4. Hasil analisis otomatis di-commit ke `data/result.json`
5. Deploy `index.html` ke GitHub Pages / Netlify / Vercel

## ⚙️ Konfigurasi

Edit `config.json` untuk mengubah:
- Daftar saham
- Parameter indikator
- Risk-reward ratio
- Threshold skor

## ⚠️ Disclaimer

Ini BUKAN nasihat keuangan. Selalu lakukan riset mandiri, kelola risiko, dan jangan all-in. Past performance ≠ future results.

## 🛠️ Tech Stack

- Python 3.11+ (yfinance, pandas, numpy)
- HTML5 + CSS3 + Vanilla JS
- GitHub Actions (automation)
- Yahoo Finance API (data)

---

Built with ⚡ by Sabda
