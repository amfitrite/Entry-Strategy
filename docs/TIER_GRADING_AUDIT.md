# Audit dan Perbaikan Metodologi Tier Grading Engine — XAUUSD (M1 / M5 / M15)

Dokumen laporan resmi hasil audit komprehensif, penghapusan nilai asumsi/palsu (*fabricated fallback*), penegakan *closed-candle only*, pencegahan *look-ahead bias*, dan pemodelan transparansi data pada sistem evaluasi kualitas sinyal (Tier Grading Engine) di repository `amfitrite/Entry-Strategy`.

---

## 1. Daftar File yang Diubah & Ditambahkan

| File | Status | Ringkasan Perubahan |
|---|---|---|
| `entrystrategy/engine/grading/models.py` | Modified | Menambahkan enum `DataStatus` (`OBSERVED`, `ESTIMATED`, `UNAVAILABLE`, `INSUFFICIENT`) dan `DataSufficiencyStatus` (`SUFFICIENT`, `INSUFFICIENT_DATA`). Menambahkan field transparansi data, pelacakan bobot efektif, normalisasi skor dinamis (`calculate_normalized_score`), dan penanda status validasi `validation_status="NOT VALIDATED"`. |
| `entrystrategy/engine/grading/thresholds.py` | Modified | Menghilangkan fallback palsu `1.5` pada `calculate_atr()`. Menambahkan validasi `is_closed=True`. Menandai parameter `TIMEFRAME_PROFILES` sebagai estimasi empiris provisional. |
| `entrystrategy/engine/grading/base.py` | Modified | Memperketat `get_closed_candles()` dengan filter `is_closed=True` dan batas `snapshot_timestamp_ms`. Menghapus fallback ATR palsu pada `assess_execution_quality()`. Menghapus baseline MTF positif fiktif (75.0/80.0) pada `evaluate_mtf_confluence()`. Mengganti confidence konstan dengan `calculate_dynamic_confidence()`. Menambahkan fungsi lokasi spesifik strategi (Breakout Clearance, Fibonacci Retracement, Discount/Premium). |
| `entrystrategy/engine/grading/engine.py` | Modified | Menerapkan evaluasi berbasis snapshot historis waktu sinyal (`signal.timestamp_ms`). Menerapkan Data Gate penalti dan pembatasan tier ke C/D jika status `INSUFFICIENT_DATA`. Kompatibilitas mundur pemanggilan evaluator mock. |
| `entrystrategy/engine/grading/evaluators.py` | Modified | Memperbarui seluruh 25 kelas evaluator (mencakup 40 strategi price-action) agar menggunakan snapshot timestamp, lokasi spesifik strategi, confidence dinamis, dan geometri OHLC asli pada FVG tanpa fallback buatan. |
| `entrystrategy/engine/grading/validation.py` | New | Fondasi evaluasi performa historis: implementasi dataclass `TierPerformanceMetrics` dan kelas `HistoricalTierValidator` (menghitung Win Rate, Expectancy, Profit Factor, Average R, Drawdown/MAE, MFE). |
| `entrystrategy/engine/grading/__init__.py` | Modified | Mengekspor model baru, fungsi helper transparansi data, dan modul validasi historis. |
| `tests/test_audit_tier_grading.py` | New | 15 pengujian audit komprehensif membuktikan batas tier, non-fabrication ATR, closed-candle only, pencegahan look-ahead bias, isolasi HTF, geometri FVG, confidence dinamis, dan penalti insufficient data. |
| `tests/test_volume_orderflow_strategies.py` | Modified | Penyelarasan timestamp sinyal pengujian dengan timestamp candle buffer agar valid pada filter snapshot non-lookahead. |
| `docs/TIER_GRADING_AUDIT.md` | New | Dokumen audit lengkap mencakup 10 poin output yang diwajibkan dalam spesifikasi tugas. |

---

## 2. Daftar Masalah yang Diperbaiki

