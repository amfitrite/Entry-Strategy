# ⚡ Entry Strategy Matrix Studio (Dukascopy Live)

Aplikasi Kumpulan Pola Entry Strategi Agnostik berkinerja tinggi untuk **XAUUSD (Gold)**. Beroperasi **100% mandiri (standalone)** tanpa ketergantungan pada MetaTrader 5 atau software eksternal, ditenagai langsung oleh data real-time dan historis institusional dari **Dukascopy Bank ECN Marketplace (Geneva, Swiss)**.

---

## 🌟 Fitur Utama

1. **100% Standalone (Bebas MT5 & Zero Setup):**
   - Tidak lagi membutuhkan MetaTrader 5, socket TCP lokal port 5558, ataupun instalasi EA MQL5.
   - Cukup jalankan aplikasi dengan Python, feed pasar XAUUSD langsung streaming dari Dukascopy Bank.

2. **Instant Warm-up (100 Candle M5 Otomatis):**
   - Mengatasi masalah *cold start*: saat aplikasi dinyalakan, modul langsung mengunduh **100 candle M5 terakhir** (< 1 detik).
   - Seluruh 40 strategi entry langsung terisi konteks pasar dan siap memicu sinyal sejak detik pertama.

3. **Agnostik Pasar Murni (Pure Deterministic Engine):**
   - Tidak tergantung pada SNR makro, Support/Demand harian, atau indikator lagging.
   - Evaluasi murni berbasis kondisi matematis tertutup pada jendela candle M5 (dengan opsi M1).

4. **Katalog Lengkap 40 Keluarga Strategi Entry:**
   - 12 Pola Pure Candlestick (Engulfing, Three Soldiers, Inside/Outside Bar, Wick Rejection, dll).
   - 9 Pola Pure Microstructure (Displacement, Velocity, Imbalance, Exhaustion, dll).
   - 14 Pola Hybrid (Breakout, Failed Breakout / Sweep & Reclaim, Micro Pullback, V-Reversal, dll).
   - 5 Pola Micro-Swing Geometry (Micro Double Top/Bottom, Micro Swing Break/Failure, Three-Push Pattern).

5. **Siklus Hidup Sinyal 5 Status (Zero Repainting):**
   - `ACTIVE` $\rightarrow$ `PENDING_CONFIRMATION` $\rightarrow$ `CONFIRMED` $\rightarrow$ `INVALIDATED` / `EXPIRED`.
   - Sinyal tidak menghilang secara keliru saat candle pemicu selesai.

6. **Desain UI Sederhana & Padat (Dense Matrix View):**
   - Seluruh 40 keluarga strategi tampil **dalam satu layar penuh tanpa perlu scroll**.
   - Dilengkapi **Simple Mode** (mini float bar) untuk memantau sinyal saat membuka aplikasi lain.
   - On-Demand Detail Pop-up Modal untuk melihat rincian alasan sinyal, harga trigger, dan invalidation level.

---

## 🚀 Cara Menjalankan

### Jalankan Aplikasi
Jalankan file batch:
```cmd
run_app.bat
```
atau via terminal:
```bash
python run_app.py
```

Aplikasi akan otomatis mengunduh 100 candle M5 XAUUSD terkini dari Dukascopy dan langsung memulai pemindaian sinyal real-time.

---

## 📋 Daftar 40 Keluarga Strategi Entry

