// Academic-format deck (title, abstract, introduction, literature, gaps, method, architecture, technology, output x2, conclusion, references)
// in the navy/cream style of the user's reference. Same real screenshot assets as before.
const pptxgen = require("pptxgenjs");
// Optional: writes the navy/cream theme colours into the .pptx. Point PPTX_APPLY_THEME at an
// apply_theme.js helper if you have one; without it the deck still builds with the same look.
const applyTheme = (() => { try { return require(process.env.PPTX_APPLY_THEME || "./apply_theme.js").applyTheme; }
                            catch (e) { return async () => {}; } })();

const path = require("path");
const A = path.join(__dirname, "assets") + "/";
const OUT = path.join(__dirname, "..", "IoT_IDS_ESP32_Presentation.pptx");

const THEME = {
  name: "Navy Bold IDS", headFontFace: "Impact", bodyFontFace: "Segoe UI",
  colors: { dk1: "384168", lt1: "F8F6E2", dk2: "1B1F2E", lt2: "C9CDE0", accent1: "A9B1D6", accent2: "F8F6E2", accent3: "FF5F57", accent4: "8AE28A", accent5: "8B93B8", accent6: "2A3045", hlink: "A9B1D6", folHlink: "C9CDE0" },
};
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "Lightweight IoT Intrusion Detection on an ESP32";
pres.author = "IoT IDS project";
const C = pres.SchemeColor;
const CREAM = C.background1, NAVY = C.text1, MUTED = C.background2;
pres.defineSlideMaster({ title: "BASE", background: { path: A + "bg_navy.png" }, objects: [], slideNumber: { x: 12.4, y: 7.0, w: 0.6, h: 0.3, fontSize: 10, color: THEME.colors.lt2, align: "right" } });
pres.defineSlideMaster({ title: "COVER", background: { path: A + "bg_navy.png" }, objects: [] });