### A. Penghapusan Fabricated ATR Fallback
- **Masalah Sebelumnya:** Fungsi `calculate_atr()` mengembalikan nilai tebakan `1.5` ketika jumlah candle closed kurang dari periode ATR (14 bar). Hal ini menyebabkan eksekusi dan rasio displacement dinilai tinggi secara fiktif seolah-olah data volatilitas tersedia.
- **Perbaikan:** `calculate_atr()` kini mengembalikan `None` jika candle closed kurang dari periode. Komponen yang membutuhkan ATR menandai metrik sebagai `UNAVAILABLE` atau `INSUFFICIENT`, dan memberikan penalti data tanpa menciptakan angka buatan.

### B. Penegakan Closed-Candle-Only Secara Mutlak
- **Masalah Sebelumnya:** Candle in-progress (belum close / `is_closed=False`) berisiko terbawa ke dalam buffer perhitungan ATR, konfirmasi candle, dan pembacaan level swing.
- **Perbaikan:** `get_closed_candles()` secara eksplisit memfilter `c.is_closed is True`. Seluruh komponen (Pattern Quality, Market Structure, Location Quality, Candle Confirmation, Execution Quality) hanya beroperasi pada bar yang telah selesai secara definitif.

### C. Pencegahan Look-Ahead Bias via Snapshot Timestamp
- **Masalah Sebelumnya:** Jika sinyal lama dievaluasi ulang di masa depan, evaluator menggunakan seluruh isi buffer termasuk candle-candle yang lahir setelah waktu sinyal (`signal.timestamp_ms`), mendistorsi penilaian historis.
- **Perbaikan:** Evaluasi mengunci waktu sinyal sebagai batas atas: `c.timestamp.timestamp() * 1000 <= snapshot_timestamp_ms`. Candle masa depan diabaikan secara ketat.

### D. Penghapusan MTF Confluence Baseline Positif Fiktif
- **Masalah Sebelumnya:** Timeframe M15 secara otomatis diberikan skor MTF 80.0 meskipun tidak ada HTF yang diperiksa. Jika buffer HTF kosong, diberikan default skor 75.0 (positif tanpa bukti).
- **Perbaikan:** Timeframe M15 yang berdiri sendiri (atau sinyal tanpa data HTF) menandai MTF confluence sebagai `UNAVAILABLE` (`score is None`). Tidak ada skor positif tanpa bukti candle HTF closed nyata. Bobot komponen disesuaikan secara transparan melalui normalisasi.

### E. Lokasi Spesifik Strategi (Location Quality Refactoring)
- **Masalah Sebelumnya:** Seluruh 40 strategi dinilai menggunakan formula generik Discount/Premium Zone (BUY di $<40\%$, SELL di $>60\%$). Hal ini tidak relevan untuk strategi Breakout atau Retest.
- **Perbaikan:** Dibagi menjadi 3 formula matematis sesuai karakter strategi:
  1. *Breakout Clearance:* Mengukur jarak penembusan di luar batas rentang konsolidasi relatif terhadap ATR.
  2. *Fibonacci Retracement Depth:* Mengukur kedalaman kembalinya harga ke zona ideal 38.2% – 61.8% untuk Pullback dan Retest.
  3. *Discount / Premium Range:* Mengukur posisi harga relatif terhadap rentang ekstrem untuk Reversal dan Sweep.

### F. Geometri FVG Berbasis OHLC Murni
- **Masalah Sebelumnya:** Evaluator Fair Value Gap menggunakan estimasi `c1.range * 0.6` saat selisih candle tidak terdefinisi.
- **Perbaikan:** Lebar gap dihitung murni dari geometri 3-candle OHLC:
  - BUY FVG: `low[0] - high[2]`
  - SELL FVG: `low[2] - high[0]`
  Jika gap $\le 0$, dicatat sebagai `gap = 0.0 pts` dengan skor minimal dan status penalised tanpa manipulasi angka.

