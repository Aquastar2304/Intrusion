"""
STEP 6 - EXPORT TO C: turn the trained forest into C code and prove the C gives the same answers.

What it does:
  1. emlearn converts models/rf5_n30_d10_f25.joblib into plain C: every tree becomes
     nested if/else statements on a 25-float array, and a predict() function counts
     the votes. No libraries, no memory allocation, nothing stored in RAM.
     The header is written straight into the Arduino sketch folder.
  2. gcc compiles firmware/desktop_test/main.c, which includes that same header, and
     runs it on the 2,000 sample rows from step 5.
  3. The C predictions are compared with the Python hard-vote predictions. They must
     match on every row; this file is then the reference the ESP32 must match in step 8.

Inputs : models/rf5_n30_d10_f25.joblib, firmware/sample_inputs_5class.csv
Outputs: firmware/esp32_ids_demo/model_rf5_n30_d10_f25.h
         firmware/desktop_preds_rf5_n30_d10_f25.csv
         firmware/desktop_test/build/desktop_test.exe

Needs gcc. On this machine it is MSYS2's gcc at C:/msys64/ucrt64/bin; any gcc on PATH works.

Usage:
    python scripts/06_export_to_c.py
"""
import hashlib
import os
import shutil
import subprocess
import sys

import joblib
import numpy as np
import pandas as pd

from common import CLASSES5, FIRMWARE, MODEL_NAME, MODELS, SKETCH, hard_vote

GCC_CANDIDATES = ["gcc", r"C:\msys64\ucrt64\bin\gcc.exe", r"C:\msys64\mingw64\bin\gcc.exe"]


def find_gcc():
    for c in GCC_CANDIDATES:
        p = shutil.which(c) or (c if os.path.exists(c) else None)
        if p:
            return p
    sys.exit("gcc not found. Install MSYS2 (https://www.msys2.org) and run: pacman -S mingw-w64-ucrt-x86_64-gcc")


def md5(path):
    return hashlib.md5(open(path, "rb").read()).hexdigest()


def main():
    import emlearn

    # 1. convert
    header = SKETCH / f"model_{MODEL_NAME}.h"
    before = md5(header) if header.exists() else None
    forest = joblib.load(MODELS / f"{MODEL_NAME}.joblib")
    emlearn.convert(forest, method="inline", dtype="float").save(file=str(header), name=f"model_{MODEL_NAME}")
    after = md5(header)
    n_lines = sum(1 for _ in open(header))
    print(f"wrote {header}  ({os.path.getsize(header) / 1024:,.0f} KB, {n_lines:,} lines of C)")
    if before and before != after:
        print("  NOTE: the header changed. Re-upload the sketch, and update the SMOKE rows in "
              "esp32_ids_demo.ino from firmware/desktop_preds_*.csv (first row of each class).")
    elif before:
        print("  header is byte-identical to the one already in the sketch")

    # 2. compile and run the desktop C reference
    gcc = find_gcc()
    build = FIRMWARE / "desktop_test" / "build"
    os.makedirs(build, exist_ok=True)
    exe = build / "desktop_test.exe"
    env = dict(os.environ, PATH=os.path.dirname(gcc) + os.pathsep + os.environ.get("PATH", ""))
    subprocess.run([gcc, "-O2", str(FIRMWARE / "desktop_test" / "main.c"), "-o", str(exe), "-lm"],
                   check=True, env=env)
    samples = (FIRMWARE / "sample_inputs_5class.csv").resolve()
    preds = (FIRMWARE / f"desktop_preds_{MODEL_NAME}.csv").resolve()
    out = subprocess.run([str(exe.resolve()), str(samples), str(preds)], check=True, env=env,
                         capture_output=True, text=True)
    print(out.stdout.strip())

    # 3. compare with Python
    s = pd.read_csv(samples)
    d = pd.read_csv(preds)
    X = s.drop(columns=["label_idx", "label"]).to_numpy(np.float32)
    py = hard_vote(forest, X, len(CLASSES5))
    match = float((py == d.desktop_pred.to_numpy()).mean())
    print(f"C vs Python hard vote: {match:.2%} of {len(d):,} rows match")
    if match < 1.0:
        sys.exit("MISMATCH - the C model does not reproduce the Python model; do not flash it.")
    print("OK - the C code reproduces the Python model exactly. Upload firmware/esp32_ids_demo next.")


if __name__ == "__main__":
    main()
