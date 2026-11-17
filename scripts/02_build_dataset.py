"""
STEP 2 - BUILD DATASET: clean the 309 CSVs and make leak-free train/val/test splits.

Result: 37 features per row (39 raw columns minus 'Tot size' and 'Tot sum').

This version folds in the disk-audit findings:
  - drop 'Tot size' (byte-identical to AVG) and 'Tot sum'
  - convert Inf -> NaN, then impute DELIBERATELY (train-median per column),
    never a blanket zero; the median is learned on train and reused for val/test
  - deduplicate within each split and report how many rows were dropped
  - measure the real duplicate rate instead of quoting a guessed 8%
  - configurable scale via --rows (default 2,000,000; use 10000000 for the big run)

Leakage control:
    >=3 files per class -> whole files assigned to one split each
      2 files per class -> file A train, file B row-split val/test
      1 file  per class -> contiguous row-order split (temporal proxy)

Requires: pip install pyarrow xgboost   (xgboost for the later training step)

Outputs (./data_out/): train.parquet  val.parquet  test.parquet
                       split_manifest.csv  build_report.txt

Usage:
    python scripts/02_build_dataset.py                       # Dataset/CSV/CSV -> data_out/
    python scripts/02_build_dataset.py /path/to/csv/ --rows 10000000 --out data_10m
"""

import sys
import os
import re
import glob
import json
import argparse
import numpy as np
import pandas as pd

try:
    import pyarrow  # noqa: F401
except ImportError:
    sys.exit("pyarrow is required. Run:  pip install pyarrow")

from common import RAW_CSV

# ------------------------- configuration -------------------------
TARGET_TOTAL_ROWS = 2_000_000        # start small; --rows 10000000 for the big run
TRAIN, VAL, TEST = 0.70, 0.15, 0.15
SEED = 42
FLOAT_DTYPE = "float32"
DROP_COLS = ["Tot size", "Tot sum"]  # 'Tot size' == AVG; 'Tot sum' redundant
# ------------------------------------------------------------------

rng = np.random.default_rng(SEED)


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
    if c.startswith("recon") or "scan" in c or "sweep" in c:
        return "Recon"
    if "spoofing" in c or "mitm" in c:
        return "Spoofing"
    if "bruteforce" in c or "dictionary" in c:
        return "BruteForce"
    return "Web"


def class_from_filename(fname: str) -> str:
    base = os.path.basename(fname).replace(".pcap.csv", "").replace(".csv", "")
    return re.sub(r"\d+$", "", base).rstrip("-_")   # also fixes 'DDoS-HTTP_Flood-'


def count_rows(path: str) -> int:
    with open(path, "rb") as f:
        return max(sum(1 for _ in f) - 1, 0)


# ---------------------------------------------------------------- planning
def plan_splits(inv: pd.DataFrame) -> pd.DataFrame:
    plan = []
    for cls, grp in inv.groupby("class"):
        grp = grp.sort_values("file").reset_index(drop=True)
        n = len(grp)
        if n >= 3:
            idx = rng.permutation(n)
            n_test = max(1, int(round(n * TEST)))
            n_val = max(1, int(round(n * VAL)))
            if n_test + n_val >= n:
                n_test, n_val = 1, 1
            test_i, val_i = set(idx[:n_test]), set(idx[n_test:n_test + n_val])
            for i, row in grp.iterrows():
                split = "test" if i in test_i else "val" if i in val_i else "train"
                plan.append({**row, "split": split, "row_lo": 0.0, "row_hi": 1.0})
        elif n == 2:
            r0, r1 = grp.iloc[0], grp.iloc[1]
            plan.append({**r0, "split": "train", "row_lo": 0.0, "row_hi": 1.0})
            plan.append({**r1, "split": "val", "row_lo": 0.0, "row_hi": 0.5})
            plan.append({**r1, "split": "test", "row_lo": 0.5, "row_hi": 1.0})
        else:
            r = grp.iloc[0]
            plan.append({**r, "split": "train", "row_lo": 0.0, "row_hi": TRAIN})
            plan.append({**r, "split": "val", "row_lo": TRAIN, "row_hi": TRAIN + VAL})
            plan.append({**r, "split": "test", "row_lo": TRAIN + VAL, "row_hi": 1.0})
    return pd.DataFrame(plan)