const W = 13.33;
function big(slide, lines, x, y, size, opts = {}) {
  const lh = size / 72 * 0.92;
  lines.forEach((t, i) => slide.addText(t, { x, y: y + i * lh, w: opts.w || (W - x - 0.4), h: lh + 0.1, fontFace: "Impact", fontSize: size, color: CREAM, margin: 0, isTextBox: true, align: opts.align || "left", charSpacing: 2, objectName: "title " + t }));
  return y + lines.length * lh;
}
function label(slide, text, x, y, w, opts = {}) {
  slide.addText(text.toUpperCase(), { x, y, w, h: opts.h || 0.35, fontFace: "Segoe UI Semibold", fontSize: opts.size || 13, color: opts.color || CREAM, margin: 0, isTextBox: true, charSpacing: 1, align: opts.align || "left", objectName: "label " + text });
}
function para(slide, text, x, y, w, h, size = 12, opts = {}) {
  slide.addText(text, { x, y, w, h, fontFace: "Segoe UI", fontSize: size, color: opts.color || MUTED, margin: 0, isTextBox: true, valign: "top", lineSpacingMultiple: 1.12, align: opts.align || "left", objectName: "text" });
}
function bullets(slide, items, x, y, w, h, size = 12, opts = {}) {
  slide.addText(items.map((t, i) => ({ text: t, options: { bullet: opts.numbered ? { type: "number", indent: 18 } : { indent: 14 }, breakLine: i < items.length - 1, paraSpaceAfter: opts.gap || 5 } })),
    { x, y, w, h, fontFace: "Segoe UI", fontSize: size, color: opts.color || MUTED, margin: 0, isTextBox: true, valign: "top", objectName: "bullets" });
}
function stat(slide, num, text, x, y, w = 2.3, size = 48) {
  slide.addText(num, { x, y, w, h: 0.9, fontFace: "Impact", fontSize: size, color: CREAM, margin: 0, isTextBox: true, objectName: "stat " + num });
  slide.addText(text.toUpperCase(), { x, y: y + 0.92, w, h: 0.5, fontFace: "Segoe UI Semibold", fontSize: 11, color: MUTED, margin: 0, isTextBox: true, valign: "top", objectName: "stat label" });
}
function numbered(slide, n, title, body, x, y, w, bodyH = 1.0, size = 11.5) {
  slide.addText(String(n), { x, y, w: 0.6, h: 0.5, fontFace: "Impact", fontSize: 24, color: CREAM, margin: 0, isTextBox: true, objectName: "num " + n });
  label(slide, title, x, y + 0.52, w, { size: 13 });
  para(slide, body, x, y + 0.9, w, bodyH, size);
}
function shot(slide, file, x, y, w, h) {
  slide.addImage({ path: A + file, x, y, w, h, sizing: { type: "contain", w, h }, objectName: file, shadow: { type: "outer", blur: 8, offset: 3, angle: 90, color: "000000", opacity: 0.45 } });
}
function box(slide, t, d, x, y, w, h, filled = false, size = 11.5) {
  slide.addShape(pres.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.08, fill: filled ? { color: CREAM } : { color: THEME.colors.dk1, transparency: 100 }, line: { color: CREAM, width: 1.5 }, objectName: "box " + t });
  const runs = [{ text: t, options: { bold: true, fontSize: size, breakLine: !!d } }];
  if (d) runs.push({ text: d, options: { fontSize: size - 2.5 } });
  slide.addText(runs, { x: x + 0.08, y, w: w - 0.16, h, fontFace: "Segoe UI", color: filled ? NAVY : CREAM, align: "center", valign: "middle", margin: 0, isTextBox: true, objectName: "box text " + t });
}
function chev(slide, x, y, w = 0.16, h = 0.2, rot = 0) {
  slide.addShape(pres.ShapeType.chevron, { x, y, w, h, rotate: rot, fill: { color: CREAM }, line: { color: CREAM, width: 0 }, objectName: "arrow" });
}
function flow(slide, steps, x, y, w, h, opts = {}) {
  const gap = 0.28, n = steps.length, bw = (w - gap * (n - 1)) / n;
  steps.forEach((s, i) => {
    const bx = x + i * (bw + gap);
    box(slide, s.t, s.d, bx, y, bw, h, opts.fill && opts.fill.includes(i), opts.size || 11.5);
    if (i < n - 1) chev(slide, bx + bw + 0.06, y + h / 2 - 0.1);
  });
}
const chartBase = {
  chartColors: [THEME.colors.lt1], catAxisLabelColor: THEME.colors.lt2, valAxisLabelColor: THEME.colors.lt2, catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
  catAxisLabelFontSize: 10, valAxisLabelFontSize: 9, dataLabelColor: THEME.colors.lt1, dataLabelFontFace: "+mn-lt", dataLabelFontSize: 9,
  valGridLine: { color: THEME.colors.accent6, size: 0.5 }, catGridLine: { style: "none" }, showLegend: false, catAxisLineShow: false, valAxisLineShow: false,
  showTitle: true, titleColor: THEME.colors.lt1, titleFontFace: "+mn-lt", titleFontSize: 11, plotArea: { fill: { color: THEME.colors.dk1, transparency: 100 } }, chartArea: { fill: { color: THEME.colors.dk1, transparency: 100 } },
};
const cell = (c, i) => ({ text: c, options: { bold: i === 0, color: i === 0 ? THEME.colors.lt2 : THEME.colors.lt1, fontSize: i === 0 ? 10 : 11, fontFace: "Segoe UI", align: "left", valign: "top", fill: { color: THEME.colors.dk1, transparency: 100 }, border: [{ type: "none" }, { type: "none" }, { type: "solid", color: THEME.colors.accent6, pt: 0.75 }, { type: "none" }], margin: [4, 5, 4, 5] } });

