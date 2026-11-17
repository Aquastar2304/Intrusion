# Lightweight Intrusion Detection Framework for Resource-Constrained IoT Devices

**Project documentation — working draft**

---

## 1. One-line summary

Build an intrusion detection system (IDS) small enough to run *on a ~$12 IoT microcontroller itself* rather than on a server, and write a paper that measures honestly what that costs.

---

## 2. Problem and motivation

IoT devices — cameras, smart plugs, sensors — are hijacked into botnets constantly (Mirai infected hundreds of thousands of them). The standard defense is an IDS that watches network traffic and flags attacks, but conventional IDS software assumes a real computer. A microcontroller such as an ESP32 has roughly 320 KB of usable SRAM and no meaningful operating system, so it cannot run a normal IDS. The device is therefore either protected by something elsewhere on the network (the cloud/centralized approach) or not protected at all.

This project takes the **edge** approach: move detection onto the device itself. That places the work squarely in **edge computing / TinyML** (on-device ML on severely constrained hardware). The edge-vs-cloud tradeoff — latency, bandwidth, privacy, and working while disconnected — is the framing motivation for the paper.

**Research question:** For IoT intrusion detection on constrained hardware, where does the cost actually go, and how small can detection get before it stops working?

---

## 3. Contributions (what makes this a paper, not just a project)

A plain "I made an IDS smaller" study has been done many times and reads as incremental. This paper's value is in measuring two things the field routinely skips:

1. **Feature extraction — not inference — dominates on-device cost (headline).** Almost every paper measures how fast the model runs and ignores that the input features must be computed from raw packets on the same tiny chip. Measuring both on an ESP32 and showing feature extraction dominates *reframes* how the detector should be designed. This is a rigorous-quantification contribution, not a claimed breakthrough — frame it that way.
   *Confirmed physically feasible:* the dataset's features are computed over a **100-packet sliding window** (the `Number` column tops out at exactly 100), so the on-device state is a small fixed-size ring buffer with a known byte cost — not an unbounded flow table. The engineering is real but bounded.
2. **Cross-dataset generalization collapse, measured through one shared extractor.** Models that report >99% F1 in-lab often fall apart on traffic from a different source. Most cross-dataset papers quietly compare datasets that were feature-extracted by *different* tools, so part of the reported "generalization gap" is a tooling artifact. Here the same extractor (§6) runs on both datasets' raw pcaps, so the gap measured is a genuine traffic-distribution gap. The paper documents how much, and whether compressed models degrade worse than their full versions.

**Supporting result, already measured.** An honest file-grouped split scores **macro-F1 0.668** where the literature reports ~0.99 with random splits on the same data (§7). That ~30-point gap is direct evidence for the honesty framing rather than an assertion about it, and it belongs in the paper as a table.

**Guiding discipline:** claim narrow, prove fully. Overclaiming is the most common reason student papers are rejected, and it is entirely avoidable.

---

## 4. Datasets

Download existing public datasets — do **not** collect your own (that would consume the whole timeline and make results non-comparable).

### Primary — CIC-IoT-2023 (train / validation / test)
- Source: Canadian Institute for Cybersecurity, University of New Brunswick. Free, short registration form.
- Contents: real traffic from ~105 IoT devices; 33 attack types in 7 categories (DDoS, DoS, reconnaissance, spoofing, Mirai, web-based, brute force) plus benign.
- **Already downloaded** — `Dataset/CSV/CSV/`, 8.4 GB. See §5.1 for a verified inventory of what is actually in it (it is not the release most papers describe).
- **Also needed later:** a *subset* of the matching **raw pcaps** from the same source — a few captures per category, not the whole set. These are required to validate the §6 extractor against the published CSVs. Start this download in Week 1 alongside the boards.

### Held-out — IoT-23 (cross-dataset test only)
- Source: Stratosphere Laboratory, CTU Prague. Free, direct download, no registration.
- Contents: 20 malware captures on real IoT hardware (Mirai, Okiru, Torii, Gagfyt, Hakai, Hide-and-Seek) plus 3 benign captures. **Ships raw pcaps** — which is the entire reason it is the held-out set here.
- **Never trained on.** Touched once, at the end, for the generalization result.