def solve_cap(avail_per_cat: pd.Series, target: int) -> int:
    lo, hi = 1, int(avail_per_cat.max())
    while lo < hi:
        mid = (lo + hi) // 2
        if int(np.minimum(avail_per_cat, mid).sum()) >= target:
            hi = mid
        else:
            lo = mid + 1
    return lo


def assign_quotas(plan: pd.DataFrame, target: int):
    plan = plan.copy()
    plan["avail"] = ((plan.row_hi - plan.row_lo) * plan.n_rows).astype(int)
    avail_cat = plan.groupby("category")["avail"].sum()
    target = min(target, int(avail_cat.sum()))
    cap = solve_cap(avail_cat, target)
    kept = np.minimum(avail_cat, cap)

    print("\n" + "=" * 74)
    print(f"SCALE  target={target:,}  ->  per-category cap = {cap:,}")
    print("=" * 74)
    rep = pd.DataFrame({"available": avail_cat, "kept": kept.astype(int)})
    rep["pct"] = (rep.kept / rep.kept.sum() * 100).round(2)
    rep["capped"] = np.where(avail_cat > cap, "yes", "no (exhausted)")
    print(rep.sort_values("kept", ascending=False).to_string())
    imb = rep.kept.max() / max(rep.kept.min(), 1)
    print(f"\n  total kept {int(rep.kept.sum()):,}   imbalance {imb:,.0f} : 1")

    plan["quota"] = 0
    frac = {"train": TRAIN, "val": VAL, "test": TEST}
    for (cat, split), grp in plan.groupby(["category", "split"]):
        want = int(kept[cat] * frac[split])
        avail = int(grp["avail"].sum())
        if avail == 0:
            continue
        take = min(want, avail)
        alloc = ((grp["avail"] / avail) * take).round().astype(int)
        drift = take - int(alloc.sum())
        if drift and len(alloc):
            alloc.iloc[int(alloc.values.argmax())] += drift
        plan.loc[grp.index, "quota"] = alloc.values
    return plan


# ------------------------------------------------------------- materialise
def load_slice(row):
    if row.quota <= 0:
        return None
    df = pd.read_csv(row.path, low_memory=False)
    lo, hi = int(len(df) * row.row_lo), int(len(df) * row.row_hi)
    df = df.iloc[lo:hi]
    if len(df) > row.quota:
        step = len(df) / row.quota
        df = df.iloc[(np.arange(row.quota) * step).astype(int)]
    df = df.copy()
    df.drop(columns=[c for c in DROP_COLS if c in df.columns], inplace=True)
    # Inf -> NaN now; imputation happens later with train medians
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    for c in df.select_dtypes(include=[np.floating]).columns:
        df[c] = df[c].astype(FLOAT_DTYPE)
    df["label"] = row.category
    df["fine_label"] = row["class"]
    df["src_file"] = row.file
    return df