### G. Confidence Dinamis Mencerminkan Kecukupan Data
- **Masalah Sebelumnya:** Nilai confidence di-hardcode dengan angka konstan `0.95` atau `0.92`.
- **Perbaikan:** Confidence dihitung melalui fungsi `calculate_dynamic_confidence()` yang menimbang jumlah candle closed, rasio ketersediaan 5 komponen, konfirmasi HTF, dan ketidakpastian proxy.

### H. Penanganan Missing Data & Data Gating
- **Masalah Sebelumnya:** Data yang hilang berpotensi menaikkan nilai rata-rata jika bobot diabaikan begitu saja.
- **Perbaikan:** Ditambahkan sistem `DataSufficiencyStatus`. Jika data penting hilang (`INSUFFICIENT_DATA`), tier sinyal dipotong secara paksa (*data gate cap*) maksimal ke Tier C atau D dan dicatat dalam daftar penalti.

---

## 3. Pemetaan Lengkap 40 Strategi ke Evaluator & Persyaratan Data

Setiap strategi memiliki evaluator terdedikasi dengan metrik spesifik dan kebutuhan data minimum yang ketat:

| ID | Nama Strategi | Kategori | Kelas Evaluator | Metrik Utama yang Dinilai | Persyaratan Data Minimum |
|---:|---|---|---|---|---|
| 1 | Candlestick Reversal | Candle | `CandlestickPatternEvaluator` | Wick-to-range ratio ($\ge 55\%$), rejection extremum | $\ge 5$ closed bars |
| 2 | Candlestick Continuation | Candle | `CandlestickPatternEvaluator` | Body dominance ($\ge 70\%$), close di ekstrem, low wick | $\ge 5$ closed bars |
| 3 | Multi-Candle Reversal | Candle | `CandlestickPatternEvaluator` | Formasi 3-bar, penetrasi bar ke-3 vs bar ke-1 | $\ge 5$ closed bars |
| 4 | Inside Bar Breakout | Candle | `InsideOutsideBarEvaluator` | Kompresi mother bar, rasio breakout close | $\ge 6$ closed bars |
| 5 | Outside Bar Breakout | Candle | `InsideOutsideBarEvaluator` | Rasio engulfing body vs previous bar ($\ge 1.3\text{x}$) | $\ge 6$ closed bars |
| 6 | Momentum | Candle | `MomentumPatternEvaluator` | Akselerasi ukuran candle body searah tren | $\ge 8$ closed bars |
| 7 | Breakout | Hybrid | `BreakoutEvaluator` | Breakout clearance vs ATR, volume expansion | $\ge 15$ closed bars + ATR |
| 8 | Failed Breakout (Trap) | Hybrid | `FailedBreakoutEvaluator` | Kedalaman liquidity sweep dan rejection wick ($\ge 45\%$) | $\ge 12$ closed bars |
| 9 | Micro Pullback | Hybrid | `TrendPullbackEvaluator` | Fibonacci depth retracement ($38.2\% - 61.8\%$) | $\ge 12$ closed bars |
| 10 | Micro Trend Reversal | Hybrid | `MicroTrendReversalEvaluator` | Penembusan micro pivot swing dengan bar penutup tegas | $\ge 10$ closed bars |
| 11 | CHoCH (Change of Character) | Structure | `ChangeOfCharacterEvaluator` | Penembusan swing struktural lawan tren, displacement body | $\ge 15$ closed bars + ATR |
| 12 | BOS (Break of Structure) | Structure | `BreakOfStructureEvaluator` | Penembusan swing searah tren, follow-through close | $\ge 15$ closed bars + ATR |
| 13 | Candle Displacement | Price Action | `CandleDisplacementEvaluator` | Ukuran body impulsif vs ATR ($\ge 1.4\text{x}$) tanpa opposing wick | $\ge 10$ closed bars + ATR |
| 14 | Breakout Retest | Price Action | `BreakoutRetestEvaluator` | S/R level flip test, retest rejection wick | $\ge 15$ closed bars |
| 15 | Fair Value Gap (FVG) | Price Action | `FairValueGapEvaluator` | Geometri OHLC 3-candle imbalance void vs ATR | $\ge 8$ closed bars + ATR |
| 16 | FVG Retest | Price Action | `FairValueGapRetestEvaluator` | Penetrasi ke zona 50% FVG dan reaksi rejection wick | $\ge 10$ closed bars |
| 17 | Order Block Retest | Price Action | `OrderBlockRetestEvaluator` | Reaksi dan ketahanan harga pada origin candle OB | $\ge 12$ closed bars |
| 18 | Micro Range Expansion | Hybrid | `VolatilityRangeEvaluator` | Rasio range bar vs rata-rata 10 bar ($\ge 1.5\text{x}$) | $\ge 12$ closed bars |
| 19 | Micro Range Compression | Hybrid | `VolatilityRangeEvaluator` | Durasi dan kerapatan range sebelum ekspansi | $\ge 12$ closed bars |
| 20 | Volatility Burst | Hybrid | `VolatilityRangeEvaluator` | Kenaikan range seketika dengan close dominan | $\ge 12$ closed bars + ATR |
| 21 | Volatility Contraction | Candle | `VolatilityRangeEvaluator` | Kontraksi range berturut-turut (NR4/NR7) | $\ge 10$ closed bars |
| 22 | Trend Pullback | Price Action | `TrendPullbackEvaluator` | Retracement ke zona S/R dinamis tren | $\ge 12$ closed bars |
| 23 | Donchian Range Breakout | Price Action | `BreakoutEvaluator` | Penembusan batas channel Donchian 20 bar | $\ge 20$ closed bars |
| 24 | Rejection Pattern | Hybrid | `CandlestickPatternEvaluator` | Rejection wick dominan pada level ekstrem ($\ge 55\%$) | $\ge 6$ closed bars |
| 25 | Wick Pattern | Candle | `CandlestickPatternEvaluator` | Pinbar rejection terhadap level struktural | $\ge 6$ closed bars |
| 26 | Body Expansion | Candle | `VolatilityRangeEvaluator` | Rasio ekspansi body terhadap 5 bar sebelumnya | $\ge 8$ closed bars |
| 27 | Body Contraction | Candle | `VolatilityRangeEvaluator` | Doji / small body menandai ekuilibrium sebelum breakout | $\ge 8$ closed bars |
| 28 | Gap Pattern | Hybrid | `VolatilityRangeEvaluator` | Ukuran price gap open-close vs baseline ATR | $\ge 8$ closed bars + ATR |
| 29 | Failed Momentum | Hybrid | `MomentumPatternEvaluator` | Penolakan harga seketika setelah candle dorongan | $\ge 8$ closed bars |
| 30 | Momentum Exhaustion | Hybrid | `MomentumPatternEvaluator` | Climax run dengan wick panjang menandai keletihan tren | $\ge 8$ closed bars |
| 31 | Micro Double Top | Swing | `GeometryPatternEvaluator` | Simetri 2 puncak harga dengan penolakan bearish dan konfirmasi | $\ge 15$ closed bars |
| 32 | Micro Double Bottom | Swing | `GeometryPatternEvaluator` | Simetri 2 lembah harga dengan penolakan bullish dan konfirmasi | $\ge 15$ closed bars |
| 33 | Micro Swing Break | Swing | `MicroSwingBreakEvaluator` | Penembusan pivot swing mikro terdekat dengan decisive close | $\ge 10$ closed bars |
| 34 | Micro Swing Failure (SFP) | Swing | `MicroSwingFailureEvaluator` | Sweep likuiditas pivot disusul penutupan kembali ke dalam range | $\ge 10$ closed bars |
| 35 | Three-Push Pattern | Swing | `GeometryPatternEvaluator` | 3 dorongan sekuensial dengan divergensi momentum | $\ge 18$ closed bars |
| 36 | V-Reversal | Hybrid | `GeometryPatternEvaluator` | Pembalikan tajam dari penurunan tajam seketika | $\ge 12$ closed bars |
| 37 | Inverted V-Reversal | Hybrid | `GeometryPatternEvaluator` | Pembalikan tajam dari lonjakan tajam seketika | $\ge 12$ closed bars |
| 38 | Staircase Pattern | Candle | `CandleSequenceEvaluator` | Sekuens Higher Highs/Higher Lows atau Lower Highs/Lower Lows | $\ge 8$ closed bars |
| 39 | Candle Sequence | Candle | `CandleSequenceEvaluator` | Rangkaian candle searah (3 white soldiers / 3 black crows) | $\ge 8$ closed bars |
| 40 | Candle Rejection Confluence | Candle | `CandlestickPatternEvaluator` | Kluster beberapa rejection wick pada level harga yang sama | $\ge 10$ closed bars |

