"""
STEP 9 - LIVE DEMO: stream held-out CIC-IoT-2023 flows to the ESP32 and show what the CHIP decides.

The laptop only feeds flows (it plays the role of a network tap).
The ESP32 runs the 5-class forest and drives its own LED:
LED on = the current flow was classified as an attack.

Story (phases), each a random sample of TEST-SET flows the model never trained on:
    Normal network  -> Benign
    DDoS hits       -> Flood
    Back to normal  -> Benign
    Botnet          -> Mirai
    Back to normal  -> Benign
    Probing         -> Probe (Recon + Web + BruteForce)

Usage:
    python scripts/09_live_demo.py --port COM15            # terminal feed
    python scripts/09_live_demo.py --port COM15 --led      # also show the LED state
    python scripts/09_live_demo.py --dry-run               # rehearse without the board
    python scripts/09_live_demo.py --delay 0.5 --seed 7    # slower scroll, different random flows
"""
import argparse, json, os, sys, time
from collections import deque
import numpy as np
import pandas as pd

from common import MODELS, DATA, RESULTS, selected_features

os.system("")  # turns on ANSI colours in the Windows console
G, R, Y, C, B, X = "\033[92m", "\033[91m", "\033[93m", "\033[96m", "\033[1m", "\033[0m"

CLASSES = ["Benign", "Flood", "Mirai", "Probe", "Spoofing"]
MERGE = {"DDoS": "Flood", "DoS": "Flood", "Recon": "Probe", "Web": "Probe", "BruteForce": "Probe"}
MODEL = "rf5_n30_d10_f25"
PHASES = [  # (title, true class, number of flows)
    ("NORMAL NETWORK TRAFFIC", "Benign", 20),
    ("DDoS ATTACK STARTS", "Flood", 20),
    ("ATTACK STOPS - NORMAL TRAFFIC", "Benign", 15),
    ("MIRAI BOTNET ACTIVITY", "Mirai", 15),
    ("NORMAL TRAFFIC", "Benign", 15),
    ("ATTACKER PROBING THE NETWORK (SCANS, WEB ATTACKS, PASSWORD GUESSING)", "Probe", 15),
]
W, K = 1, 1  # alert window, must match ALERT_W / ALERT_K in esp32_ids_demo.ino


def build_playlist(seed):
    feats = selected_features()
    df = pd.read_parquet(DATA / "test.parquet", columns=feats + ["label"])
    lab = df["label"].astype(str).map(lambda c: MERGE.get(c, c)).to_numpy()
    rng = np.random.default_rng(seed)
    out = []
    for title, cls, n in PHASES:
        idx = rng.choice(np.flatnonzero(lab == cls), n, replace=False)
        for i in idx:
            out.append((title, cls, df[feats].iloc[i].to_numpy(np.float32)))
    return feats, out


class Board:
    def __init__(self, port, baud):
        import serial, serial.tools.list_ports
        if not port:
            ps = list(serial.tools.list_ports.comports())
            hit = [p.device for p in ps if any(k in (p.description or "").lower()
                   for k in ("cp210", "ch340", "ch910", "usb serial", "silicon labs", "uart"))]
            port = hit[0] if hit else (ps[0].device if len(ps) == 1 else None)
            if not port:
                sys.exit("Board not found. Plug it in, close the Arduino Serial Monitor, or pass --port COMx")
        self.ser = serial.Serial(port, baud, timeout=3)
        time.sleep(2.5)                       # board resets when the port opens
        self.ser.reset_input_buffer()
        self.cmd("PING")
        print(f"Connected to ESP32 on {port}")

    def cmd(self, c):
        self.ser.write((c + "\n").encode())
        t = time.time() + 5
        while time.time() < t:
            if self.ser.readline().decode(errors="replace").strip() == "READY":
                return
        sys.exit(f"Board did not answer {c}. Is esp32_ids_demo uploaded and the Serial Monitor closed?")

    def classify(self, x):
        self.ser.write((",".join(repr(float(v)) for v in x) + "\n").encode())
        line = self.ser.readline().decode(errors="replace").strip()
        parts = line.split(",")
        if len(parts) == 3:
            return int(parts[0]), int(parts[1]), parts[2] == "1"
        if len(parts) == 2:                   # old firmware without LED logic
            return int(parts[0]), int(parts[1]), None
        sys.exit(f"Unexpected reply from board: {line!r}")