// ============ 1. TITLE + STUDENT DETAILS ============
pres.addSection({ title: "Front" });
{
  const s = pres.addSlide({ masterName: "COVER", sectionTitle: "Front" });
  s.addText("PROJECT PRESENTATION", { x: 0.75, y: 0.5, w: 8, h: 0.5, fontFace: "Segoe UI Light", fontSize: 22, color: CREAM, margin: 0, isTextBox: true, objectName: "kicker" });
  big(s, ["INTRUSION", "DETECTION"], 0.75, 1.0, 140);
  s.addText("LIGHTWEIGHT IoT INTRUSION DETECTION\nON AN ESP32 MICROCONTROLLER", { x: 9.55, y: 1.1, w: 3.4, h: 1.0, fontFace: "Segoe UI Semibold", fontSize: 13, color: CREAM, margin: 0, isTextBox: true, objectName: "tag" });
  s.addShape(pres.ShapeType.rect, { x: 3.1, y: 2.3, w: 7.1, h: 1.25, fill: { color: THEME.colors.dk2 }, line: { color: CREAM, width: 1.5 }, objectName: "strip frame" });
  s.addImage({ path: A + "shot_demo.png", x: 3.15, y: 2.35, w: 7.0, h: 1.15, sizing: { type: "cover", w: 7.0, h: 1.15 }, objectName: "demo strip" });
  label(s, "Submitted by", 0.75, 4.75, 4, { size: 11, color: MUTED });
  s.addText("[STUDENT NAME]  -  [ROLL NUMBER]\n[STUDENT NAME]  -  [ROLL NUMBER]", { x: 0.75, y: 5.05, w: 6.0, h: 0.8, fontFace: "Segoe UI Semibold", fontSize: 15, color: CREAM, margin: 0, isTextBox: true, valign: "top", objectName: "students" });
  label(s, "Guide", 7.3, 4.75, 3, { size: 11, color: MUTED });
  s.addText("[GUIDE NAME], [DESIGNATION]", { x: 7.3, y: 5.05, w: 5.5, h: 0.4, fontFace: "Segoe UI Semibold", fontSize: 15, color: CREAM, margin: 0, isTextBox: true, objectName: "guide" });
  label(s, "Department", 7.3, 5.5, 3, { size: 11, color: MUTED });
  s.addText("[DEPARTMENT], [COLLEGE NAME]", { x: 7.3, y: 5.8, w: 5.5, h: 0.4, fontFace: "Segoe UI Semibold", fontSize: 15, color: CREAM, margin: 0, isTextBox: true, objectName: "department" });
  s.addText("NOVEMBER 2026", { x: 0.75, y: 6.6, w: 4, h: 0.4, fontFace: "Segoe UI", fontSize: 14, color: CREAM, margin: 0, isTextBox: true, objectName: "date" });
  s.addText("CIC-IoT-2023  ->  RANDOM FOREST  ->  ESP32-WROOM-32", { x: 6.3, y: 6.6, w: 6.3, h: 0.4, fontFace: "Segoe UI", fontSize: 14, color: CREAM, align: "right", margin: 0, isTextBox: true, objectName: "byline" });
  s.addNotes("Fill in the student names, roll numbers, guide and department on this slide. The strip across the title is the live demo output from the ESP32.");
}

// ============ 2. ABSTRACT ============
{
  const s = pres.addSlide({ masterName: "BASE", sectionTitle: "Front" });
  big(s, ["ABSTRACT"], 0.6, 0.35, 96);
  para(s, "Internet of Things devices are cheap, numerous and rarely protected, which makes them the preferred target of botnets such as Mirai. Most intrusion detection systems for IoT run on servers in the cloud, where every packet must first travel off the device. This project asks whether a useful detector can run on the device class itself: a $5 ESP32 microcontroller with 4 MB of flash and 320 KB of RAM.\n\nA random forest was trained on the CIC-IoT-2023 dataset (46.8 million flow records, 33 attack types) using a leak-free, file-grouped split so that test traffic comes from captures the model never saw. The forest was compressed from 958 MB to 240 KB by selecting 25 of 37 features, limiting it to 30 trees of depth 10, and grouping the attacks into five classes (Benign, Flood, Mirai, Probe, Spoofing). The emlearn library converted it to plain C, which was compiled into an Arduino sketch and flashed to the ESP32.\n\nOn the chip the model reaches 98.6% accuracy on a realistic traffic mix and 84.3% balanced accuracy, matches the laptop prediction on 100% of 2,000 test rows, and classifies a flow in 295 microseconds on average, about 3,400 flows per second. A live demonstration replays held-out traffic over USB and lights the on-board LED when the chip detects an attack.", 0.6, 1.95, 7.9, 4.9, 12.5, { color: CREAM });
  stat(s, "98.6%", "accuracy, real-traffic mix", 9.1, 2.0, 3.6);
  stat(s, "240 KB", "model flash footprint", 9.1, 3.55, 3.6);
  stat(s, "295 us", "per flow on the ESP32", 9.1, 5.1, 3.6);
  s.addNotes("Read the abstract in three beats: the problem, the method, the result. Every number on this slide is measured on the real board or on the held-out test set.");
}