| No | Keluarga Strategi | Tipe Data | Deskripsi Singkat Logika |
|:---:|:---|:---:|:---|
| 1 | **Candlestick Reversal** | Candle | Engulfing body rasio $\ge 1.1\times$ bar sebelumnya |
| 2 | **Candlestick Continuation** | Candle | Three White Soldiers / Three Black Crows |
| 3 | **Multi-Candle Reversal** | Candle | Two-Bar Reversal dengan ukuran body seimbang |
| 4 | **Inside Bar** | Candle | Breakout penembusan batas mother bar |
| 5 | **Outside Bar** | Candle | Mother bar menelan bar sebelumnya lalu melanjutkan ekspansi |
| 6 | **Momentum** | Candle | Candle besar dengan body $\ge 70\%$ dan range $> 1.6\times$ avg |
| 7 | **Breakout** | Hybrid | Penembusan High/Low candle bar sebelumnya |
| 8 | **Failed Breakout** | Hybrid | Liquidity Sweep & Reclaim (Trap ekor menyapu level lalu reclaim) |
| 9 | **Micro Pullback** | Hybrid | Retracement 50% body bar momentum disusul rebound searah |
| 10 | **Micro Trend Reversal** | Hybrid | Patahnya tren lokal 3 bar oleh akselerasi bar berjalan |
| 11 | **Momentum Displacement** | Micro | Akumulasi pergeseran harga dalam jendela pergerakan mikro |
| 12 | **V-Reversal Flow** | Micro | Pembalikan cepat arah harga mikro (V-Shape micro) |
| 13 | **Tick Imbalance** | Micro | Dominasi arah tick/bar dalam jendela mikro |
| 14 | **Micro Burst** | Micro | Lonjakan frekuensi transaksi dan rentang harga |
| 15 | **Micro Exhaustion** | Micro | Likuiditas terserap: aktivitas tinggi namun harga terhenti |
| 16 | **Price Velocity** | Micro | Kecepatan perpindahan harga per detik ($\Delta P / \Delta t$) |
| 17 | **Price Acceleration** | Micro | Percepatan laju pergerakan harga ($\Delta V / \Delta t$) |
| 18 | **Micro Range Expansion** | Hybrid | Rentang harga melompat melampaui rata-rata range bar |
| 19 | **Micro Range Compression** | Hybrid | Rentang harga menyempit ketat sebelum ledakan harga |
| 20 | **Volatility Burst** | Hybrid | Lonjakan serentak aktivitas transaksi dan rentang harga |
| 21 | **Volatility Contraction** | Candle | Penyusutan range candle 3 bar berturut-turut |
| 22 | **Consecutive Price Movement**| Micro | 6 bar/tick berurutan bergerak searah tanpa interupsi |
| 23 | **Alternating Pattern** | Micro | Patahnya osilasi harga bolak-balik |
| 24 | **Rejection Pattern** | Hybrid | Penolakan harga cepat di level ekstrem meninggalkan ekor |
| 25 | **Wick Pattern** | Candle | Pin Bar / Hammer: Panjang wick $\ge 60\%$ total rentang |
| 26 | **Body Expansion** | Candle | Body candle membesar berturut-turut $> 20\%$ per bar |
| 27 | **Body Contraction** | Candle | Body candle mengecil berturut-turut (exhaustion fade) |
| 28 | **Gap Pattern** | Hybrid | Lompatan harga antar candle berturut-turut |
| 29 | **Failed Momentum** | Hybrid | Dorongan momentum awal gagal dan berbalik 100% |
| 30 | **Momentum Exhaustion** | Hybrid | Tenaga buyer/seller habis setelah pergerakan panjang |
| 31 | **Micro Double Top** | Swing | Dua puncak lokal sejajar gagal ditembus ke atas |
| 32 | **Micro Double Bottom** | Swing | Dua lembah lokal sejajar gagal ditembus ke bawah |
| 33 | **Micro Swing Break** | Swing | Penembusan swing level 5 bar terakhir |
| 34 | **Micro Swing Failure** | Swing | Kegagalan menembus swing level 5 bar terakhir |
| 35 | **Three-Push Pattern** | Swing | Tiga dorongan bertingkat dengan daya dorong mengecil |
| 36 | **V-Reversal** | Hybrid | Pembalikan cepat berbentuk huruf V |
| 37 | **Inverted V-Reversal** | Hybrid | Pembalikan cepat berbentuk huruf V terbalik |
| 38 | **Staircase Pattern** | Candle | Anak tangga 4 bar berturut-turut searah |
| 39 | **Candle Sequence** | Candle | Urutan khusus (misal Bear-Bear-Doji-Bull) |
| 40 | **Hybrid Candle Synergy** | Hybrid | Sinergi candle rejection dikonfirmasi oleh pergerakan searah |

---

## 🧪 Pengujian & Unit Test

Untuk menjalankan seluruh rangkaian automated unit test (74 test suite: verifikasi 40 pola, akurasi rumus, proteksi data kosong, siklus hidup sinyal, pemisahan timeframe M1/M5, simetri BUY/SELL, dan integrasi Dukascopy Live feed):
```bash
python -m pytest tests -v
```

Laporan audit konseptual mendalam dan verifikasi teknis arsitektur 40 strategi dapat dibaca di:
👉 [`docs/AUDIT_KONSEPTUAL_40_STRATEGI.md`](docs/AUDIT_KONSEPTUAL_40_STRATEGI.md)