### Why not N-BaIoT — and why this matters

N-BaIoT was the original choice and it **does not work**. UCI publishes it as 115 pre-extracted statistical stream features (Host-IP, Host-MAC&IP, Channel and Socket aggregates over five decay windows) and **no pcaps**. Those 115 columns have *zero* overlap with CIC-IoT-2023's feature set, and with no pcaps there is no way to recompute a shared representation. A model trained on one cannot be evaluated on the other — not "with some effort", but at all. IoT-23 avoids this precisely because its pcaps let the §6 extractor emit the *identical* 39-feature vector on both sides.

**Why this pair works:** both contain botnet flood traffic including Mirai (a shared attack class for fair comparison), but different devices, different capture setups, and different years — so the cross-dataset test is meaningful, not a rerun.

> Note: dataset download links occasionally move. If a link differs from the above, use the institution's official dataset page rather than a random mirror.

---

## 5. Dataset inventory and preprocessing

### 5.1 What the download actually contains — verified, not assumed

Path: `Dataset/CSV/CSV/` — 34 per-attack folders of `*.pcap.csv`, **8.4 GB**, ~**43.2 M rows**. The label is the *folder name*; there is no label column.

| Property | Value |
|---|---|
| Feature columns | **39**, all numeric |
| Label column | **none** — label = folder name |
| Identifier columns (IP / MAC / port / timestamp / flow ID) | **none present** |
| Sliding window | **100 packets** (`Number` ∈ [1, 100]) |
| Total rows | ≈ 43.2 M |
| Largest class | DDoS-ICMP_Flood ≈ 6.4 M rows |
| Smallest class | Uploading_Attack ≈ 1,256 rows |
| Benign | ≈ 1.1 M rows |
| Imbalance ratio | ≈ 5000 : 1 |

This is the **39-feature per-attack release**, *not* the 46-feature merged release that most published papers use. Missing relative to that release: `flow_duration`, `Duration`, `Srate`, `Drate`, `urg_count`, `Magnitue`, `Radius`, `Covariance`, `Weight`. Four of those (`Magnitue`, `Radius`, `Covariance`, `Weight`) are algebraic functions of `Min`/`Max`/`AVG`/`Std`, which you do have, so the real information loss is small — but **state which release you used**, because reproducibility and comparability to published numbers depend on it.

### 5.2 Preprocessing steps

0. **Inspect a small sample first.** Already done — §5.1 is the result. Re-run the same inspection on anything new you add (pcap-derived rows especially).

1. ~~**Drop identifier columns.**~~ **Not applicable to this release.** There are no IP, MAC, port, timestamp, or flow-ID columns to leak, so the single biggest source of fake accuracy is already eliminated. This step *does* still apply to whatever you extract from raw pcaps in §6 — do not reintroduce identifiers there.

2. **Handle missing / infinite values — confirmed present.** `Rate` contains `Inf` (divide-by-zero on zero-duration windows); `Std` and `Variance` contain `NaN`. Both occur at roughly 6 per 100 k rows. Convert `±Inf` to `NaN`, then impute deliberately — do **not** blanket-`fillna(0)` on `Rate`, since 0 is a meaningful low value there. Use a large sentinel or a per-class median, and say in the paper which you chose.

3. **Deduplicate — confirmed necessary, and absent from most published pipelines.** Roughly **8 % of rows are exact duplicates** within a single class file. Duplicates straddling the train/test boundary are pure leakage. Deduplicate *before* splitting, and report how many rows you dropped.

4. **Drop algebraically redundant features — confirmed.** `Tot size` is byte-identical to `AVG`, and `Tot sum = AVG × Number`. Dropping both is free feature reduction with zero information loss: 39 → 37. Do this before the feature-importance work in §8 so the rankings are not split across duplicate columns.