// ============ 3. INTRODUCTION / MOTIVATION ============
pres.addSection({ title: "Background" });
{
  const s = pres.addSlide({ masterName: "BASE", sectionTitle: "Background" });
  big(s, ["INTRODUCTION"], 0.6, 0.35, 96);
  label(s, "Motivation", 0.6, 1.75, 4, { size: 12, color: MUTED });
  flow(s, [{ t: "Billions of IoT devices", d: "cameras, plugs, sensors" }, { t: "Weak security", d: "default passwords, no updates" }, { t: "Botnets recruit them", d: "Mirai, Gafgyt, Okiru" }, { t: "Floods and scans", d: "DDoS, DoS, Recon, Spoofing" }, { t: "Cloud IDS is late", d: "packets leave the device first" }], 0.6, 2.15, W - 1.2, 0.9, { fill: [4] });
  numbered(s, 1, "The problem", "IoT devices cannot run the deep models used by server-side intrusion detection. They have kilobytes of RAM, no operating system and no GPU, so detection is pushed to the cloud and the device itself stays blind.", 0.6, 3.5, 3.8, 1.7);
  numbered(s, 2, "The idea", "Put a small but honest classifier on the microcontroller class that IoT devices are built from. If an ESP32 can tell a flood from normal traffic in microseconds, an IoT device can raise an alarm on its own.", 4.75, 3.5, 3.8, 1.7);
  numbered(s, 3, "The goal", "Train on a large public IoT attack dataset, compress the model until it fits in flash, convert it to C, deploy it on a real ESP32 and prove that the chip gives the same answers as the laptop.", 8.9, 3.5, 3.8, 1.7);
  stat(s, "$5", "cost of the ESP32 board", 0.6, 5.75, 2.4, 40);
  stat(s, "4 MB", "flash memory in total", 3.3, 5.75, 2.4, 40);
  stat(s, "320 KB", "RAM in total", 6.0, 5.75, 2.4, 40);
  stat(s, "240 MHz", "dual-core CPU, no GPU", 8.7, 5.75, 3.0, 40);
  s.addNotes("Motivation: the devices being attacked are exactly the devices that cannot run today's detectors. The ESP32 is the chip inside many real IoT products, so it is a fair target.");
}

// ============ 4. LITERATURE SURVEY ============
{
  const s = pres.addSlide({ masterName: "BASE", sectionTitle: "Background" });
  big(s, ["LITERATURE", "SURVEY"], 0.6, 0.35, 88);
  const rows = [
    ["#", "WORK", "WHAT IT DID", "WHAT IT LEFT OPEN"],
    ["1", "Neto et al., 2023 (CICIoT2023)", "Published a large real-device IoT attack dataset: 105 devices, 33 attacks, flow features; reported baseline classifiers (RF, LR, AdaBoost, DNN).", "Baselines are evaluated on a laptop with a random split; no deployment on constrained hardware."],
    ["2", "Meidan et al., 2018 (N-BaIoT)", "Botnet detection on 9 commercial IoT devices using per-device deep autoencoders over 115 statistical features.", "Features are pre-extracted and no raw captures are released; deep autoencoders are too large for a microcontroller."],
    ["3", "Koroniotis et al., 2019 (Bot-IoT)", "Simulated IoT testbed dataset with DDoS, DoS, scanning and theft; evaluated SVM, RNN and LSTM detectors.", "Traffic is from a simulated network; models are server-side and heavy."],
    ["4", "Nordby, 2019 (emlearn)", "A converter that turns scikit-learn tree ensembles into dependency-free C for microcontrollers.", "A tool, not a study: it does not say how accurate a compressed IDS forest remains on a real chip."],
    ["5", "David et al., 2021 (TensorFlow Lite Micro)", "Framework for running small neural networks on microcontrollers with no OS or dynamic memory.", "Targets neural networks; tree ensembles are usually smaller and faster for tabular flow features."],
  ];
  s.addTable(rows.map((r, i) => r.map((c) => cell(c, i))), { x: 0.6, y: 2.75, w: W - 1.2, colW: [0.4, 2.7, 4.6, 4.43], rowH: 0.6, objectName: "literature table" });
  s.addNotes("Five representative works: three datasets and two deployment tools. The pattern is that detection accuracy is studied on servers and deployment tools are studied without an IDS workload. This project joins the two.");
}