def build_raw_split(plan, split):
    sub = plan[(plan.split == split) & (plan.quota > 0)]
    print(f"\nBuilding {split}: {len(sub)} slices, target {sub.quota.sum():,} rows")
    parts = []
    for i, (_, row) in enumerate(sub.iterrows(), 1):
        d = load_slice(row)
        if d is not None and len(d):
            parts.append(d)
        if i % 40 == 0:
            print(f"   ...{i}/{len(sub)}")
    return pd.concat(parts, ignore_index=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=str(RAW_CSV))
    ap.add_argument("--rows", type=int, default=TARGET_TOTAL_ROWS)
    ap.add_argument("--out", default="data_out")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    files = sorted(glob.glob(os.path.join(args.root, "**", "*.csv"), recursive=True))
    files = [f for f in files if "inventory" not in os.path.basename(f).lower()]
    if not files:
        sys.exit(f"No CSVs under {args.root}")

    print(f"Indexing {len(files)} files...")
    inv = pd.DataFrame([{
        "file": os.path.basename(f), "path": f,
        "class": class_from_filename(f),
        "category": categorise(class_from_filename(f)),
        "n_rows": count_rows(f),
    } for f in files])

    plan = plan_splits(inv)
    plan = assign_quotas(plan, args.rows)
    plan.to_csv(os.path.join(args.out, "split_manifest.csv"), index=False)

    report = {}
    medians = None
    feature_cols = None

    for split in ("train", "val", "test"):
        df = build_raw_split(plan, split)

        # --- dedup within split, count drops ---
        before = len(df)
        feat = [c for c in df.columns if c not in ("label", "fine_label", "src_file")]
        df = df.drop_duplicates(subset=feat).reset_index(drop=True)
        dropped = before - len(df)
        dup_rate = round(dropped / before * 100, 2) if before else 0.0

        # --- deliberate imputation: learn medians on TRAIN, reuse elsewhere ---
        if split == "train":
            feature_cols = feat
            medians = df[feat].median(numeric_only=True)
        df[feature_cols] = df[feature_cols].fillna(medians)

        # shuffle rows (safe now: splitting already done at file/row-range level)
        df = df.sample(frac=1, random_state=SEED).reset_index(drop=True)

        path = os.path.join(args.out, f"{split}.parquet")
        df.to_parquet(path, index=False)

        report[split] = {
            "rows_after_dedup": int(len(df)),
            "rows_dropped_as_dup": int(dropped),
            "dup_rate_pct": dup_rate,
            "label_counts": df["label"].value_counts().to_dict(),
        }
        print(f"   wrote {path}  rows={len(df):,}  dup dropped={dropped:,} ({dup_rate}%)")

    # ------------------------------------------------------- sanity checks
    print("\n" + "=" * 74)
    print("SANITY CHECKS")
    print("=" * 74)
    tr = pd.read_parquet(os.path.join(args.out, "train.parquet"),
                         columns=["src_file", "fine_label", "label"])
    te = pd.read_parquet(os.path.join(args.out, "test.parquet"),
                         columns=["src_file", "fine_label", "label"])
    multi = inv["class"].value_counts()
    multi = set(multi[multi >= 3].index)
    overlap = (set(tr.loc[tr.fine_label.isin(multi), "src_file"]) &
               set(te.loc[te.fine_label.isin(multi), "src_file"]))
    leak = "OK" if not overlap else f"LEAK -> {sorted(overlap)[:5]}"
    print(f"multi-file classes sharing a file across train/test: {len(overlap)}  {leak}")
    print(f"categories present  train={tr.label.nunique()}  test={te.label.nunique()}")

    full_tr = pd.read_parquet(os.path.join(args.out, "train.parquet"))
    num = full_tr.select_dtypes(include=[np.number])
    dead = [c for c in num.columns if num[c].nunique() <= 1]
    n_nan = int(full_tr.isna().sum().sum())
    n_inf = int(np.isinf(num.to_numpy()).sum())
    print(f"feature columns kept: {num.shape[1]}  (dropped {DROP_COLS})")
    print(f"zero-variance columns: {dead if dead else 'none'}")
    print(f"remaining NaN: {n_nan}   remaining Inf: {n_inf}   (both should be 0)")
    print("\ntrain label counts:")
    print(full_tr['label'].value_counts().to_string())

    report["leak_check"] = leak
    report["dead_columns"] = dead
    report["remaining_nan"] = n_nan
    report["dropped_columns"] = DROP_COLS
    with open(os.path.join(args.out, "build_report.txt"), "w") as f:
        f.write(json.dumps(report, indent=2))
    print(f"\nWrote {os.path.join(args.out, 'build_report.txt')}")


if __name__ == "__main__":
    main()