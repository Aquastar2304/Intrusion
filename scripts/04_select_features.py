"""
STEP 4 - SELECT FEATURES: rank the 37 features and keep the smallest set that loses no accuracy.

How:
  1. Train a 150-tree random forest on all 37 features (8 categories, balanced weights)
     and rank the features by its importance scores.
  2. Retrain a fixed 100-tree, depth-16 forest on the top 37, 25, 20, 15, 10, 8 and 5
     features and record macro-F1 on the test set for each.
  3. Keep the smallest feature count whose macro-F1 is within 0.02 of the best.
     On the project data this picked 25 features.

Fewer features means a smaller model and less work for the chip per flow.
The order of the saved list is the order the C code and the serial protocol expect.

Inputs : data_out/train.parquet, data_out/test.parquet
Outputs: results/feature_selection/feature_ranking.csv
         results/feature_selection/feature_sweep.csv
         models/selected_features.json            (the 25 chosen features, in order)

Usage:
    python scripts/04_select_features.py
    python scripts/04_select_features.py --sample 300000            # faster
    python scripts/04_select_features.py --out-dir tmp --out-features tmp/feats.json   # dry check
"""
import argparse
import json
import os
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_class_weight

from common import DATA, META, RESULTS, FEATURES_FILE

FEATURE_STEPS = [37, 25, 20, 15, 10, 8, 5]
TOLERANCE = 0.02


def load(split, le=None):
    df = pd.read_parquet(DATA / f"{split}.parquet")
    feats = [c for c in df.columns if c not in META]
    y_raw = df["label"].astype(str).to_numpy()
    le = le or LabelEncoder().fit(y_raw)
    return df[feats].astype("float32").to_numpy(), le.transform(y_raw), feats, le


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0, help="subsample training rows")
    ap.add_argument("--out-dir", default=str(RESULTS / "feature_selection"))
    ap.add_argument("--out-features", default=str(FEATURES_FILE))
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)

    Xtr, ytr, feats, le = load("train")
    Xte, yte, _, _ = load("test", le)
    if a.sample and a.sample < len(Xtr):
        idx = np.random.RandomState(42).choice(len(Xtr), a.sample, replace=False)
        Xtr, ytr = Xtr[idx], ytr[idx]
    cw = dict(enumerate(compute_class_weight("balanced", classes=np.unique(ytr), y=ytr)))
    print(f"train {Xtr.shape}  test {Xte.shape}  {len(feats)} features")

    # 1. rank
    ranker = RandomForestClassifier(n_estimators=150, n_jobs=-1, random_state=42, class_weight=cw).fit(Xtr, ytr)
    order = np.argsort(ranker.feature_importances_)[::-1]
    ranked = [feats[i] for i in order]
    rank_df = pd.DataFrame({"rank": range(1, len(ranked) + 1), "feature": ranked,
                            "importance": np.round(ranker.feature_importances_[order], 5)})
    rank_df.to_csv(os.path.join(a.out_dir, "feature_ranking.csv"), index=False)
    print("\nTop 15 features:\n" + rank_df.head(15).to_string(index=False))

    # 2. sweep feature counts
    rows = []
    for k in FEATURE_STEPS:
        cols = [feats.index(c) for c in ranked[:min(k, len(feats))]]
        t = time.time()
        clf = RandomForestClassifier(n_estimators=100, max_depth=16, n_jobs=-1, random_state=42,
                                     class_weight=cw).fit(Xtr[:, cols], ytr)
        m = round(f1_score(yte, clf.predict(Xte[:, cols]), average="macro"), 4)
        nodes = int(sum(e.tree_.node_count for e in clf.estimators_))
        rows.append({"n_features": k, "macro_f1": m, "nodes": nodes, "fit_sec": round(time.time() - t, 1)})
        print(f"  {k:2d} features -> macro-F1 {m}   nodes {nodes:,}")
    sweep = pd.DataFrame(rows)
    sweep.to_csv(os.path.join(a.out_dir, "feature_sweep.csv"), index=False)

    # 3. choose
    best = sweep.macro_f1.max()
    k = int(sweep[sweep.macro_f1 >= best - TOLERANCE].sort_values("n_features").iloc[0].n_features)
    chosen = ranked[:k]
    os.makedirs(os.path.dirname(a.out_features) or ".", exist_ok=True)
    json.dump(chosen, open(a.out_features, "w"), indent=2)
    print(f"\nchosen: {k} features (within {TOLERANCE} macro-F1 of the best, {best}) -> {a.out_features}")


if __name__ == "__main__":
    main()