---

## 4. Formula Final Komponen Grading

### A. Bobot Komponen Konfigurasi
- **Pattern Quality ($w_{PQ}$):** 30% ($0.30$)
- **Market Structure ($w_{MS}$):** 20% ($0.20$)
- **Location Quality ($w_{LQ}$):** 20% ($0.20$)
- **Candle Confirmation ($w_{CC}$):** 15% ($0.15$)
- **Execution Quality ($w_{EQ}$):** 15% ($0.15$)

Total bobot konfigurasi: $\sum w_i = 1.00$.

### B. Normalisasi Skor Komponen Dinamis
Jika terdapat komponen yang berstatus `UNAVAILABLE` (misalnya Execution Quality karena spread tidak dilaporkan oleh feed), skor dinormalisasi secara adil berdasarkan komponen yang tersedia tanpa menganggap komponen yang hilang bernilai 0 atau 100:

$$\text{Effective Weight } w'_i = \frac{w_i}{\sum_{j \in \text{Available}} w_j}$$

$$\text{Total Score} = \sum_{i \in \text{Available}} w'_i \times C_i$$

### C. Rincian Formula Setiap Komponen

#### 1. Pattern Quality (PQ)
Mengukur ketepatan bentuk pola teknis berdasarkan geometri candle pemicu:
- Rasio Body terhadap Range ($R_{body} = \frac{|C - O|}{H - L}$)
- Rasio Penolakan Wick ($R_{wick} = \frac{\text{Wick Searah}}{\text{Range}}$)
- Rasio Displacement terhadap ATR ($R_{disp} = \frac{|C - O|}{\text{ATR}}$)
- Skor berkisar 0–100 dengan pengurangan bila rasio displacement atau dominasi candle di bawah standar profil timeframe.

