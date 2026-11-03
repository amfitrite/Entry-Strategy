# Entry Strategy Matrix Studio — XAUUSD M1/M5

Engine entry berbasis **completed OHLC candles** untuk XAUUSD, dengan feed historis dan live Dukascopy. Aplikasi tetap standalone dan tidak membutuhkan MT4/MT5 atau EA.

## Prinsip analisis

- Seluruh 40 strategi mengevaluasi candle timeframe aktif: **M1 atau M5**.
- Sinyal baru diputuskan setelah candle selesai. Wick/intrabar yang belum ditutup tidak boleh memicu entry.
- **Tidak ada strategi tick, tick imbalance, tick velocity, tick burst, atau tick acceleration.** Modul tick-only telah dihapus.
- Stream bid/ask tetap boleh dipakai untuk quote, estimasi harga eksekusi BUY/SELL, dan pembaruan lifecycle sinyal. Stream tersebut tidak boleh menjadi pemicu pola entry.
- M1 dan M5 memiliki buffer terpisah. Perpindahan timeframe mengganti konteks evaluasi; data M1 tidak boleh mencampuri M5 dan sebaliknya.

## Katalog 40 strategi

| ID | Strategi | Kelompok | Definisi pemicu ringkas |
|---:|---|---|---|
| 1 | Candlestick Reversal | Candle | Engulfing bullish/bearish |
| 2 | Candlestick Continuation | Candle | Three White Soldiers / Three Black Crows |
| 3 | Multi-Candle Reversal | Candle | Reversal dua candle dengan konfirmasi body |
| 4 | Inside Bar Breakout | Candle | Break close dari mother bar setelah inside-bar setup |
| 5 | Outside Bar | Candle | Outside bar diikuti continuation |
| 6 | Momentum Candle | Candle | Ekspansi range dan body dominan |
| 7 | Breakout | Price Action | Close melewati high/low candle referensi |
| 8 | Failed Breakout / Sweep & Reclaim | Price Action | Wick sweep level lalu close reclaim |
| 9 | Micro Pullback | Price Action | Retracement impuls dan close kembali searah |
| 10 | Micro Trend Reversal | Structure | Perubahan swing lokal dan close break |
| 11 | **CHoCH** | Structure | Close menembus protected swing melawan struktur tren sebelumnya |
| 12 | **BOS** | Structure | Close menembus swing searah struktur HH/HL atau LH/LL |
| 13 | **Candle Displacement** | Price Action | Range/body ekspansif dan close di luar range lokal |
| 14 | **Breakout Retest** | Price Action | Breakout close, retest level, lalu close mempertahankan level |
| 15 | **Fair Value Gap (FVG)** | Price Action | Inefisiensi tiga candle setelah displacement |
| 16 | **FVG Retest** | Price Action | Retest zona FVG dan rejection close |
| 17 | **Order Block Retest** | Price Action | Retest candle lawan terakhir sebelum displacement dan break |
| 18 | Micro Range Expansion | Price Action | Range candle mengembang dibanding bar sebelumnya |
| 19 | Micro Range Compression | Price Action | Konsolidasi beberapa candle dan close breakout |
| 20 | Volatility Burst (OHLC) | Price Action | Range melebar, body dominan, close dekat ekstrem |
| 21 | Volatility Contraction | Candle | Penyusutan range beberapa candle |
| 22 | Trend Pullback | Price Action | Pullback pada HH/HL atau LH/LL lalu close continuation |
| 23 | Donchian Range Breakout | Price Action | Close keluar dari range high/low multi-candle |
| 24 | Rejection Pattern | Candle | Wick rejection pada ekstrem candle |
| 25 | Wick Pattern | Candle | Pin bar / hammer / shooting star |
| 26 | Body Expansion | Candle | Body candle membesar berturut-turut |
| 27 | Body Contraction | Candle | Body candle mengecil berturut-turut |
| 28 | Gap Pattern | Candle | Gap harga antar candle |
| 29 | Failed Momentum | Price Action | Impuls gagal dipertahankan dan close berbalik |
| 30 | Momentum Exhaustion | Price Action | Impuls besar kehilangan follow-through |
| 31 | Micro Double Top | Structure | Dua puncak sejajar dan bearish close rejection |
| 32 | Micro Double Bottom | Structure | Dua lembah sejajar dan bullish close rejection |
| 33 | Micro Swing Break | Structure | Close menembus swing lima candle |
| 34 | Micro Swing Failure | Structure | Wick sweep swing lalu close kembali ke dalam |
| 35 | Three-Push Pattern | Structure | Tiga dorongan melemah dan candle close membalik struktur |
| 36 | V-Reversal | Candle | Kejatuhan diikuti bullish recovery candle |
| 37 | Inverted V-Reversal | Candle | Reli diikuti bearish reversal candle |
| 38 | Staircase Pattern | Candle | Urutan higher-high/higher-low atau lower-high/lower-low |
| 39 | Candle Sequence | Candle | Urutan multi-candle yang membentuk reversal |
| 40 | Candle Rejection Confluence | Candle | Rejection wick dan follow-through candle berikutnya |

Strategi 11–17, 22–23 menggantikan slot yang sebelumnya khusus tick-based. ID tetap dipertahankan agar matriks, API, dan penyimpanan sinyal tetap kompatibel.

## Lifecycle sinyal

Sinyal yang sudah lahir disimpan dan bergerak melalui status:

`ACTIVE → PENDING_CONFIRMATION → CONFIRMED`

atau berakhir melalui `INVALIDATED` / `EXPIRED`.

Setiap sinyal mencatat alasan pemicu, reference price, trigger price, estimasi execution price, invalidation level, timeframe, dan event ID. Penutupan candle berikutnya yang tidak memenuhi pola tidak otomatis menghapus sinyal sebelumnya.

## Menjalankan aplikasi

```bash
python run_app.py
```

Atau jalankan `run_app.bat` pada Windows. Timeframe default adalah M5; M1 tersedia melalui pilihan timeframe.

## Pengujian

```bash
python -m pytest tests -v
```

Suite regresi telah disesuaikan untuk strategi candle-only, termasuk struktur CHoCH/BOS, displacement, breakout-retest, FVG, order-block retest, pullback, Donchian breakout, dan larangan akses tick dari strategi.

**Catatan validasi:** pembaruan strategi ini belum membuktikan profitabilitas. Sebelum digunakan untuk keputusan live, jalankan seluruh pytest dan lakukan backtest/walk-forward pada data historis Dukascopy untuk M1 dan M5 secara terpisah. Periksa juga frekuensi sinyal, spread/slippage, invalidation distance, dan hasil BUY/SELL agar aturan yang terlihat simetris benar-benar teruji.
