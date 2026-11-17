"""
STEP 7 - MEASURE FOOTPRINT: how much flash and RAM the model really takes on the ESP32.

Method (measured, not estimated):
  1. Compile the real demo sketch, firmware/esp32_ids_demo, for "ESP32 Dev Module".
  2. Compile an identical copy in a temporary folder where the forest is replaced by a
     one-line stub, so everything else (serial, LED, smoke test, Arduino core) is the same.
  3. Model footprint = (1) minus (2).

On the project board this gave 520,204 - 280,232 = 239,972 bytes, about 240 KB of flash
(KB = 1,000 bytes), and 0 bytes of static RAM: the trees are compiled code, not data.

Needs the Arduino IDE (it ships arduino-cli) with the esp32 board package installed.
Nothing is uploaded to the board.

Outputs: results/device/footprint_rf5_n30_d10_f25.json

Usage:
    python scripts/07_measure_footprint.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from common import MODEL_NAME, RESULTS, SKETCH

FQBN = "esp32:esp32:esp32"     # Tools -> Board -> "ESP32 Dev Module"
CLI_CANDIDATES = [
    "arduino-cli",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe"),
    r"C:\Program Files\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe",
]


def find_cli():
    for c in CLI_CANDIDATES:
        p = shutil.which(c) or (c if os.path.exists(c) else None)
        if p:
            return p
    sys.exit("arduino-cli not found. Install the Arduino IDE 2.x, or arduino-cli, and the esp32 board package.")


def compile_sketch(cli, sketch_dir, build_dir):
    out = subprocess.run([cli, "compile", "--fqbn", FQBN, "--build-path", str(build_dir), str(sketch_dir)],
                         capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"compile failed for {sketch_dir}:\n{out.stdout[-2000:]}\n{out.stderr[-2000:]}")
    flash = int(re.search(r"Sketch uses (\d+) bytes", out.stdout).group(1))
    ram = int(re.search(r"Global variables use (\d+) bytes", out.stdout).group(1))
    part = int(re.search(r"Maximum is (\d+) bytes", out.stdout).group(1))
    return flash, ram, part


def main():
    cli = find_cli()
    tmp = Path(tempfile.mkdtemp(prefix="ids_footprint_"))
    try:
        print(f"compiling {SKETCH} ...", flush=True)
        flash, ram, part = compile_sketch(cli, SKETCH, tmp / "build_full")

        # identical sketch with the forest stubbed out
        stub_dir = tmp / "esp32_ids_stub"
        stub_dir.mkdir()
        src = (SKETCH / "esp32_ids_demo.ino").read_text(encoding="utf-8")
        include = f'#include "model_{MODEL_NAME}.h"'
        assert include in src, f"{include} not found in the sketch"
        stub = (f"static int32_t model_{MODEL_NAME}_predict(const float *f, int32_t n) "
                "{ (void)n; return (f[0] > 100.0f) ? 1 : 0; }   // forest removed")
        (stub_dir / "esp32_ids_stub.ino").write_text(src.replace(include, stub), encoding="utf-8")
        print("compiling the same sketch without the forest ...", flush=True)
        b_flash, b_ram, _ = compile_sketch(cli, stub_dir, tmp / "build_stub")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    result = {
        "model": MODEL_NAME, "board": "ESP32 Dev Module (ESP32-WROOM-32)", "fqbn": FQBN,
        "sketch_flash_bytes": flash, "stub_sketch_flash_bytes": b_flash,
        "model_only_flash_bytes": flash - b_flash,
        "sketch_static_ram_bytes": ram, "stub_sketch_static_ram_bytes": b_ram,
        "model_only_static_ram_bytes": ram - b_ram,
        "app_partition_bytes": part, "sketch_pct_of_partition": round(flash / part * 100, 1),
    }
    os.makedirs(RESULTS / "device", exist_ok=True)
    out = RESULTS / "device" / f"footprint_{MODEL_NAME}.json"
    json.dump(result, open(out, "w"), indent=2)
    print(json.dumps(result, indent=2))
    print(f"\nmodel only: {result['model_only_flash_bytes'] / 1000:,.0f} KB flash, "
          f"{result['model_only_static_ram_bytes']} B static RAM  -> {out}")


if __name__ == "__main__":
    main()
