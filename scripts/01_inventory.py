"""
STEP 1 - INVENTORY: count every file and row in the raw dataset.

In this CIC-IoT-2023 release the label is the FILENAME, not a column:
    Backdoor_Malware.pcap.csv          -> class "Backdoor_Malware"
    DDoS-ACK_Fragmentation7.pcap.csv   -> class "DDoS-ACK_Fragmentation"

Numbered siblings are chunks of the SAME capture session, so they must never be
scattered across train/test - that is exactly the leakage we are avoiding.

This script:
  1. maps every file to its class and its 7-category group
  2. counts files and rows per class
  3. flags single-file classes (they need row-wise splitting instead)
  4. writes data_out/inventory.csv (also used later for real-traffic accuracy weights)

Usage:
    python scripts/01_inventory.py                      # uses Dataset/CSV/CSV
    python scripts/01_inventory.py /path/to/csv_dir/
"""

import sys
import os
import glob
import re
import pandas as pd

from common import RAW_CSV, DATA

# ---- map fine-grained class -> the 7 coarse categories used in the paper ----
def categorise(cls: str) -> str:
    c = cls.lower()
    if c.startswith("benign"):
        return "Benign"
    if c.startswith("ddos"):
        return "DDoS"
    if c.startswith("dos"):
        return "DoS"
    if "mirai" in c:
        return "Mirai"
    if c.startswith("recon") or "scan" in c or "ping_sweep" in c or "port_scan" in c:
        return "Recon"
    if "spoofing" in c or "mitm" in c or "arp" in c or "dns_spoof" in c:
        return "Spoofing"
    if any(k in c for k in ("backdoor", "browserhijacking", "commandinjection",
                            "sqlinjection", "uploading", "xss", "malware")):
        return "Web"
    if "bruteforce" in c or "dictionary" in c:
        return "BruteForce"
    return "Other"


def class_from_filename(fname: str) -> str:
    base = os.path.basename(fname)
    base = base.replace(".pcap.csv", "").replace(".csv", "")
    # strip a trailing chunk number: DDoS-ACK_Fragmentation12 -> DDoS-ACK_Fragmentation
    return re.sub(r"\d+$", "", base)


def count_rows(path: str) -> int:
    """Fast line count minus header."""
    with open(path, "rb") as f:
        return max(sum(1 for _ in f) - 1, 0)


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else str(RAW_CSV)

    files = sorted(glob.glob(os.path.join(root, "**", "*.csv"), recursive=True))
    if not files:
        sys.exit(f"No CSVs under {root}")

    print(f"Scanning {len(files)} files (counting rows, takes a minute)...\n")

    rows = []
    for i, f in enumerate(files, 1):
        cls = class_from_filename(f)
        rows.append({
            "file": os.path.basename(f),
            "path": f,
            "class": cls,
            "category": categorise(cls),
            "n_rows": count_rows(f),
            "size_mb": round(os.path.getsize(f) / 1e6, 2),
        })
        if i % 50 == 0:
            print(f"  ...{i}/{len(files)}")

    inv = pd.DataFrame(rows)

    # ---------- per-class summary ----------
    print("\n" + "=" * 78)
    print("CLASS INVENTORY  (fine-grained)")
    print("=" * 78)
    per_class = (inv.groupby(["category", "class"])
                    .agg(n_files=("file", "count"),
                         n_rows=("n_rows", "sum"),
                         size_mb=("size_mb", "sum"))
                    .sort_values(["category", "n_rows"], ascending=[True, False]))
    print(per_class.to_string())

    # ---------- category summary ----------
    print("\n" + "=" * 78)
    print("CATEGORY SUMMARY  (the 7 groups you will classify)")
    print("=" * 78)
    per_cat = (inv.groupby("category")
                  .agg(n_classes=("class", "nunique"),
                       n_files=("file", "count"),
                       n_rows=("n_rows", "sum"))
                  .sort_values("n_rows", ascending=False))
    per_cat["pct_rows"] = (per_cat["n_rows"] / per_cat["n_rows"].sum() * 100).round(2)
    print(per_cat.to_string())
    imb = per_cat["n_rows"].max() / max(per_cat["n_rows"].min(), 1)
    print(f"\n  category imbalance ratio = {imb:,.0f} : 1   -> macro-F1, not accuracy")

    if "Other" in per_cat.index:
        print("\n  !! Some classes fell into 'Other' - the category mapping needs")
        print("     fixing. Classes affected:")
        print("     ", sorted(inv.loc[inv.category == "Other", "class"].unique()))

    # ---------- split feasibility ----------
    print("\n" + "=" * 78)
    print("SPLIT FEASIBILITY  (files per class)")
    print("=" * 78)
    counts = inv.groupby("class")["n_files"].count() if "n_files" in inv else inv["class"].value_counts()
    counts = inv["class"].value_counts()
    multi = counts[counts >= 3]
    two = counts[counts == 2]
    single = counts[counts == 1]

    print(f"classes with >=3 files (clean file-level split) : {len(multi)}")
    print(f"classes with  2 files (train/test only, no val) : {len(two)}")
    print(f"classes with  1 file  (needs row-wise split)    : {len(single)}")
    if len(single):
        print("\n  single-file classes:")
        for c in sorted(single.index):
            n = int(inv.loc[inv["class"] == c, "n_rows"].iloc[0])
            print(f"    {c:35s} {n:>10,} rows")
        print("\n  ^ For these we split by ROW ORDER (first 70% train, next 15% val,")
        print("    last 15% test). Row order approximates capture order, so this is")
        print("    a temporal split - honest, though weaker than a file-level split.")

    # ---------- save ----------
    os.makedirs(DATA, exist_ok=True)
    out = str(DATA / "inventory.csv")
    inv.to_csv(out, index=False)
    print(f"\nWrote {out}  ({len(inv)} files, {inv.n_rows.sum():,} total rows)")


if __name__ == "__main__":
    main()