# Technical Tier Grading Engine — XAUUSD (M1 / M5 / M15)

Dokumentasi arsitektur, metodologi skoring, dan spesifikasi teknis untuk sistem evaluasi kualitas sinyal (Tier Grading Engine) pada 40 keluarga strategi entry XAUUSD di repository `amfitrite/Entry-Strategy`.

---

## 1. Tujuan & Filosofi

Sistem Tier Grading Engine memberikan penilaian teknis dinamis (**Technical Grade SSS–D**) secara real-time pada setiap sinyal yang dihasilkan oleh 40 strategi entry candle.

### Prinsip Utama:
1. **Dynamic & Contextual**: Satu strategi tidak memiliki grade tetap. Contohnya, pola *CHoCH #11* pada M1 bisa memperoleh **SSS** jika didukung displacement tinggi, market structure selaras, discount location, dan spread rapat; namun bisa memperoleh **B** atau **C** jika penembusan tipis atau terjadi di puncak resistensi.
2. **Post-Trigger Evaluation Layer**: Evaluator berjalan secara independen *setelah* pola mendeteksi kondisi trigger matematisnya. Logika pemicu entry dan parameter bawaan 40 strategi tidak dimodifikasi sama sekali.
3. **Strict Closed-Candle Integrity**: Penilaian murni berbasis candle yang sudah selesai (*completed closed bars*). Unfinished bar dan data masa depan (*look-ahead bias*) dilarang keras masuk ke dalam pipeline analisis.
4. **Independent Multi-Timeframe**: M1, M5, dan M15 dinilai secara mandiri menggunakan profil volatilitas dan threshold masing-masing. Konteks timeframe yang lebih tinggi (HTF) hanya menggunakan bar yang sudah close.
5. **No Win-Rate Illusion**: Technical Grade mengukur kualitas eksekusi dan keselarasan teknis pasar saat sinyal lahir, bukan klaim probabilitas menang otomatis atau historical win rate.

---

## 2. Tabel Klasifikasi Tier

| Tier | Rentang Skor | Karakteristik Kualitas | Persyaratan Minimum Gating |
|---|---|---|---|
| **SSS** | 95.00 – 100.00 | Eksekusi ideal, konfluensi sempurna, momentum dominan | Skor $\ge 95$, PQ $\ge 90$, MS $\ge 90$, CC $\ge 85$, EQ $\ge 80$, Confidence $\ge 0.85$, Tanpa kontradiksi |
| **SS** | 90.00 – 94.99 | Setup sangat berkualitas tinggi, struktur kokoh | Skor $\ge 90$, Seluruh komponen $\ge 65$, Confidence $\ge 0.70$, Tanpa kontradiksi kritis |
| **S** | 85.00 – 89.99 | Pola valid dengan konfirmasi tegas dan lokasi baik | Skor $\ge 85$, Seluruh komponen $\ge 50$, Confidence $\ge 0.60$ |
| **A** | 75.00 – 84.99 | Kualitas teknis solid di atas rata-rata | Skor 75.00 – 84.99 |
| **B** | 65.00 – 74.99 | Sinyal standar memenuhi syarat dasar algoritma | Skor 65.00 – 74.99 |
| **C** | 50.00 – 64.99 | Kualitas marjinal, terdapat friksi struktur atau spread | Skor 50.00 – 64.99 |
| **D** | 0.00 – 49.99 | Kualitas rendah, data terbatas, atau kontra-tren | Skor 0.00 – 49.99 |

---

## 3. Arsitektur Modul

Modul grading diisolasi secara bersih di bawah direktori `entrystrategy/engine/grading/`:

```
entrystrategy/engine/grading/
├── __init__.py           # Export publik & facade engine
├── models.py             # Data models: GradeTier, ComponentBreakdown, GradingWeights, GradingResult
├── thresholds.py         # Batas tier, gating rules, dan profil volatilitas M1/M5/M15
├── base.py               # BaseStrategyEvaluator & analytical tools (Structure, Location, Confirmation, Execution, MTF)
├── evaluators.py         # Evaluator khusus untuk seluruh 40 keluarga strategi & EVALUATOR_MAPPING
└── engine.py             # GradingEngine mengorkestrasi evaluasi, gating, dan atribusi ke EntrySignal
```

