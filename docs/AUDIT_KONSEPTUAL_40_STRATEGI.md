# Arsitektur Strategi Candle-Only — XAUUSD M1/M5

Dokumen ini menggantikan audit 40 strategi versi sebelumnya. Katalog dan jalur pemicu kini berbasis completed OHLC candles; klaim hasil pengujian dari versi lama tidak berlaku untuk branch ini.

## 1. Prinsip pemicu

1. Satu evaluasi strategi hanya boleh membaca candle yang sudah close pada timeframe aktif (M1 atau M5).
2. Wick pada candle yang sedang berjalan tidak dianggap trigger final.
3. Tick-only patterns telah dihapus. `MarketBuffer.get_recent_ticks()` mengembalikan list kosong dan `latest_tick` selalu `None` untuk jalur analisis.
4. Dukascopy bid/ask stream tetap tersedia untuk quote telemetry, estimasi eksekusi BUY pada Ask / SELL pada Bid, dan pembaruan lifecycle. Quote stream tidak boleh dipakai untuk menghasilkan sinyal pola.
5. Data M1 dan M5 disimpan dalam buffer terpisah.

## 2. Strategi yang menggantikan slot tick-only

| ID | Nama | Keluarga | Trigger |
|---:|---|---|---|
| 11 | CHoCH | Structure | Protected swing ditembus oleh close candle melawan arah struktur HH/HL atau LH/LL sebelumnya |
| 12 | BOS | Structure | Close melewati swing terkonfirmasi searah struktur HH/HL atau LH/LL |
| 13 | Candle Displacement | Price Action | Range candle mengembang, body dominan, close melewati range lokal |
| 14 | Breakout Retest | Price Action | Breakout close, retest level, dan candle close kembali mempertahankan level |
| 15 | Fair Value Gap | Price Action | Ketidakseimbangan tiga candle dengan displacement middle candle |
| 16 | FVG Retest | Price Action | Zona FVG belum invalid, harga masuk kembali, lalu candle close rejection |
| 17 | Order Block Retest | Price Action | Candle lawan terakhir sebelum displacement/break struktur diuji ulang dan ditolak |
| 22 | Trend Pullback | Price Action | Pullback dalam struktur HH/HL atau LH/LL dan candle trigger menembus candle koreksi |
| 23 | Donchian Range Breakout | Price Action | Candle close keluar dari range lookback 10 candle |

## 3. Interpretasi struktur

**CHoCH** tidak sekadar berarti harga membuat satu higher-high/lower-low. Implementasi menuntut dua confirmed swing highs dan lows untuk membaca arah struktur sebelumnya, lalu close menembus protected swing yang berlawanan. Ini mengurangi false detection akibat wick, tetapi tetap merupakan definisi algoritmik dan perlu diuji terhadap data.

**BOS** dipisahkan dari CHoCH. BOS mengukur kelanjutan struktur; CHoCH mengukur perubahan karakter struktur. Keduanya mensyaratkan close melewati swing, bukan sekadar sentuhan level.

**FVG** dibentuk oleh gap tiga candle: bullish bila low candle terbaru di atas high candle pertama; bearish bila high candle terbaru di bawah low candle pertama. FVG Retest adalah pola terpisah, bukan sinyal yang otomatis lahir ketika gap terbentuk.

**Order Block Retest** adalah definisi operasional: candle terakhir berlawanan sebelum displacement candle yang mematahkan range konteks. Retest harus berinteraksi dengan range candle tersebut dan ditutup kembali ke arah displacement. Ini bukan bukti bahwa order institusi benar-benar berada di sana.

## 4. Lifecycle dan eksekusi

Sinyal mencatat reference level, trigger close, invalidation, event ID, timeframe, alasan, dan estimasi execution price. BUY menggunakan Ask dan SELL menggunakan Bid apabila quote yang tersedia masih segar; bila tidak, estimasi kembali ke harga candle dan spread yang tersedia.

Lifecycle tetap memantau harga sesudah sinyal terbit:
- `ACTIVE`: pemicu baru lahir.
- `PENDING_CONFIRMATION`: menunggu perkembangan harga.
- `CONFIRMED`: harga bergerak sesuai threshold.
- `INVALIDATED`: invalidation level ditembus.
- `EXPIRED`: batas usia sinyal tercapai.

Tick stream boleh memperbarui harga untuk lifecycle, tetapi tidak boleh membuat pola entry baru.

## 5. Pengujian dan batas validasi

Test regressions telah diperbarui agar pola baru memiliki fixture candle-only. Namun **angka test pass dari dokumen audit lama dihapus**: test suite harus dijalankan kembali pada branch ini sebelum status lulus dapat diklaim.

Jalankan:

```bash
python -m pytest tests -v
```

Setelah unit test:
1. Jalankan backtest M1 dan M5 secara terpisah pada histori Dukascopy.
2. Ukur frekuensi sinyal, waktu pemicu, jarak invalidation, spread, slippage, dan expectancy.
3. Lakukan walk-forward dan uji BUY/SELL secara terpisah.
4. Audit sinyal yang hilang, terduplikasi, atau muncul saat replay/catch-up.
5. Baru kalibrasi ambang; jangan menyamakan parameter harga absolut untuk semua kondisi volatilitas XAUUSD.

Tidak ada klaim win rate, expectancy, atau profitabilitas yang dibuat oleh perubahan ini.