// ============ 5. RESEARCH GAPS ============
{
  const s = pres.addSlide({ masterName: "BASE", sectionTitle: "Background" });
  big(s, ["RESEARCH", "GAPS"], 0.6, 0.35, 88);
  para(s, "Reading the survey side by side, four gaps appear between what is published and what an IoT device actually needs.", 7.2, 0.5, 5.6, 1.0, 12);
  numbered(s, 1, "Optimistic evaluation", "Published IoT IDS results are usually computed on random train/test splits of the same captures, which lets near-duplicate rows leak across the split and inflates accuracy. Few papers group the split by source file.", 0.6, 2.85, 5.8, 1.5);
  numbered(s, 2, "No deployment", "Models are trained and scored on laptops or servers. Flash size, RAM use and latency on a real microcontroller are rarely reported, so it is unknown whether the published model could run where the attack happens.", 7.0, 2.85, 5.8, 1.5);
  numbered(s, 3, "Model size versus chip size", "Deep detectors and large forests are hundreds of megabytes. A typical IoT microcontroller has a few megabytes of flash, so the detector must be compressed by three orders of magnitude without losing its value.", 0.6, 4.95, 5.8, 1.6);
  numbered(s, 4, "Unverified conversion", "Converting a trained model to C changes how it votes and how it rounds floats. Without a row-by-row parity check against the original, the on-device accuracy is only assumed, never shown.", 7.0, 4.95, 5.8, 1.6);
  s.addNotes("Each gap maps to one design decision in the method: file-grouped split, real ESP32 deployment, feature and tree compression, and the 100% parity test.");
}

// ============ 6. PROPOSED METHOD ============
pres.addSection({ title: "Method" });
{
  const s = pres.addSlide({ masterName: "BASE", sectionTitle: "Method" });
  big(s, ["PROPOSED", "METHOD"], 0.6, 0.35, 88);
  para(s, "An end-to-end pipeline of seven numbered scripts. Each stage writes its results to disk so every number in this deck can be traced back to a file.", 7.2, 0.5, 5.6, 1.0, 12);
  flow(s, [{ t: "Inventory", d: "01_inventory" }, { t: "Build dataset", d: "02_build_dataset" }, { t: "Baselines", d: "03_train_baselines" }, { t: "Features + model", d: "04 + 05" }, { t: "Compile to C", d: "06_export_to_c" }, { t: "Deploy + size", d: "07_measure_footprint" }, { t: "Verify + demo", d: "08_parity / 09_demo" }], 0.6, 2.75, W - 1.2, 0.8, { size: 10.5 });
  shot(s, "shot_build.png", 0.6, 3.85, 6.6, 3.1);
  numbered(s, 1, "Leak-free data", "46.8M rows deduplicated (-9.4%), NaN/Inf fixed, two redundant columns dropped, then split 70/15/15 by source file so no capture appears in two splits. Leak check: OK.", 7.5, 3.75, 5.3, 0.8, 11);
  numbered(s, 2, "Compression", "37 -> 25 features by importance; 200 trees of unlimited depth -> 30 trees of depth 10; attacks grouped into 5 classes. Scored with hard voting, exactly as the C code votes.", 7.5, 5.35, 5.3, 0.9, 11);
  s.addNotes("The screenshot is the real build report. The method's two non-obvious choices are the file-grouped split and scoring the sweep with hard voting, so the laptop number predicts the chip number.");
}