### Aliran Data (Data Flow Pipeline):
```
Closed Candle (M1 / M5 / M15)
       │
       ▼
BasePattern.check(buffer)  ───► Fired EntrySignal
                                       │
                                       ▼
                       GradingEngine.grade_signal(signal, buffer, tf)
                                       │
                         ┌─────────────┴─────────────┐
                         ▼                           ▼
              Strategy Evaluator (1-40)      MTF Context Evaluator (Closed only)
                         │                           │
                         └─────────────┬─────────────┘
                                       ▼
                         5 Component Scores (0 - 100)
                                       │
                                       ▼
                         Weighted Sum & Evidence Dedup
                                       │
                                       ▼
                         Tier Gating & Contradiction Caps
                                       │
                                       ▼
                         GradingResult (SSS - D)
                                       │
                                       ▼
                     Attached to EntrySignal attributes
                                       │
                 ┌─────────────────────┴─────────────────────┐
                 ▼                                           ▼
            Live Radar                                 Signal Journal
   (Grade badge, breakdown,                   (Distribution stats, TF stats,
   filters SSS/SS+/S+/A+, score sort)         filters TF/Grade/Dir, full audit)
```

---

## 4. Model Penilaian 5 Komponen

Formula skor akhir dihitung menggunakan pembobotan (*weighted sum*) yang dapat dikonfigurasi:

$$\text{Total Score} = \sum_{i=1}^{5} w_i \times C_i$$

| Komponen | Bobot Default | Parameter yang Dinilai |
|---|---:|---|
| **Pattern Quality (PQ)** | 30% | Validitas geometri pola spesifik, rasio displacement/ATR, clearance penembusan swing, ukuran body bar, rasio rejection wick |
| **Market Structure (MS)** | 20% | Keselarasan dengan Higher Highs/Higher Lows (BUY) atau Lower Highs/Lower Lows (SELL), integritas swing structure, MTF closed confluence |
| **Location Quality (LQ)** | 20% | Posisi relatif harga terhadap range 15–20 bar terakhir: Discount Zone ($\le 40\%$) untuk BUY, Premium Zone ($\ge 60\%$) untuk SELL |
| **Candle Confirmation (CC)** | 15% | Kualitas penutupan bar pemicu: dominasi body ($\ge 65\%$), penutupan di sepertiga ekstrim searah sinyal, minimnya opposing rejection wick |
| **Execution Quality (EQ)** | 15% | Efisiensi spread real-time vs ambang batas aman timeframe, kelayakan jarak level invalidasi terhadap ATR ($0.5\text{x} - 3.0\text{x}$ ATR) |

---

## 5. Pemetaan 40 Strategi ke Evaluator Khusus

Seluruh 40 strategi memiliki evaluator yang memodelkan fenomena pasar riil yang diukur:

| ID | Nama Strategi | Kategori | Kelas Evaluator | Metrik Utama yang Dinilai |
|---:|---|---|---|---|
| 1 | Candlestick Reversal | Candle | `CandlestickPatternEvaluator` | Wick-to-range ratio ($\ge 60\%$), rejection dari ekstrim harga |
| 2 | Candlestick Continuation | Candle | `CandlestickPatternEvaluator` | Body dominance ($\ge 75\%$), penutupan dekat high/low, minim wick |
| 3 | Multi-Candle Reversal | Candle | `CandlestickPatternEvaluator` | Urutan 3 bar (Morning/Evening star), penetrasi bar ke-3 |
| 4 | Inside Bar Breakout | Candle | `InsideOutsideBarEvaluator` | Rasio kompresi mother bar terhadap inside bar |
| 5 | Outside Bar Breakout | Candle | `InsideOutsideBarEvaluator` | Rasio ekspansi engulfing terhadap bar sebelumnya ($\ge 1.5\text{x}$) |
| 6 | Momentum | Candle | `MomentumPatternEvaluator` | Percepatan ukuran body candle searah tren |
| 7 | Breakout | Hybrid | `BreakoutEvaluator` | Jarak breakout clearance dari batas range ($\text{pts} > 0.4\text{x}$ ATR) |
| 8 | Failed Breakout (Trap) | Hybrid | `FailedBreakoutEvaluator` | Kedalaman sweep likuiditas dan ketajaman wick penolakan ($\ge 45\%$) |
| 9 | Micro Pullback | Hybrid | `TrendPullbackEvaluator` | Retracement sehat ke golden zone ($35\% - 65\%$ range) |
| 10 | Micro Trend Reversal | Hybrid | `MicroTrendReversalEvaluator` | Penembusan micro swing high/low dengan close candle tegas |
| 11 | CHoCH (Change of Character) | Structure | `ChangeOfCharacterEvaluator` | Clearance penembusan protected swing dan displacement body ($\ge 1.2\text{x}$ ATR) |
| 12 | BOS (Break of Structure) | Structure | `BreakOfStructureEvaluator` | Penembusan swing tren searah, follow-through candle close |
| 13 | Candle Displacement | Price Action | `CandleDisplacementEvaluator` | Ekspansi body impulsif ($\ge 1.8\text{x}$ ATR) tanpa opposing wick |
| 14 | Breakout Retest | Price Action | `BreakoutRetestEvaluator` | Uji coba level yang tertembus (S/R flip) dan konfirmasi bertahan |
| 15 | Fair Value Gap (FVG) | Price Action | `FairValueGapEvaluator` | Lebar ketidakseimbangan 3-candle void relatif terhadap ATR |
| 16 | FVG Retest | Price Action | `FairValueGapRetestEvaluator` | Mitigasi ke zona 50% FVG dan reaksi rejection wick |
| 17 | Order Block Retest | Price Action | `OrderBlockRetestEvaluator` | Reaksi dan kemampuan harga bertahan di atas/bawah origin candle OB |
| 18 | Micro Range Expansion | Hybrid | `VolatilityRangeEvaluator` | Rasio ekspansi range bar terhadap rata-rata historis ($\ge 1.6\text{x}$) |
| 19 | Micro Range Compression | Hybrid | `VolatilityRangeEvaluator` | Durasi dan kerapatan koiling harga sebelum breakout |
| 20 | Volatility Burst | Hybrid | `VolatilityRangeEvaluator` | Lonjakan ATR seketika dengan close dominan di ujung bar |
| 21 | Volatility Contraction | Candle | `VolatilityRangeEvaluator` | Formasi NR4/NR7 (penyempitan volatilitas) sebelum ekspansi |
| 22 | Trend Pullback | Price Action | `TrendPullbackEvaluator` | Kedalaman retracement ke zona S/R dinamis |
| 23 | Donchian Range Breakout | Price Action | `BreakoutEvaluator` | Penembusan channel Donchian 20-bar dengan close di luar pita |
| 24 | Rejection Pattern | Hybrid | `CandlestickPatternEvaluator` | Penolakan harga ekstrim dengan wick ekstrim ($\ge 60\%$) |
| 25 | Wick Pattern | Candle | `CandlestickPatternEvaluator` | Pinbar rejection terhadap level struktural |
| 26 | Body Expansion | Candle | `VolatilityRangeEvaluator` | Rasio volume & luas body terhadap 5 candle sebelumnya |
| 27 | Body Contraction | Candle | `VolatilityRangeEvaluator` | Doji/Spinning top menandai ekuilibrium sebelum pergerakan besar |
| 28 | Gap Pattern | Hybrid | `VolatilityRangeEvaluator` | Ukuran price gap open-close relatif terhadap noise ATR |
| 29 | Failed Momentum | Hybrid | `MomentumPatternEvaluator` | Penolakan seketika setelah candle dorongan terpicu |
| 30 | Momentum Exhaustion | Hybrid | `MomentumPatternEvaluator` | Climax run dengan wick panjang menandai keletihan pembeli/penjual |
| 31 | Micro Double Top | Swing | `GeometryPatternEvaluator` | Simetri 2 puncak harga dengan penolakan bearish dan konfirmasi neckline |
| 32 | Micro Double Bottom | Swing | `GeometryPatternEvaluator` | Simetri 2 lembah harga dengan penolakan bullish dan konfirmasi neckline |
| 33 | Micro Swing Break | Swing | `MicroSwingBreakEvaluator` | Penembusan pivot mikro terdekat dengan decisive close |
| 34 | Micro Swing Failure (SFP) | Swing | `MicroSwingFailureEvaluator` | Sweep likuiditas di atas/bawah swing pivot disusul reclaim close |
| 35 | Three-Push Pattern | Swing | `GeometryPatternEvaluator` | Tiga dorongan sekuensial dengan pelemahan momentum (wedge) |
| 36 | V-Reversal | Hybrid | `GeometryPatternEvaluator` | Pembalikan tajam dari penurunan tajam seketika dibalas lonjakan |
| 37 | Inverted V-Reversal | Hybrid | `GeometryPatternEvaluator` | Pembalikan tajam dari lonjakan tajam seketika dibalas penurunan |
| 38 | Staircase Pattern | Candle | `CandleSequenceEvaluator` | Sekuens Higher Highs/Higher Lows beruntun |
| 39 | Candle Sequence | Candle | `CandleSequenceEvaluator` | Rangkaian candle searah (3 white soldiers / 3 black crows) |
| 40 | Candle Rejection Confluence | Candle | `CandlestickPatternEvaluator` | Kluster beberapa rejection wick pada level harga yang sama |