5. **Choose label granularity.** 33-way is not viable — several classes have only 1–6 k rows. Use the **7 categories** (or binary for the floor model). The *Web* category (Backdoor_Malware, Uploading_Attack, XSS, SqlInjection, CommandInjection, BrowserHijacking) is the weak spot and will drag macro-F1; decide in Week 2 whether you report 7 categories with an honestly low Web number or 6 with a stated exclusion — and decide it *before* seeing which looks better.

6. **Scale / normalize.** Ranges differ wildly (`Variance` reaches 8.4 × 10⁷; flag features are 0–1). Fit the scaler **on the training set only**, then apply to val/test — fitting on everything leaks test information. Tree models do not need this; the MLP and 1D-CNN do.

7. **Split by capture file. Random splits are banned; timestamp splits are impossible.** There is no timestamp column in this release, so file-based grouping is the only honest option available: hold out whole `*.pcap.csv` files per class. **State the residual weakness honestly** — numbered files within a class (`DDoS-ICMP_Flood1.csv`, `…2.csv`, …) are sequential chunks of the *same* capture session, so a file split is only partially independent. It is a limitation, not a fatal one; the ~30-point drop it already produces (§7) shows it bites hard enough to be worth doing. For single-file classes, split by row position (first 50 % train, last 50 % test), never shuffled. Use **train / validation / test**: validation for tuning, test touched once at the end.

8. **Address class imbalance.** The ratio is ~5000 : 1. Subsample the majority classes and apply `class_weight='balanced'` on top. You do **not** need all 43 M rows — a stratified ~400 k-row sample trains a usable Random Forest in about two minutes on a laptop, which makes the whole Month-1 loop fast enough to iterate on. This imbalance is *why* macro-F1 is the metric, not accuracy.

9. ~~**Restrict to on-device-computable features.**~~ **Already satisfied — and this changes the framing.** CIC's extractor computes over a **100-packet sliding window**, not completed flows (`Number` never exceeds 100). Every remaining feature is a running counter, a protocol-flag rate, or a running mean/variance over that window — all computable on an ESP32 in constant memory. The "we sacrificed F1 for deployability" caveat the original plan expected to pay **does not apply here**. Say that plainly rather than inventing a sacrifice; the honest version is stronger. What this unlocks concretely is a fixed-size 100-packet ring buffer with a known byte cost, which is exactly what §6 builds.

---

## 6. The shared feature extractor (the spine of the project)

Both headline contributions run through one artifact: a **39-feature extractor** that turns raw packets into the same feature vector the CSVs contain. Write it once, in two forms.

1. **`extract.py` — Python reference.** Consumes a pcap (`scapy` or `dpkt`), emits CIC-IoT-2023-shaped rows over a 100-packet sliding window.
   **Acceptance test:** run it on a CIC-IoT-2023 pcap whose published CSV you already have and confirm the rows match within floating-point tolerance. Until this passes, nothing downstream is trustworthy. This test is the single highest-value thing you will write all project.
2. **`extract.c` — ESP32 port.** Same logic, fixed-size ring buffer, integer/fixed-point arithmetic where possible. Instrumented so extraction time is measured *separately* from inference time.

Why the plan is built around this:

- **It unblocks contribution #2.** With `extract.py`, IoT-23's pcaps become 39-feature rows in the same space as your training data. Without it there is no cross-dataset test at all — see §4.
- **It makes contribution #1 credible.** The C version is validated against the Python version, which is validated against the published CSVs. A latency number from unvalidated code proves nothing.
- **It costs no extra time.** The C extractor was always Weeks 7–8 work. Writing the Python reference first (Week 3) front-loads the design decisions and hands you a correctness oracle for the hard part.

**Scope discipline:** the extractor reads pcap *files*. It does **not** do live promiscuous capture — that is a rabbit hole and not the contribution (§9).

---

## 7. Models (train from scratch — there is no pre-trained model)

Pre-trained models exist for images and text because those inputs are universal. The input here is a row of dataset-specific network features, so nothing transfers and nothing is downloaded. Training from scratch is the correct, standard, and *easier* path — these models train in seconds to minutes on a laptop, no GPU needed.

