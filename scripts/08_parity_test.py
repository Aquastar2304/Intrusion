"""
STEP 8 - PARITY TEST: prove the ESP32 gives exactly the same answers as the laptop.

Needs: firmware/esp32_ids_demo uploaded to the board, Arduino Serial Monitor closed.

Streams every row of firmware/sample_inputs_5class.csv to the ESP32 over serial,
collects the board's prediction + inference time, and checks:

  1. board prediction == laptop C prediction, ROW FOR ROW   (must be 100 %)
  2. board accuracy   == laptop C accuracy                   (0.8135)
  3. (informational) board prediction vs the Python sklearn model

Writes results/device/parity_rf5_n30_d10_f25.csv with one row per sample.

Usage:
    python scripts/08_parity_test.py                 # auto-detect the port
    python scripts/08_parity_test.py --port COM15
    python scripts/08_parity_test.py --limit 200     # quick run
"""
import argparse, os, re, sys, time
import pandas as pd
import serial
import serial.tools.list_ports

from common import MODEL_NAME, FIRMWARE, MODELS, RESULTS

MODEL     = MODEL_NAME                                   # overridden by --model
SAMPLES   = str(FIRMWARE / "sample_inputs_5class.csv")   # overridden by --samples
OUT_DIR   = str(RESULTS / "device")
REPLY_RE  = re.compile(r"^(-?\d+),(\d+)(?:,[01])?$")   # demo sketch adds ",<alert>"


def find_port():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        d = (p.description or "").lower()
        if any(k in d for k in ("cp210", "ch340", "ch910", "usb serial", "silicon labs", "uart")):
            return p.device
    if len(ports) == 1:
        return ports[0].device
    sys.exit("Could not auto-detect the board. Ports seen: "
             + (", ".join(f"{p.device} ({p.description})" for p in ports) or "none")
             + "\nRe-run with --port COMx")


def wait_for(ser, token, timeout):
    """Read lines until one equals token. Returns the lines seen before it."""
    seen, t_end = [], time.time() + timeout
    while time.time() < t_end:
        line = ser.readline().decode("utf-8", "replace").strip()
        if not line:
            continue
        if line == token:
            return seen
        seen.append(line)
    sys.exit(f"Timed out waiting for '{token}'. Last lines from board:\n  " + "\n  ".join(seen[-10:]))


def main():
    global MODEL
    ap = argparse.ArgumentParser()
    ap.add_argument("--port")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--limit", type=int, default=0, help="only send the first N rows")
    ap.add_argument("--model", default=MODEL, help="model name flashed on the board")
    ap.add_argument("--samples", default=SAMPLES, help="sample rows csv to replay")
    args = ap.parse_args()
    MODEL = args.model
    REFERENCE = str(FIRMWARE / f"desktop_preds_{MODEL}.csv")

    df  = pd.read_csv(args.samples)
    ref = pd.read_csv(REFERENCE)
    feats = [c for c in df.columns if c not in ("label_idx", "label")]
    assert len(feats) == 25, f"expected 25 features, got {len(feats)}"
    assert len(df) == len(ref), "sample file and reference file differ in length"
    if args.limit:
        df, ref = df.iloc[:args.limit], ref.iloc[:args.limit]

    port = args.port or find_port()
    print(f"Opening {port} @ {args.baud} ...")
    ser = serial.Serial(port, args.baud, timeout=2)
    time.sleep(2.5)                     # opening the port resets the ESP32
    ser.reset_input_buffer()

    # The board prints the smoke test then READY on boot; if we missed it, PING.
    ser.write(b"PING\n")
    boot_lines = wait_for(ser, "READY", timeout=15)
    smoke = [l for l in boot_lines if l.startswith("RESULT:")]
    if smoke:
        print("Board boot:", smoke[-1])

    preds, micros, errors = [], [], 0
    t_start = time.time()
    for i, (_, row) in enumerate(df.iterrows()):
        line = ",".join(repr(float(row[f])) for f in feats) + "\n"
        ser.write(line.encode())
        reply = None
        for _ in range(5):              # skip any stray non-reply lines
            raw = ser.readline().decode("utf-8", "replace").strip()
            m = REPLY_RE.match(raw)
            if m:
                reply = (int(m.group(1)), int(m.group(2)))
                break
            if raw.startswith("ERR"):
                print(f"  row {i}: board said {raw}")
                break
        if reply is None:
            errors += 1
            preds.append(-1); micros.append(-1)
        else:
            preds.append(reply[0]); micros.append(reply[1])
        if (i + 1) % 200 == 0:
            print(f"  {i+1}/{len(df)} rows  ({time.time()-t_start:.0f}s)")
    ser.close()

    res = pd.DataFrame({
        "row":          ref["row"].values,
        "label_idx":    df["label_idx"].values,
        "label":        df["label"].values,
        "desktop_pred": ref["desktop_pred"].values,
        "board_pred":   preds,
        "board_us":     micros,
    })

    # ---- informational: Python sklearn model on the same rows ----
    try:
        import joblib
        mp = str(MODELS / f"{MODEL}.joblib")
        clf = joblib.load(mp)
        res["python_pred"] = clf.predict(df[feats].values)
    except Exception as e:
        print(f"(skipping Python-model comparison: {e})")

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"parity_{MODEL}.csv")
    res.to_csv(out, index=False)

    ok = res[res.board_pred >= 0]
    n            = len(res)
    rowmatch     = (ok.board_pred == ok.desktop_pred).mean()
    board_acc    = (ok.board_pred == ok.label_idx).mean()
    desktop_acc  = (res.desktop_pred == res.label_idx).mean()
    us           = ok.board_us

    print("\n==== STAGE 2 PARITY RESULT ====")
    print(f"rows sent              : {n}   (no reply / parse error: {errors})")
    print(f"board == laptop C      : {rowmatch*100:.2f} %  row-for-row")
    print(f"board accuracy         : {board_acc:.4f}")
    print(f"laptop C accuracy      : {desktop_acc:.4f}")
    if "python_pred" in res:
        print(f"board == Python sklearn: {(ok.board_pred == ok.python_pred).mean()*100:.2f} %")
    print(f"inference time (us)    : mean {us.mean():.1f}   median {us.median():.0f}   "
          f"min {us.min()}   max {us.max()}")
    print("\nper-class mean inference time (us):")
    for c, g in ok.groupby("label"):
        print(f"  {c:10s} {g.board_us.mean():8.1f}")

    mism = ok[ok.board_pred != ok.desktop_pred]
    if len(mism):
        print(f"\nFIRST MISMATCHES ({len(mism)} total):")
        print(mism.head(10).to_string(index=False))
    verdict = "STAGE 2 PASS" if (errors == 0 and rowmatch == 1.0) else "STAGE 2 FAIL"
    print(f"\n{verdict}   (details -> {out})")


if __name__ == "__main__":
    main()