---

## 6. Deduplikasi Bukti (Evidence Deduplication)

Untuk mencegah *double-counting* (misalnya menggabungkan skor candle displacement dan body expansion secara linier padahal mengukur fenomena harga yang sama), bukti dikelompokkan ke dalam **Evidence Clusters**:
1. `MOMENTUM_DISPLACEMENT`
2. `STRUCTURAL_BREAK`
3. `REJECTION_WICK`
4. `LOCATION_CONFLUENCE`
5. `MTF_ALIGNMENT`

Di dalam setiap kluster, bukti sekunder dikenakan *diminishing returns*:
$$\text{Cluster Score} = \text{Primary Score} + 0.25 \times (\text{Secondary Score} - 50)$$

---

## 7. Kalibrasi Khusus Timeframe (M1, M5, M15)

Parameter volatilitas XAUUSD disesuaikan secara proporsional per timeframe:

| Parameter | M1 | M5 | M15 |
|---|---:|---:|---:|
| **Default ATR Baseline** | 1.2 pts | 2.5 pts | 4.5 pts |
| **Minimum Displacement Ratio** | $1.4\text{x}$ ATR | $1.3\text{x}$ ATR | $1.25\text{x}$ ATR |
| **Max Acceptable Spread** | 0.35 pts | 0.45 pts | 0.60 pts |
| **Golden Retest Depth** | 38.2% – 61.8% | 38.2% – 61.8% | 38.2% – 61.8% |
| **Minimum Closed Bars for Evaluation** | 10 bars | 10 bars | 8 bars |
| **Signal Maximum Lifetime (`max_age_sec`)** | 60 detik (1 bar) | 300 detik (1 bar) | 900 detik (1 bar) |

---

## 8. Verifikasi dan Pengujian

Seluruh 15 kriteria pengujian wajib yang disyaratkan berhasil lulus 100%:

```
tests/test_tier_grading_engine.py::test_all_40_strategies_have_evaluators PASSED
tests/test_tier_grading_engine.py::test_score_bounds_and_breakdown PASSED
tests/test_tier_grading_engine.py::test_tier_mapping_correctness PASSED
tests/test_tier_grading_engine.py::test_single_strategy_dynamic_different_grades PASSED
tests/test_tier_grading_engine.py::test_timeframe_independence_m1_m5_m15 PASSED
tests/test_tier_grading_engine.py::test_missing_data_handling_and_penalties PASSED
tests/test_tier_grading_engine.py::test_critical_contradiction_capping PASSED
tests/test_tier_grading_engine.py::test_sss_gating_rules_prerequisites PASSED
tests/test_tier_grading_engine.py::test_unclosed_candles_strictly_ignored PASSED
tests/test_tier_grading_engine.py::test_entrysignal_to_from_dict_compatibility PASSED
tests/test_tier_grading_engine.py::test_session_persistence_preserves_grade PASSED
tests/test_tier_grading_engine.py::test_lifecycle_unaltered_by_grading PASSED
tests/test_tier_grading_engine.py::test_prices_never_altered_by_grading PASSED
tests/test_tier_grading_engine.py::test_no_tick_dependency PASSED
tests/test_tier_grading_engine.py::test_mtf_context_uses_only_closed_candles PASSED
tests/test_tier_grading_engine.py::test_all_40_evaluators_run_on_m1_m5_m15 PASSED

93 passed in 3.49s (100% pass across all test suites)
```