Baselines (set the accuracy ceiling):
- **Random Forest** (scikit-learn)
- **XGBoost**
- **Small MLP** (2 hidden layers, Keras/PyTorch)
- **1D-CNN** over a packet window

Reporting metric: **macro-F1 and per-class F1**, never plain accuracy. Macro-F1 computes F1 per class then averages with equal weight, so a rare attack class counts as much as a common one — exactly what security needs.

### Measured anchor (already obtained)

A 60-tree Random Forest on a 400 k-row stratified sample with a **file-held-out 7-category split** scores **macro-F1 0.668**, in about two minutes on a laptop:

| Class | F1 |
|---|---|
| Mirai | 0.994 |
| DDoS | 0.860 |
| Recon | 0.790 |
| Spoofing | 0.669 |
| DoS | 0.656 |
| Benign | 0.568 |
| BruteForce | 0.493 |
| Web | 0.312 |

Published results on this dataset routinely report ~0.99 — using random splits. **The ~30-point gap is itself a result**, and it is the empirical backing for the honesty framing in §3. Two consequences for how you run the rest of the project:

- Your compressed on-device models are competing against **~0.67, not ~0.99**. A tiny model losing two points against an honest ceiling is a far better story than the same two points against an inflated one.
- Web and BruteForce are the classes that will move macro-F1. Effort spent there is worth more than effort spent squeezing DDoS from 0.86 to 0.88.

*Expectation:* on tabular flow features, tree-based models (RF/XGBoost → compiled ensemble) often beat the neural nets on both accuracy and latency. Reporting that honestly is a more interesting finding than confirming NN superiority.

---

## 8. Compression / "shrinking" (the engineering core)

The laptop models are far too big for the chip; making them fit without destroying accuracy is the core work. Compare paths on identical hardware — the *comparison* is the point, not any single winner.

| Path | What it does | Effort | Risk | Keep? |
|---|---|---|---|---|
| **Feature reduction** | Use top-N features (40→20→10→5); shrinks input *and* model, and cuts on-device feature-computation cost | ~1 day | Very low | Always — safest win |
| **Int8 quantization** | 32-bit weights → 8-bit; 4× smaller, faster integer math | ~1 day | Very low | Always |
| **Compiled tree ensemble** | Shallow trees compiled to nested C `if`-statements (`emlearn`/`micromlgen`); tiny, extremely fast | 1–2 days | Low | Always — likely best performer |
| **Distillation** | Big "teacher" trains a tiny "student" to imitate its soft outputs | 3–4 days | Medium | Keep if time allows — most interesting to discuss |
| **Pruning** | Zero out small weights | 4–5 days | High | Drop first — TFLite Micro ignores unstructured sparsity, so the file doesn't actually shrink. Use *structured* pruning, or report the null result honestly |

**Baseline floor model:** also train a deliberately tiny model (logistic regression or a depth-6 tree) that fits anywhere. It anchors the bottom of the tradeoff curve and answers "do you even need the complicated thing?"

---

## 9. Hardware

Order in **week one** — shipping is the one delay that cannot be coded around.

### Essential (~$45)
| Item | Exact part | Qty | ~Cost | Why |
|---|---|---|---|---|
| Main board | **ESP32-S3-DevKitC-1-N16R8** (16 MB flash, 8 MB PSRAM) | 2 | $12–15 ea | S3 has vector (SIMD) instructions → fair NN-vs-tree fight; PSRAM holds feature buffers. Second board is spare insurance. |
| Power sensor | **INA219** breakout | 1 | ~$5 | Energy-per-inference — the x-axis of the headline figure. Non-negotiable. |
| Cables | Known-good **USB-C data** cables (not charge-only) | 2 | ~$8 | Charge-only cables cause "won't flash" panics. |

### Recommended (cheap, adds a result)
| Item | Exact part | Qty | ~Cost | Why |
|---|---|---|---|---|
| Contrast board | **Original ESP32 (WROOM-32) DevKit** | 1 | ~$5 | No SIMD → free "vector instructions move the crossover point" result |
| Breadboard | Half-size | 1 | ~$3 | Wire the INA219 |
| Jumper wires | M-F + M-M pack | 1 | ~$4 | Connect INA219 |

