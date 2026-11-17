import os, json, subprocess
import numpy as np, pandas as pd
from PIL import Image, ImageDraw, ImageFont
S = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))   # project root
os.makedirs(S, exist_ok=True)
NAVY, CREAM = (0x38, 0x41, 0x68), (0xF8, 0xF6, 0xE2)

# 1. grainy navy background like the reference
rng = np.random.default_rng(1)
bg = np.ones((1080, 1920, 3), np.float32) * np.array(NAVY, np.float32)
noise = rng.normal(0, 9, (1080, 1920, 1))
bg = np.clip(bg + noise, 0, 255).astype(np.uint8)
Image.fromarray(bg).save(f"{S}/bg_navy.png")

# 2. terminal-style screenshots of REAL outputs
MONO = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 26)
MONO_B = ImageFont.truetype("C:/Windows/Fonts/consolab.ttf", 26)
UI = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 22)


def shot(name, title, lines, width=1640, hl=()):
    lh = 34; pad = 28
    h = 56 + pad * 2 + lh * len(lines)
    im = Image.new("RGB", (width, h), (0x1B, 0x1F, 0x2E)); d = ImageDraw.Draw(im)
    d.rectangle([0, 0, width, 56], fill=(0x2A, 0x30, 0x45))
    for i, c in enumerate([(0xFF, 0x5F, 0x57), (0xFE, 0xBC, 0x2E), (0x28, 0xC8, 0x41)]):
        d.ellipse([22 + i * 30, 18, 42 + i * 30, 38], fill=c)
    d.text((120, 15), title, font=UI, fill=(0xC8, 0xCC, 0xD8))
    y = 56 + pad
    for ln in lines:
        col = (0xE6, 0xE8, 0xEF); f = MONO
        if ln.startswith("$ "): col = (0x8A, 0xE2, 0x8A)
        elif any(k in ln for k in hl): col = (0xF8, 0xF6, 0xE2); f = MONO_B
        elif ln.startswith("#") or ln.startswith("=="): col = (0x8F, 0x9B, 0xC4)
        d.text((pad, y), ln[:130], font=f, fill=col); y += lh
    im.save(f"{S}/{name}.png"); print("wrote", name, im.size)