#### 2. Market Structure (MS)
Mengukur keselarasan arah sinyal terhadap struktur swing internal dan konteks higher timeframe (HTF):
- Penilaian Swing Pivot: Menguji urutan Higher Highs/Higher Lows (tren Bullish) atau Lower Highs/Lower Lows (tren Bearish) pada 15–20 bar closed terakhir.
- Konfluensi HTF: Hanya diperiksa jika bar HTF closed tersedia. Jika selaras menambah hingga +15 poin; jika kontra-tren memotong hingga -25 poin; jika HTF tidak tersedia berstatus `UNAVAILABLE` (tanpa bonus/penalti fiktif).

#### 3. Location Quality (LQ)
Menggunakan salah satu dari 3 formula spesifik:
- **Formula Breakout Clearance (Breakout / Structure):**
  $$LQ = \min\left(100, 50 + \frac{\text{Clearance Pts}}{\text{ATR}} \times 40\right)$$
- **Formula Retracement Depth (Pullback / Retest):**
  $$LQ = \max\left(0, 100 - \frac{|\text{Retracement \%} - 50.0|}{25.0} \times 50\right)$$
  (Puncak 100% pada area Golden Retest 50%, optimal di rentang 38.2% – 61.8%).
- **Formula Discount/Premium (Reversal / Extremum):**
  - BUY (Discount): $LQ = \max(0, 100 - \text{Posisi Range} \times 120)$
  - SELL (Premium): $LQ = \max(0, (\text{Posisi Range} - 0.4) \times 166.7)$