**Do NOT buy:** sensors/cameras/displays you won't use, ESP32-CAM, and (for the core project) a Jetson/Raspberry Pi — a 4 GB + GPU board makes the "constrained" premise collapse. Borrow those from the edge lab only if doing the optional hardware-ladder version. Buy the S3 from a reputable seller (clone PSRAM causes mystery crashes); get the INA219 with headers pre-soldered if not comfortable soldering.

**Input method:** feed the test set to the board by **replaying rows over the serial port**, not live WiFi capture (promiscuous-mode sniffing is a rabbit hole and not the contribution). Replay is honest, reproducible, and lets you confirm on-device predictions match the laptop exactly.

---

## 10. On-device measurement

Measure per model, **on the device**:

| Metric | How |
|---|---|
| Flash + RAM footprint | Build output + runtime heap probe |
| Inference latency | Hardware timer, averaged over ~1000 runs |
| Energy per inference | INA219 (or USB power meter) |
| On-device accuracy | Replay the test set through the device; confirm it matches the laptop (catches quantization bugs) |
| Throughput under load | Packets/sec the device can inspect before dropping traffic |

Latency measured on a laptop is worthless here — the whole claim rests on real-hardware numbers. Also run the S3-vs-plain-ESP32 comparison for the SIMD result, and measure **on-device feature extraction** cost separately from inference (this is what proves contribution #1). The extraction path being timed is `extract.c` from §6 — and it only counts if its outputs match the `extract.py` reference row-for-row.

---

## 11. Headline figure

One plot carries the paper: **detection F1 (y) vs. energy-per-inference (x)**, every model plotted, the Pareto frontier drawn through the dominant points, colored by hardware tier. Real measured numbers. Most undergrad projects — and many published papers — lack this.

---

## 12. Timeline (3 months)

**Month 1 — laptop only (no hardware dependency).** A complete "floor" paper exists by the end of this month, before touching hardware.
- Wk 1: order boards; start the CIC-IoT-2023 **raw-pcap subset** download and grab IoT-23; build the §5.2 pipeline (dedup → NaN/Inf → drop redundant cols → file-grouped 7-category split) and **save the splits to disk** so every later experiment uses identical data.
- Wk 2: baselines (RF, XGBoost, MLP, 1D-CNN); macro-F1; lock the accuracy ceiling against the 0.668 anchor. Decide 7-vs-6 categories here.
- Wk 3: **`extract.py` + its acceptance test against the published CSVs** (§6) — this is now critical path. Then feature reduction and the CPU-side compression paths (quantization, compiled trees, distillation).
- Wk 4: run `extract.py` over IoT-23 pcaps; cross-dataset test (contribution #2 — done and safe before any hardware exists).

**Month 2 — hardware + contribution #1.**
- Wk 5: toolchain; one quantized model running via `esp-tflite-micro`; confirm on-device predictions match laptop.
- Wk 6: all model families on the S3; measure size, latency, energy.
- Wk 7–8: **port `extract.py` to `extract.c`** and measure it on-device (the hard part — budget the full two weeks and expect toolchain pain). The Week 3 Python version is your correctness oracle: every C output must match it before any timing number counts. Add S3-vs-plain-ESP32 runs.

**Month 3 — write.**
- Wk 9: throughput-under-load; finalize all numbers.
- Wk 10: headline figure; draft methods + results.
- Wk 11: intro, related work, discussion; have someone read it cold for overclaiming.
- Wk 12: tighten, format for venue, push to arXiv. Buffer for slippage.

---

## 13. Final demo (end of project)

A staged ~10-minute demo where theatre pulls them in and numbers earn the marks.

1. **Problem (30 s)** — devices get hacked, too weak for normal security, so detection goes on the device.
2. **Live demo (2 min)** — laptop replays unseen traffic over serial; ESP32 detects on-chip; **LED flips green→red** (and/or OLED shows "DDoS DETECTED"). Narrate: *"the laptop only feeds data — the chip is deciding."*
3. **Prove it's on-device (1 min)** — show serial output with the device's own prediction, on-chip latency (ms), and memory footprint. Optional: run from a battery to prove autonomy.
4. **Numbers (3 min)** — three slides: headline F1-vs-energy figure; feature-extraction-dominates breakdown; cross-dataset drop.
5. **Limitations (1 min)** — the honest cross-dataset number and next steps; ending on honesty reads as maturity.
6. **Buffer / questions.**

**Make-or-break:** rehearse and pre-load everything; record a **backup video** the night before in case hardware sulks; make the attack moment a big, unmistakable state change visible across the room.

**Progressive demo ladder** (what you can show *before* the end):
- First meeting (nothing built): the plan + one-page proposal.
- After ~Month 1 (laptop only): software demo — replay traffic through the trained model, print `BENIGN … ATTACK DETECTED (DDoS)` as rows stream. Build this early; it's also your debugging tool and becomes the ESP32 demo later.
- After Month 2: the physical blinking-board demo.

---

## 14. Risks and how the plan absorbs them

- **Boards arrive late** → order week one; all of Month 1 runs without them.
- **ESP32 toolchain fights back** → laptop-first sequencing means a complete (thinner) paper already exists by end of Month 1.
- **`extract.py` cannot reproduce the published CSVs** → this is the new critical-path risk, and it is exactly why the acceptance test sits in Week 3 rather than Week 7. Fallback if exact reproduction proves impossible: define **your own** feature set and apply it consistently to both datasets. The cross-dataset comparison stays valid (same extractor on both sides); you lose only direct comparability to published CIC numbers. Document the fallback if you take it.
- **On-device C runs long** → the single hardest item; the Month 3 buffer week absorbs slippage, and the Week 3 Python reference removes the design work from that window.
- **Fake-high accuracy** → deduplicate before splitting, file-grouped splits, macro-F1, cross-dataset test. Already measured: honest splits cost ~30 F1 points on this data.
- **Web category drags macro-F1** → decide in Week 2 whether to report 7 categories with an honestly weak Web number or 6 with a stated exclusion. Do not make that call after seeing which looks better.
- **Overclaiming** → claim narrow, prove fully; cold read for overclaims in Wk 11.
- **Scope creep / testbed-building** → public data only; skip live capture, adversarial work, and extra datasets unless time is easy.

---

## 15. Honest assessment

For an undergraduate project / first paper: strong (top-decile). Its strengths are real hardware measurements, a genuine thesis (not just an artifact), deliberate honesty where others cheat, a single shared extractor that makes the cross-dataset claim airtight instead of a tooling artifact, and scope that actually finishes. Its ceiling: the novelty is in *measurement and reframing*, not a new algorithm or state-of-the-art accuracy, so the correct venue is a **student workshop / poster track / co-located workshop + arXiv**, not a top-tier main track. Career/interview value is disproportionately high because every number is defensible. The entire quality rests on executing the honesty — do that and it is genuinely very good.

---

## 16. Immediate next actions

1. **Order** 2× ESP32-S3-DevKitC-1-N16R8 + INA219 + good USB-C data cables (add plain ESP32, breadboard, jumpers if possible).
2. **Download** a subset of CIC-IoT-2023 **raw pcaps** (needed to validate `extract.py`) and the IoT-23 captures. The CSVs are already in place at `Dataset/CSV/CSV/`.
3. **Build** the §5.2 preprocessing pipeline and persist the splits to disk. Everything downstream reads those files and nothing re-splits.
4. **Write** the one-page proposal for supervisor sign-off, using the measured 0.668 anchor as evidence that a working floor already exists.

---

## 17. Resume / keyword value

Edge computing, edge intelligence, TinyML, on-device ML, model quantization, knowledge distillation, TensorFlow Lite Micro, embedded C, ESP32, network intrusion detection, anomaly detection, pcap feature extraction, cross-dataset generalization. Strongest bullets are measured: *"Deployed an int8-quantized IDS on ESP32-S3 (X KB RAM), Y F1 at Z ms/inference; showed feature extraction costs N× more than inference on-device."*