def R(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout.rstrip("\n").split("\n")


# dataset listing (real)
folders = sorted(f for f in os.listdir("Dataset/CSV/CSV") if os.path.isdir("Dataset/CSV/CSV/" + f))
csvs = sum(len([x for x in os.listdir("Dataset/CSV/CSV/" + f) if x.endswith(".csv")]) for f in folders)
head = pd.read_csv("Dataset/CSV/CSV/DDoS-ICMP_Flood/DDoS-ICMP_Flood.pcap.csv", nrows=3)
lines = ["$ ls Dataset/CSV/CSV/"] + ["  ".join(folders[i:i + 6]) for i in range(0, len(folders), 6)]
lines += [f"# {len(folders)} attack folders, {csvs} CSV files, 8.4 GB, 46,776,700 rows, no label column (label = folder name)", "",
          "$ head -3 Dataset/CSV/CSV/DDoS-ICMP_Flood/DDoS-ICMP_Flood.pcap.csv",
          ",".join(head.columns[:9]) + ",...  (39 numeric features)"]
lines += [",".join(f"{v:g}" for v in r[:9]) + ",..." for r in head.values]
shot("shot_dataset", "PowerShell  -  Dataset inventory (Inspection.py)", lines)

# build report (real)
br = json.load(open("data_out/build_report.txt"))
lines = ["$ python 03_build_dataset.py", "$ cat data_out/build_report.txt"]
for sp in ("train", "val", "test"):
    b = br[sp]
    lines.append(f'  "{sp}": rows_after_dedup={b["rows_after_dedup"]:,}  rows_dropped_as_dup={b["rows_dropped_as_dup"]:,}  dup_rate={b["dup_rate_pct"]}%')
    lines.append("    " + "  ".join(f"{k}:{v:,}" for k, v in b["label_counts"].items()))
lines += [f'  "leak_check": "{br["leak_check"]}"     (no source file appears in two splits)',
          f'  "remaining_nan": {br["remaining_nan"]}',
          f'  "dropped_columns": {br["dropped_columns"]}   (Tot size == AVG, Tot sum == AVG x Number)',
          "", "$ head -4 data_out/split_manifest.csv"] + R("head -4 data_out/split_manifest.csv")
shot("shot_build", "PowerShell  -  03_build_dataset.py output", lines, hl=('"leak_check"',))

# sweep + per-class (real)
sw = pd.read_csv("results/final_model/sweep_5class.csv")
pc = pd.read_csv("results/final_model/per_class_f1_rf5_n30_d10_f25.csv")
lines = ["$ python 11_build_5class.py",
         "classes: ['Benign', 'Flood', 'Mirai', 'Probe', 'Spoofing'] | train (1268922, 25) test (286197, 25)"]
for _, r in sw.iterrows():
    lines.append(f"{{'name': '{r['name']}', 'trees': {r.trees}, 'depth': {r.depth}, 'nodes': {r.nodes}, "
                 f"'macro_f1_hard': {r.macro_f1_hard}, 'acc_test_hard': {r.acc_test_hard}, 'acc_natural_hard': {r.acc_natural_hard}}}")
lines += ["exported firmware/model_rf5_n30_d10_f25.h  (2918.7 KB source)", "   class  f1_hardvote"]
lines += [f"{r['class']:>8}       {r.f1_hardvote:.4f}" for _, r in pc.iterrows()]
lines += ["wrote 2000 sample rows", "python hard-vote accuracy on sample: 0.8135"]
shot("shot_sweep", "PowerShell  -  11_build_5class.py output", lines, hl=("rf5_n30_d10_f25'",))

# emlearn header (real)
hdr = [l.rstrip() for l in open("firmware/esp32_ids_demo/model_rf5_n30_d10_f25.h", encoding="utf-8")]
first = [l for l in hdr if l.strip()][:20]
n_lines = len(hdr); size_kb = os.path.getsize("firmware/esp32_ids_demo/model_rf5_n30_d10_f25.h") / 1024
lines = ["$ head firmware/model_rf5_n30_d10_f25.h"] + [l.replace("    ", "  ") for l in first]
lines += ["  ...", f"# {n_lines:,} lines, {size_kb:,.0f} KB of C source: 30 trees x depth 10 = 26,376 nodes of pure if/else, no malloc, nothing in RAM"]
shot("shot_header", "model_rf5_n30_d10_f25.h  -  generated by emlearn", lines, hl=("model_rf5_n30_d10_f25_tree_0",))

# compile output (real, from arduino-cli)
lines = ["$ python scripts/07_measure_footprint.py", "compiling firmware/esp32_ids_demo ...",
         "Sketch uses 520204 bytes (39%) of program storage space. Maximum is 1310720 bytes.",
         "Global variables use 23156 bytes (7%) of dynamic memory, leaving 304524 bytes for local variables. Maximum is 327680 bytes.",
         "", "compiling the same sketch without the forest ...",
         "Sketch uses 280232 bytes (21%) of program storage space.", "Global variables use 23156 bytes (7%) of dynamic memory.", "",
         "model only: 239,972 bytes = 240 KB flash, 0 B static RAM  -> results/device/footprint_rf5_n30_d10_f25.json"]
shot("shot_compile", "PowerShell  -  07_measure_footprint.py (arduino-cli compile, ESP32 Dev Module)", lines, hl=("model only: 239,972",))

# parity (real, user's run 2026-11-17)
lines = ["$ python 08_parity_test.py --port COM15 --model rf5_n30_d10_f25 --samples firmware/sample_inputs_5class.csv",
         "Opening COM15 @ 115200 ...", "  2000/2000 rows  (33s)", "",
         "==== STAGE 2 PARITY RESULT ====", "rows sent              : 2000   (no reply / parse error: 0)",
         "board == laptop C      : 100.00 %  row-for-row", "board accuracy         : 0.8135", "laptop C accuracy      : 0.8135",
         "board == Python sklearn: 98.20 %", "inference time (us)    : mean 295.2   median 299   min 168   max 541", "",
         "per-class mean inference time (us):", "  Benign        344.4", "  Flood         227.4", "  Mirai         229.5",
         "  Probe         332.0", "  Spoofing      342.9", "", "STAGE 2 PASS   (details -> results/device/parity_rf5_n30_d10_f25.csv)"]
shot("shot_parity", "PowerShell  -  08_parity_test.py (ESP32 on COM15)", lines, hl=("100.00 %", "STAGE 2 PASS"))

# demo (real, user's run)
lines = ["$ python 10_demo.py --port COM15", "Connected to ESP32 on COM15", "===== NORMAL NETWORK TRAFFIC =====",
         "[  3] true: Benign   chip says: Benign      379 us  ok   normal",
         "[  4] true: Benign   chip says: Benign      395 us  ok   normal",
         "[  6] true: Benign   chip says: Probe       308 us  MISS  ATTACK DETECTED",
         "===== DDoS ATTACK STARTS =====",
         "[ 21] true: Flood    chip says: Flood       387 us  ok   ATTACK DETECTED",
         "[ 22] true: Flood    chip says: Flood       284 us  ok   ATTACK DETECTED",
         "===== MIRAI BOTNET ACTIVITY =====",
         "[ 56] true: Mirai    chip says: Mirai       398 us  ok   ATTACK DETECTED",
         "[ 57] true: Mirai    chip says: Mirai       268 us  ok   ATTACK DETECTED",
         "===== ATTACKER PROBING THE NETWORK =====",
         "[ 86] true: Probe    chip says: Probe       368 us  ok   ATTACK DETECTED",
         "[ 90] true: Probe    chip says: Benign      406 us  MISS  normal", "",
         "===== SUMMARY =====", "Flows classified          : 100", "Exact class correct       : 87.0%",
         "Attack flows flagged      : 96.0%", "Benign flows called attack: 20.0%", "On-chip inference time    : mean 342 us, max 473 us"]
shot("shot_demo", "PowerShell  -  10_demo.py live replay (chip decides, laptop only feeds flows)", lines, hl=("ATTACK DETECTED", "SUMMARY"))

# sketch snippet (real)
src = open("firmware/esp32_ids_demo/esp32_ids_demo.ino", encoding="utf-8").read().split("\n")
i = next(k for k, l in enumerate(src) if "static void handleLine" in l)
snip = [l for l in src[i:i + 26] if l.strip() != ""]
shot("shot_sketch", "esp32_ids_demo.ino  -  serial handler on the ESP32", ["// esp32_ids_demo/esp32_ids_demo.ino"] + snip,
     hl=("model_rf5_n30_d10_f25_predict",))

# 3. confusion matrix heatmap (real)
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
cm = pd.read_csv("results/final_model/confusion_rf5_n30_d10_f25.csv", index_col=0)
cmap = LinearSegmentedColormap.from_list("nc", ["#384168", "#8B93B8", "#F8F6E2"])
fig, ax = plt.subplots(figsize=(6.4, 5.6), dpi=200); fig.patch.set_alpha(0); ax.set_facecolor("none")
ax.imshow(cm.values, cmap=cmap, vmin=0, vmax=1)
for i in range(5):
    for j in range(5):
        v = cm.values[i, j]
        ax.text(j, i, f"{v*100:.0f}%", ha="center", va="center", fontsize=13, fontweight="bold",
                color="#1B1F2E" if v > 0.55 else "#F8F6E2")
ax.set_xticks(range(5)); ax.set_yticks(range(5))
ax.set_xticklabels(cm.columns, color="#F8F6E2", fontsize=12); ax.set_yticklabels(cm.index, color="#F8F6E2", fontsize=12)
ax.set_xlabel("Chip predicted", color="#F8F6E2", fontsize=13); ax.set_ylabel("True class", color="#F8F6E2", fontsize=13)
for s in ax.spines.values(): s.set_visible(False)
ax.tick_params(colors="#F8F6E2", length=0); plt.tight_layout()
fig.savefig(f"{S}/confusion.png", transparent=True); print("wrote confusion")