class DryRun:
    """Same forest, same hard voting, same 3-of-5 rule, run on the laptop."""
    def __init__(self):
        import joblib
        self.clf = joblib.load(MODELS / f"{MODEL}.joblib")
        self.win = deque(maxlen=W)
        print(f"{Y}DRY RUN: the laptop is classifying, not the ESP32. Use this for rehearsal only.{X}")

    def classify(self, x):
        v = np.zeros(len(CLASSES), int)
        for t in self.clf.estimators_:
            v[int(t.predict(x[None])[0])] += 1
        p = int(v.argmax()); self.win.append(p != 0)
        return p, None, sum(self.win) >= K


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port"); ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--delay", type=float, default=0.25, help="seconds between flows")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--led", action="store_true", help="show the LED alert state (needs esp32_ids_demo)")
    a = ap.parse_args()

    feats, playlist = build_playlist(a.seed)
    dev = DryRun() if a.dry_run else Board(a.port, a.baud)
    if a.led and not a.dry_run:
        dev.cmd("RESET")
    laptop_win = deque(maxlen=W)
    log, phase = [], None
    print(f"\n{B}ESP32 IoT Intrusion Detection - live classification of held-out flows{X}")
    print(f"Model: {MODEL}  (5 classes, 30 trees, depth 10, 25 features, ~240 KB on chip)\n")
    input("Press Enter to start the traffic... ")

    for n, (title, true, x) in enumerate(playlist, 1):
        if title != phase:
            phase = title
            print(f"\n{C}{B}===== {title} ====={X}"); time.sleep(1.0)
        pred, us, alert = dev.classify(x)
        laptop_win.append(pred != 0)
        if alert is None:
            alert = sum(laptop_win) >= K
        name = CLASSES[pred]
        col = G if pred == 0 else R
        ok = "ok " if name == true else "MISS"
        if a.led:
            led = f"{R}{B}LED ON  *** INTRUSION ALERT ***{X}" if alert else f"{G}LED off{X}"
        else:
            led = f"{R}{B}ATTACK DETECTED{X}" if pred != 0 else f"{G}normal{X}"
        lat = f"{us:4d} us" if us is not None else "   -   "
        print(f"[{n:3d}] true: {true:<7}  chip says: {col}{name:<10}{X} {lat}  {ok}  {led}")
        log.append({"n": n, "phase": title, "true": true, "pred": name, "micros": us, "alert": int(alert)})
        time.sleep(a.delay)

    L = pd.DataFrame(log)
    acc = (L.true == L.pred).mean()
    attack_flows = L[L.true != "Benign"]; benign_flows = L[L.true == "Benign"]
    det = (attack_flows.pred != "Benign").mean()
    fa = (benign_flows.alert == 1).mean()
    print(f"\n{B}===== SUMMARY ====={X}")
    print(f"Flows classified          : {len(L)}")
    print(f"Exact class correct       : {acc:.1%}")
    print(f"Attack flows flagged      : {det:.1%}")
    if a.led:
        print(f"Benign flows with LED on  : {fa:.1%}")
    else:
        print(f"Benign flows called attack: {(benign_flows.pred != 'Benign').mean():.1%}")
    if L.micros.notna().any():
        print(f"On-chip inference time    : mean {L.micros.mean():.0f} us, max {L.micros.max():.0f} us")
    os.makedirs(RESULTS / "device", exist_ok=True)
    out = str(RESULTS / "device" / f"demo_log_{'dryrun' if a.dry_run else 'board'}_seed{a.seed}.csv")
    L.to_csv(out, index=False); print(f"Log saved to {out}")


if __name__ == "__main__":
    main()