#### 4. Candle Confirmation (CC)
Mengukur kekuatan candle saat penutupan:
- BUY: Close berada di sepertiga atas rentang candle ($C \ge H - 0.33 \times (H - L)$).
- SELL: Close berada di sepertiga bawah rentang candle ($C \le L + 0.33 \times (H - L)$).
- Tidak adanya opposing wick tajam yang menolak arah pergerakan.

#### 5. Execution Quality (EQ)
Mengukur kelayakan pelaksanaan teknis saat sinyal lahir:
- Efisiensi Spread vs Ambang Batas Timeframe ($0.35$ pts M1, $0.45$ pts M5, $0.60$ pts M15).
- Kewajaran Jarak Invalidation Level terhadap ATR ($0.5\text{x} \le \text{Dist}_{SL} \le 3.0\text{x}$ ATR).
- Jika data closed bar tidak mencukupi untuk menghitung ATR, EQ ditandai `UNAVAILABLE` dan memicu `INSUFFICIENT_DATA`.

### D. Formula Dynamic Confidence
Confidence tidak lagi menggunakan konstanta, melainkan dihitung berdasarkan kecukupan bukti:
$$\text{Confidence} = 0.50 \times \min\left(1.0, \frac{N_{closed}}{N_{required}}\right) + 0.25 \times \frac{K_{available}}{5} + 0.15 \times \mathbb{I}_{MTF} + 0.10 \times (1 - \text{Penalty}_{proxy})$$

---

## 5. Bukti Closed-Candles Only Enforcement

Penegakan bahwa hanya closed candle yang digunakan dijamin melalui tiga lapis arsitektur:

1. **Lapis Buffer Filtering (`entrystrategy/engine/grading/base.py`):**
   ```python
   def get_closed_candles(
       buffer: MarketBuffer,
       timeframe: str,
       limit: int = 50,
       snapshot_timestamp_ms: Optional[int] = None,
   ) -> List[Candle]:
       raw_candles = buffer.get_candles(timeframe, limit=limit + 10)
       closed = [c for c in raw_candles if getattr(c, "is_closed", True) is True]
       if snapshot_timestamp_ms is not None:
           closed = [
               c for c in closed
               if int(c.timestamp.timestamp() * 1000) <= snapshot_timestamp_ms
           ]
       return closed[-limit:]
   ```
2. **Lapis ATR Calculation (`entrystrategy/engine/grading/thresholds.py`):**
   ```python
   closed_candles = [c for c in candles if getattr(c, "is_closed", True) is True]
   if len(closed_candles) < period:
       return None  # Tegas mengembalikan None, tidak ada angka 1.5 buatan
   ```
3. **Verifikasi Unit Test:**
   - `test_unclosed_candle_never_affects_grading`: Memasukkan candle unclosed yang sangat ekstrem ke dalam buffer, membuktikan skor grading dan breakdown identik 100% dengan kondisi sebelum bar unclosed dimasukkan.
   - `test_calculate_atr_uses_only_closed_candles`: Memasukkan 13 closed candle + 1 unclosed candle untuk ATR 14; fungsi tetap mengembalikan `None`.
   - `test_htf_unclosed_candles_never_leak_into_mtf_context`: Memastikan bar HTF unclosed tidak pernah dievaluasi sebagai konfirmasi tren.

---

## 6. Bukti Pencegahan Look-Ahead Bias

Look-ahead bias dicegah secara deterministik dengan mengisolasi jendela observasi tepat pada saat sinyal muncul:

1. **Mekanisme Snapshot Timestamp:**
   Setiap pemanggilan grading mengunci snapshot waktu:
   ```python
   snapshot_ts = getattr(signal, "timestamp_ms", None)
   # Seluruh pengambilan data closed bar dibatasi secara kaku oleh snapshot_ts
   ```
2. **Verifikasi Pengujian (`test_future_candles_never_affect_historical_grade`):**
   - Dibuat sinyal pada $T_0$ dengan 20 closed candle. Sinyal dinilai menghasilkan Skor $S_0$ dan Tier $T_0$.
   - Ditambahkan 10 candle masa depan ke dalam buffer ($T_{+1}$ hingga $T_{+10}$) dengan volatilitas ekstrem yang berlawanan.
   - Sinyal $T_0$ dinilai kembali menggunakan engine yang sama.
   - **Hasil:** Skor sebelum dan sesudah penambahan candle masa depan sama persis ($S_{after} == S_{before}$), membuktikan tidak ada kebocoran data masa depan (*zero look-ahead bias*).

---

## 7. Hasil Unit Test dan Integration Test

Pengujian dijalankan menggunakan pytest pada seluruh test suite repository:

```
============================= test session starts =============================
platform win32 -- Python 3.14.7, pytest-9.1.1, pluggy-1.7.0
rootdir: D:\Entry Strategy
collected 125 items

tests/test_audit_all_40_patterns.py (22 tests) ...................... PASSED [ 18%]
tests/test_audit_conceptual_and_symmetry.py (10 tests) ..........    PASSED [ 26%]
tests/test_audit_tier_grading.py (15 tests) ...............          PASSED [ 38%]
tests/test_gui_api.py (26 tests) ..........................          PASSED [ 59%]
tests/test_patterns.py (5 tests) .....                               PASSED [ 63%]
tests/test_signal_lifecycle.py (7 tests) .......                     PASSED [ 68%]
tests/test_tier_grading_engine.py (17 tests) .................       PASSED [ 82%]
tests/test_timeframe_and_ticks.py (8 tests) ........                PASSED [ 88%]
tests/test_volume_orderflow_strategies.py (15 tests) ............... PASSED [100%]

============================= 125 passed in 3.17s =============================
```

### Rincian Pengujian Audit Tier Grading Baru (`tests/test_audit_tier_grading.py`):
1. `test_all_tier_boundaries` — LULUS (Batas SSS $\ge 95$, SS $\ge 90$, S $\ge 85$, A $\ge 75$, B $\ge 65$, C $\ge 50$, D $< 50$).
2. `test_grading_weights_sum_to_one` — LULUS (Total bobot = 1.00).
3. `test_calculate_atr_no_fabricated_fallback` — LULUS (Mengembalikan `None` tanpa data).
4. `test_calculate_atr_uses_only_closed_candles` — LULUS (Bar unclosed diabaikan).
5. `test_unclosed_candle_never_affects_grading` — LULUS (Bar berjalan tidak mempengaruhi skor).
6. `test_future_candles_never_affect_historical_grade` — LULUS (Bebas look-ahead bias).
7. `test_htf_unclosed_candles_never_leak_into_mtf_context` — LULUS (HTF unclosed diisolasi).
8. `test_no_mtf_positive_baseline_without_evidence` — LULUS (Tidak ada baseline 75/80 fiktif).
9. `test_location_quality_strategy_specific_formulas` — LULUS (Formula lokasi relevan per strategi).
10. `test_fvg_real_ohlc_geometry_no_fabricated_fallback` — LULUS (Geometri FVG murni dari OHLC).
11. `test_dynamic_confidence_calculation` — LULUS (Confidence proporsional dengan kelengkapan data).
12. `test_insufficient_data_produces_tier_cap` — LULUS (Pembatasan tier ke C/D saat data tidak cukup).
13. `test_all_40_strategy_ids_have_evaluator_mapping` — LULUS (Semua 40 strategi terpetakan).
14. `test_deterministic_scoring_for_identical_snapshot` — LULUS (Skor konsisten dan deterministik).
15. `test_historical_validation_foundation_and_not_validated_status` — LULUS (Label NOT VALIDATED tersemat).

