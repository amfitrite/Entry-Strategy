# ⚡ Entry Strategy Matrix Studio

Aplikasi Kumpulan Pola Entry Strategi Agnostik berkinerja tinggi untuk XAUUSD dan multi-aset. Terhubung langsung dengan streaming tick dan agregasi candle MT5 melalui TCP Bridge pada **Port 5558**.

---

## 🌟 Fitur Utama

1. **Agnostik Pasar Murni (Pure Deterministic Engine):**
   - Tidak tergantung pada SNR, Support/Demand makro, atau indikator lagging.
   - Evaluasi murni berbasis kondisi matematis tertutup: setiap pola dievaluasi secara independen pada jendela tick dan candle.
2. **Katalog Lengkap 40 Keluarga Strategi Entry:**
   - 12 Pola Pure Candlestick (Engulfing, Three Soldiers, Inside/Outside Bar, Wick Rejection, dll).
   - 9 Pola Pure Tick Microstructure (Tick Momentum, Tick Imbalance, Tick Burst, Tick Exhaustion, Price Velocity, dll).
   - 14 Pola Hybrid Tick-Candle (Breakout, Failed Breakout/Fakeout, Micro Pullback, V-Reversal, dll).
   - 5 Pola Micro-Swing Geometry (Micro Double Top/Bottom, Micro Swing Break/Failure, Three-Push Pattern).
3. **Desain UI Sederhana & Padat (Dense Matrix View):**
   - Seluruh 40 keluarga strategi tampil **dalam satu layar penuh tanpa perlu scroll**.
   - Indikator warna minimalis dan jelas:
     - **Abu-abu gelap (IDLE):** Menunggu kondisi.
     - **HIJAU NEON BOLD:** Sinyal **BUY** aktif.
     - **MERAH NEON BOLD:** Sinyal **SELL** aktif.
   - Efek kedipan (*flash pulse*) saat sinyal baru terpicu.
4. **On-Demand Detail Pop-up Modal:**
   - Cukup **klik kartu strategi manapun** untuk membuka pop-up yang merinci alasan matematis (*reason checklist*), harga trigger, spread saat entry, dan timestamp akurat hingga milidetik.
5. **Dual-Mode Bridge:**
   - **Mode Live MT5:** Mendengarkan koneksi EA MT5 di socket port `5558`.
   - **Mode Simulator Bawaan:** Otomatis aktif saat MT5 belum terhubung, sehingga visual dan deteksi pola langsung dapat dilihat dan diuji.

---

## 🚀 Cara Menjalankan

### 1. Jalankan Aplikasi
Jalankan file batch:
```cmd
run_app.bat
```
atau via terminal:
```bash
python run_app.py
```

### 2. Hubungkan ke MT5 (Port 5558)
1. Salin script EA dari folder `mql5/EntryStrategy_Bridge_5558.mq5` ke direktori MT5 Anda (`MQL5/Experts/`).
2. Buka MetaEditor, tekan **Compile (F7)**.
3. Lampirkan EA ke chart **XAUUSD** (M1 atau timeframe apapun).
4. Pastikan opsi **Allow WebRequest / Socket** aktif.
5. Begitu terhubung, indikator di header aplikasi akan otomatis berubah menjadi **PORT 5558 LIVE** (Hijau).

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
| 7 | **Breakout** | Hybrid | Penembusan High/Low candle bar sebelumnya dengan laju tick |
| 8 | **Failed Breakout** | Hybrid | Fakeout/Trap: Tembus high/low lalu ditarik balik dalam tempo singkat |
| 9 | **Micro Pullback** | Hybrid | Retracement 50% body bar momentum disusul rebound searah |
| 10 | **Micro Trend Reversal** | Hybrid | Patahnya tren lokal 3 bar oleh akselerasi tick bar berjalan |
| 11 | **Tick Momentum** | Tick | Akumulasi pergeseran harga dalam jendela tick mikro |
| 12 | **Tick Reversal** | Tick | Pembalikan cepat arah tick (V-Shape tick micro) |
| 13 | **Tick Imbalance** | Tick | Dominasi $\ge 75\%$ uptick atau downtick dalam 20 tick |
| 14 | **Tick Burst** | Tick | Lonjakan frekuensi transaksi $> 25$ ticks/detik |
| 15 | **Tick Exhaustion** | Tick | Likuiditas terserap: frekuensi tick tinggi namun harga macet |
| 16 | **Price Velocity** | Tick | Kecepatan perpindahan harga per detik ($\Delta P / \Delta t$) |
| 17 | **Price Acceleration** | Tick | Percepatan laju harga ($\Delta V / \Delta t$) |
| 18 | **Micro Range Expansion** | Hybrid | Rentang tick melompat melampaui rata-rata range bar |
| 19 | **Micro Range Compression** | Hybrid | Rentang harga menyempit ketat sebelum ledakan harga |
| 20 | **Volatility Burst** | Hybrid | Lonjakan serentak frekuensi tick dan rentang harga |
| 21 | **Volatility Contraction** | Candle | Penyusutan range candle 3 bar berturut-turut |
| 22 | **Consecutive Price Movement**| Tick | 6 tick berurutan bergerak searah tanpa interupsi |
| 23 | **Alternating Tick Pattern** | Tick | Patahnya osilasi ping-pong tick bolak-balik |
| 24 | **Rejection Pattern** | Hybrid | Penolakan harga cepat di level ekstrem meninggalkan ekor |
| 25 | **Wick Pattern** | Candle | Pin Bar / Hammer: Panjang wick $\ge 60\%$ total rentang |
| 26 | **Body Expansion** | Candle | Body candle membesar berturut-turut $> 20\%$ per bar |
| 27 | **Body Contraction** | Candle | Body candle mengecil berturut-turut (exhaustion fade) |
| 28 | **Gap Pattern** | Hybrid | Lompatan harga antar candle atau antar tick berturut-turut |
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
| 40 | **Hybrid Tick-Candle** | Hybrid | Sinergi candle rejection dikonfirmasi oleh tick imbalance |

---

## 🧪 Pengujian & Unit Test

Untuk menjalankan seluruh rangkaian automated unit test (72 test suite: verifikasi 40 pola, akurasi rumus, proteksi data kosong, siklus hidup sinyal, pemisahan buffer M1/M5, simetri BUY/SELL, dan socket TCP port 5558):
```bash
python -m pytest tests -v
```

Laporan audit konseptual mendalam dan verifikasi teknis arsitektur 40 strategi dapat dibaca di:
👉 [`docs/AUDIT_KONSEPTUAL_40_STRATEGI.md`](docs/AUDIT_KONSEPTUAL_40_STRATEGI.md)