// ============ 7. ARCHITECTURE / MODEL ============
{
  const s = pres.addSlide({ masterName: "BASE", sectionTitle: "Method" });
  big(s, ["ARCHITECTURE"], 0.6, 0.35, 96);
  label(s, "Offline, on the laptop", 0.6, 1.8, 6, { size: 11, color: MUTED });
  flow(s, [{ t: "CIC-IoT-2023", d: "309 CSV files" }, { t: "Preprocess + split", d: "train / val / test" }, { t: "Random forest", d: "balanced class weights" }, { t: "Compress", d: "25 feats, 30 trees, d10" }, { t: "emlearn", d: "forest -> C header" }], 0.6, 2.15, W - 1.2, 0.8, { size: 11 });
  chev(s, 11.78, 3.05, 0.2, 0.3, 90);
  label(s, "Online, on the ESP32 (runs in 295 us per flow)", 0.6, 3.5, 7, { size: 11, color: MUTED });
  box(s, "Serial input", "25 floats per line, 115200 baud", 0.6, 3.85, 2.3, 0.8); chev(s, 2.96, 4.15);
  box(s, "Parse to float[25]", "strtod, same as laptop", 3.2, 3.85, 2.3, 0.8); chev(s, 5.56, 4.15);
  box(s, "predict()", "30 trees, hard vote", 5.8, 3.85, 2.3, 0.8, true); chev(s, 8.16, 4.15);
  box(s, "Class + time", "<class>,<micros>,<alert>", 8.4, 3.85, 2.3, 0.8); chev(s, 10.76, 4.15);
  box(s, "LED", "on for any attack", 11.0, 3.85, 1.73, 0.8);
  s.addChart(pres.ChartType.bar, [{ name: "Macro-F1", labels: ["Random Forest", "XGBoost", "MLP", "1D-CNN"], values: [0.672, 0.635, 0.597, 0.593] }],
    { ...chartBase, x: 0.6, y: 4.95, w: 5.6, h: 2.2, barDir: "bar", title: "Model selection: macro-F1 of the four baselines (8 classes)", showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.000", catAxisOrientation: "maxMin", valAxisHidden: true, valGridLine: { style: "none" } });
  label(s, "Deployed model", 6.6, 5.0, 4, { size: 12 });
  const spec = [["Algorithm", "Random forest, hard (majority) voting"], ["Size", "30 trees, depth 10, 26,376 nodes"], ["Inputs", "25 flow features (sizes, rate, IAT, TTL, TCP flags, protocol mix)"], ["Classes", "Benign, Flood, Mirai, Probe, Spoofing"], ["Footprint", "240 KB flash, 0 B static RAM, 520 KB total sketch"]];
  s.addTable(spec.map((r) => r.map((c, j) => ({ text: c, options: { bold: j === 0, color: j === 0 ? THEME.colors.lt2 : THEME.colors.lt1, fontSize: 10.5, fontFace: "Segoe UI", fill: { color: THEME.colors.dk1, transparency: 100 }, border: [{ type: "none" }, { type: "none" }, { type: "solid", color: THEME.colors.accent6, pt: 0.75 }, { type: "none" }], margin: [3, 4, 3, 4] } }))),
    { x: 6.6, y: 5.35, w: 6.2, colW: [1.3, 4.9], rowH: 0.33, objectName: "model spec" });
  s.addNotes("Two tiers. Everything above the arrow happens once on the laptop; everything below runs on the chip for every flow. The random forest was chosen because it scored highest of the four baselines and because trees compile to tiny branch-only C code.");
}

// ============ 8. TECHNOLOGY USED ============
{
  const s = pres.addSlide({ masterName: "BASE", sectionTitle: "Method" });
  big(s, ["TECHNOLOGY", "USED"], 0.6, 0.35, 88);
  const tech = [
    ["Python 3.13", "pandas, NumPy, scikit-learn for data and training"], ["CIC-IoT-2023", "46.8M labelled flow records, 33 attacks"],
    ["emlearn 0.23", "scikit-learn forest to plain C"], ["Arduino IDE + ESP32 core 3.3", "xtensa-gcc toolchain, esptool"],
    ["ESP32-WROOM-32 DevKit", "240 MHz, 4 MB flash, 320 KB RAM"], ["pyserial", "laptop to board link at 115200 baud"],
  ];
  tech.forEach(([t, d], i) => { const col = i % 2, row = Math.floor(i / 2); box(s, t, d, 7.2 + col * 2.9, 0.55 + row * 0.95, 2.7, 0.8, false, 11.5); });
  shot(s, "shot_header.png", 0.6, 3.55, 6.5, 3.5);
  shot(s, "shot_compile.png", 7.3, 3.55, 5.5, 1.7);
  label(s, "How the Python model becomes firmware", 7.3, 5.4, 5.5, { size: 11, color: MUTED });
  bullets(s, ["emlearn writes each tree as nested if/else on the 25-float feature array: 52,945 lines of C, no malloc, no library calls.", "The header is included in the Arduino sketch and compiled by xtensa-gcc into a 520 KB binary (39% of the app partition).", "Model-only footprint is measured by compiling the same sketch with the forest stubbed out: 240 KB."], 7.3, 5.75, 5.5, 1.3, 10.5);
  s.addNotes("Left: the real generated header. Right: the real compiler output for the demo sketch and for the baseline sketch without the forest. The difference between the two is the model's footprint.");
}

// ============ 9. OUTPUT: MODEL RESULTS ============
pres.addSection({ title: "Output" });
{
  const s = pres.addSlide({ masterName: "BASE", sectionTitle: "Output" });
  big(s, ["OUTPUT"], 0.6, 0.35, 96);
  label(s, "1 / 2  -  Classification results on the held-out test set", 0.6, 1.7, 7, { size: 11, color: MUTED });
  s.addImage({ path: A + "confusion.png", x: 0.5, y: 2.05, w: 5.8, h: 5.0, sizing: { type: "contain", w: 5.8, h: 5.0 }, objectName: "confusion matrix" });
  stat(s, "98.6%", "real-traffic accuracy", 6.7, 1.0, 2.1);
  stat(s, "84.3%", "balanced accuracy", 8.8, 1.0, 2.1);
  stat(s, "0.82", "macro-F1", 10.9, 1.0, 1.9);
  s.addChart(pres.ChartType.bar, [{ name: "F1", labels: ["Flood", "Mirai", "Probe", "Benign", "Spoofing"], values: [0.999, 0.998, 0.768, 0.681, 0.632] }],
    { ...chartBase, x: 6.6, y: 2.6, w: 6.2, h: 2.5, barDir: "bar", title: "Per-class F1 (hard voting, 286,197 test rows)", showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.000", catAxisOrientation: "maxMin", valAxisHidden: true, valGridLine: { style: "none" } });
  s.addChart(pres.ChartType.bar, [{ name: "Balanced accuracy", labels: ["8 classes (full forest)", "7 classes", "5 classes"], values: [77.1, 78.1, 84.3] }, { name: "Real-traffic accuracy", labels: ["8 classes (full forest)", "7 classes", "5 classes"], values: [76.6, 98.0, 98.6] }],
    { ...chartBase, chartColors: [THEME.colors.accent1, THEME.colors.lt1], x: 6.6, y: 5.15, w: 6.2, h: 2.0, barDir: "col", barGapWidthPct: 60, title: "Effect of class grouping (%)", showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "0.0", valAxisMinVal: 60, valAxisMaxVal: 100, showLegend: true, legendPos: "r", legendColor: THEME.colors.lt2, legendFontFace: "+mn-lt", legendFontSize: 9 });
  s.addNotes("Flood and Mirai are near perfect. Spoofing is the hardest class because 40% of it looks like normal traffic in these flow features. Train accuracy is 88.8% against 84.3% test, a four-point gap, so the forest is not overfitting.");
}

// ============ 10. OUTPUT: ON THE CHIP ============
{
  const s = pres.addSlide({ masterName: "BASE", sectionTitle: "Output" });
  big(s, ["OUTPUT"], 0.6, 0.35, 96);
  label(s, "2 / 2  -  Running on the ESP32: parity test and live demo", 0.6, 1.7, 7, { size: 11, color: MUTED });
  shot(s, "shot_parity.png", 0.6, 2.1, 6.0, 4.0);
  shot(s, "shot_demo.png", 6.9, 2.1, 5.9, 4.0);
  stat(s, "100%", "2,000 of 2,000 rows match the laptop", 0.6, 6.05, 3.2, 36);
  stat(s, "295 us", "mean inference, max 541 us", 3.9, 6.05, 2.8, 36);
  stat(s, "96%", "attack flows flagged (demo)", 6.9, 6.05, 3.0, 36);
  stat(s, "87%", "exact class correct (demo)", 9.9, 6.05, 2.4, 36);
  s.addNotes("Left: the parity test streams 2,000 held-out rows over USB; the chip's answer equals the laptop C build on every row. Right: the live demo replays six phases of traffic; the chip prints the class and lights the LED for attacks. Flood and Mirai were 35 for 35.");
}

// ============ 11. CONCLUSION AND FUTURE WORK ============
pres.addSection({ title: "Closing" });
{
  const s = pres.addSlide({ masterName: "BASE", sectionTitle: "Closing" });
  big(s, ["CONCLUSION &", "FUTURE WORK"], 0.6, 0.35, 88);
  label(s, "Conclusion", 0.6, 2.85, 5, { size: 13 });
  bullets(s, ["A random forest trained on CIC-IoT-2023 was compressed 4,000 times, from 958 MB to 240 KB, and runs on a $5 ESP32.", "On the chip it reaches 98.6% accuracy on a realistic traffic mix and 84.3% balanced accuracy, with Flood and Mirai detected almost perfectly.", "The chip reproduces the laptop prediction on 100% of 2,000 test rows and classifies a flow in 295 microseconds, about 3,400 flows per second.", "All numbers come from a leak-free, file-grouped split, so they reflect traffic the model had never seen."], 0.6, 3.25, 5.9, 3.7, 11.5, { gap: 7 });
  label(s, "Future work", 7.0, 2.85, 5, { size: 13 });
  bullets(s, ["Compute the 25 flow features on the ESP32 itself from live packets, so the device needs no laptop at all.", "Add alerting over Wi-Fi (MQTT or a small web page) and an OLED display so detections are visible on the device.", "Measure energy per inference with an INA219 current sensor and compare the forest against a small neural network on the same board.", "Improve Spoofing and Benign separation with time-window features that the current flow statistics do not capture."], 7.0, 3.25, 5.8, 3.7, 11.5, { gap: 7 });
  s.addNotes("Close on the two numbers that matter: 98.6% and 295 microseconds on a 5-dollar chip. Future work is ordered by how much it changes the demo: on-device feature extraction first.");
}

// ============ 12. REFERENCES ============
{
  const s = pres.addSlide({ masterName: "BASE", sectionTitle: "Closing" });
  big(s, ["REFERENCES"], 0.6, 0.35, 96);
  const refs = [
    "E. C. P. Neto, S. Dadkhah, R. Ferreira, A. Zohourian, R. Lu and A. A. Ghorbani, \"CICIoT2023: A Real-Time Dataset and Benchmark for Large-Scale Attacks in IoT Environment,\" Sensors, vol. 23, no. 13, 5941, 2023.",
    "Y. Meidan, M. Bohadana, Y. Mathov, Y. Mirsky, A. Shabtai, D. Breitenbacher and Y. Elovici, \"N-BaIoT: Network-Based Detection of IoT Botnet Attacks Using Deep Autoencoders,\" IEEE Pervasive Computing, vol. 17, no. 3, pp. 12-22, 2018.",
    "N. Koroniotis, N. Moustafa, E. Sitnikova and B. Turnbull, \"Towards the development of realistic botnet dataset in the Internet of Things for network forensic analytics: Bot-IoT dataset,\" Future Generation Computer Systems, vol. 100, pp. 779-796, 2019.",
    "J. Nordby, \"emlearn: Machine Learning inference engine for Microcontrollers and Embedded Devices,\" 2019. https://github.com/emlearn/emlearn",
    "R. David, J. Duke, A. Jain, V. J. Reddi, N. Jeffries, J. Li, N. Kreeger, I. Nappier, M. Natraj, S. Regev, R. Rhodes, T. Wang and P. Warden, \"TensorFlow Lite Micro: Embedded Machine Learning on TinyML Systems,\" Proceedings of Machine Learning and Systems (MLSys), 2021.",
    "L. Breiman, \"Random Forests,\" Machine Learning, vol. 45, no. 1, pp. 5-32, 2001.",
    "I. Sharafaldin, A. H. Lashkari and A. A. Ghorbani, \"Toward Generating a New Intrusion Detection Dataset and Intrusion Traffic Characterization,\" Proc. ICISSP, pp. 108-116, 2018.",
    "Espressif Systems, \"ESP32 Series Datasheet\" and \"Arduino core for the ESP32,\" https://github.com/espressif/arduino-esp32",
  ];
  bullets(s, refs, 0.6, 1.8, W - 1.2, 5.2, 11.5, { numbered: true, gap: 7, color: CREAM });
  s.addNotes("References in IEEE style. 1 is the dataset, 2 and 3 are the comparison datasets from the survey, 4 and 5 are the deployment tools, 6 is the algorithm, 7 is the CIC feature-extraction lineage, 8 is the hardware and toolchain.");
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