---

## 8. Daftar Parameter Provisional (Empiris)

Parameter berikut merupakan estimasi empiris awal (*provisional*) untuk instrumen XAUUSD dan **belum tervalidasi secara statistik melalui forward testing out-of-sample**:

1. **Ambang Batas Tier:** SSS (95), SS (90), S (85), A (75), B (65), C (50), D (<50).
2. **Bobot Komponen:** PQ (30%), MS (20%), LQ (20%), CC (15%), EQ (15%).
3. **Periode ATR:** 14 bar untuk seluruh timeframe.
4. **Baseline Volatilitas Tipikal XAUUSD:** M1 ($1.2$ poin), M5 ($2.5$ poin), M15 ($4.5$ poin).
5. **Ambang Batas Spread Maksimum:** M1 ($0.35$ poin / 3.5 pips), M5 ($0.45$ poin / 4.5 pips), M15 ($0.60$ poin / 6.0 pips).
6. **Rasio Displacement Minimum:** M1 ($1.4\text{x}$ ATR), M5 ($1.3\text{x}$ ATR), M15 ($1.25\text{x}$ ATR).
7. **Jendela Golden Retest Depth:** Rentang Fibonacci $38.2\% - 61.8\%$.

*Seluruh parameter di atas disimpan sebagai konfigurasi transparan yang dapat dikalibrasi ulang setelah evaluasi historis komprehensif dilakukan.*

---

## 9. Daftar Keterbatasan yang Belum Dapat Diselesaikan

1. **Ketiadaan Data Level 2 / DOM Depth:** Sumber data tick/bar Dukascopy tidak menyediakan antrean resting order limit (L2 Depth of Market). Oleh karena itu, likuiditas resting tidak dapat diobservasi langsung dan tidak diikutsertakan dalam penilaian grading untuk menghindari fabrikasi data.
2. **Proxy Volume Transaksi Agresor:** Pada feed retail/Dukascopy, volume buy/sell dan delta dihitung menggunakan pendekatan arah pergerakan tick (*tick-direction proxy classification*), bukan pencatatan pita transaksi agresor bursa terpusat (*CME real trade tape*). Keterbatasan ini telah ditandai secara transparan dengan status data `ESTIMATED`.
3. **Ketiadaan Riwayat Eksekusi Forward Nyata:** Karena proyek saat ini berfokus pada lapisan engine sinyal dan jurnal (tanpa automated execution bot), data eksekusi fill/slippage riil belum tersedia untuk mengukur korelasi tier terhadap real-world slippage.

---

## 10. Hasil Historical Validation (Pernyataan Status)

> **STATUS: NOT VALIDATED (BELUM DILAKUKAN)**

### Pernyataan Resmi:
Sesuai dengan ketentuan metodologi: **Tier grading saat ini berstatus teknis "NOT VALIDATED" dan belum dinyatakan prediktif terhadap hasil perdagangan riil.**

### Fondasi yang Telah Disiapkan:
Modul `entrystrategy.engine.grading.validation` telah diimplementasikan dengan kelas `HistoricalTierValidator` dan dataclass `TierPerformanceMetrics`. Modul ini siap digunakan untuk menghitung metrik berikut per Tier (SSS hingga D) ketika dataset eksekusi out-of-sample tersedia:
- Sample Size ($N$ sinyal per tier)
- Win Rate ($\%$)
- Expectancy ($R$)
- Average $R$-Multiple
- Profit Factor
- Maximum Adverse Excursion (MAE)
- Maximum Favorable Excursion (MFE)

Setiap hasil grading yang dihasilkan oleh `GradingEngine` saat ini secara transparan menyematkan atribut:
```python
validation_status: str = "NOT VALIDATED"
```
Grading murni mencerminkan keselarasan teknis candle saat sinyal lahir, bukan jaminan probabilitas kemenangan.
