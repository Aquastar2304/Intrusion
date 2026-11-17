"""
STEP 5 - TRAIN THE FINAL MODEL: the 5-class forest that runs on the ESP32.

Classes (merged because the flow features cannot tell them apart):
    DDoS + DoS              -> Flood
    Recon + Web + BruteForce -> Probe
    Benign, Mirai, Spoofing  unchanged
  -> Benign, Flood, Mirai, Probe, Spoofing

What it does:
  * trains two sizes on the 25 selected features with balanced class weights:
      rf5_n20_d6_f25   (20 trees, depth 6)  - the small comparison point
      rf5_n30_d10_f25  (30 trees, depth 10) - the deployed model
  * scores both with HARD voting (one vote per tree), exactly as the C code votes
  * reports test accuracy, real-traffic accuracy (rows weighted by how common each
    original category is in the full dataset), macro-F1 and train accuracy
  * saves per-class F1 and the confusion matrix of the deployed model
  * writes firmware/sample_inputs_5class.csv: 2,000 test rows, 400 per class,
    which step 6 runs through the C code and step 8 sends to the board

Optional --compare-groupings also trains the same-size forest on 8 and 7 classes,
to show what the class merging buys (results/final_model/class_grouping.csv).

Inputs : data_out/{train,test}.parquet, data_out/inventory.csv, models/selected_features.json
Outputs: models/rf5_n30_d10_f25.joblib, models/rf5_n20_d6_f25.joblib
         results/final_model/{sweep_5class.csv, chosen.json,
                              per_class_f1_rf5_n30_d10_f25.csv, confusion_rf5_n30_d10_f25.csv}
         firmware/sample_inputs_5class.csv

Usage:
    python scripts/05_train_final_model.py
    python scripts/05_train_final_model.py --compare-groupings
"""
import argparse
import json
import os
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.preprocessing import LabelEncoder
from sklearn.utils.class_weight import compute_class_weight

from common import (DATA, FIRMWARE, MERGE5, MODEL_NAME, MODELS, RESULTS,
                    hard_vote, natural_weights, selected_features)

SWEEP = [(20, 6), (30, 10)]
OUT = RESULTS / "final_model"
GROUPINGS = {
    "8 classes": {},
    "7 classes (Flood)": {"DDoS": "Flood", "DoS": "Flood"},
    "5 classes (Flood + Probe)": MERGE5,
}


def load(split, feats, merge):
    df = pd.read_parquet(DATA / f"{split}.parquet", columns=feats + ["label"])
    cat = df["label"].astype(str).to_numpy()
    y = np.array([merge.get(c, c) for c in cat])
    return df[feats].astype("float32").to_numpy(), y, cat


def compare_groupings(feats):
    rows = []
    for name, merge in GROUPINGS.items():
        Xtr, ytr_raw, _ = load("train", feats, merge)
        Xte, yte_raw, cat_te = load("test", feats, merge)
        le = LabelEncoder().fit(ytr_raw)
        ytr, yte = le.transform(ytr_raw), le.transform(yte_raw)
        K = len(le.classes_)
        cw = dict(zip(range(K), compute_class_weight("balanced", classes=np.arange(K), y=ytr)))
        clf = RandomForestClassifier(n_estimators=30, max_depth=10, n_jobs=-1, random_state=42,
                                     class_weight=cw).fit(Xtr, ytr)
        p = hard_vote(clf, Xte, K)
        rows.append({"grouping": name, "n_classes": K,
                     "acc_test": round(accuracy_score(yte, p), 4),
                     "acc_natural": round(accuracy_score(yte, p, sample_weight=natural_weights(cat_te)), 4),
                     "macro_f1": round(f1_score(yte, p, average="macro"), 4)})
        print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(OUT / "class_grouping.csv", index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--compare-groupings", action="store_true")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    feats = selected_features()

    Xtr, ytr_raw, _ = load("train", feats, MERGE5)
    Xte, yte_raw, cat_te = load("test", feats, MERGE5)
    le = LabelEncoder().fit(ytr_raw)
    ytr, yte = le.transform(ytr_raw), le.transform(yte_raw)
    classes = list(map(str, le.classes_))
    K = len(classes)
    print(f"classes {classes}  train {Xtr.shape}  test {Xte.shape}")

    w_nat = natural_weights(cat_te)
    cw = dict(zip(range(K), compute_class_weight("balanced", classes=np.arange(K), y=ytr)))

    rows = []
    for n, d in SWEEP:
        t0 = time.time()
        clf = RandomForestClassifier(n_estimators=n, max_depth=d, n_jobs=-1, random_state=42,
                                     class_weight=cw).fit(Xtr, ytr)
        hard, htr = hard_vote(clf, Xte, K), hard_vote(clf, Xtr, K)
        name = f"rf5_n{n}_d{d}_f{len(feats)}"
        joblib.dump(clf, MODELS / f"{name}.joblib")
        r = {"name": name, "trees": n, "depth": d,
             "nodes": int(sum(t.tree_.node_count for t in clf.estimators_)),
             "macro_f1_hard": round(f1_score(yte, hard, average="macro"), 4),
             "acc_test_hard": round(accuracy_score(yte, hard), 4),
             "acc_natural_hard": round(accuracy_score(yte, hard, sample_weight=w_nat), 4),
             "acc_train_hard": round(accuracy_score(ytr, htr), 4),
             "train_sec": round(time.time() - t0, 1)}
        rows.append(r)
        print(r, flush=True)
    sweep = pd.DataFrame(rows)
    sweep.to_csv(OUT / "sweep_5class.csv", index=False)
    best = sweep.set_index("name").loc[MODEL_NAME]

    # detailed results for the deployed model
    clf = joblib.load(MODELS / f"{MODEL_NAME}.joblib")
    hard = hard_vote(clf, Xte, K)
    pc = pd.DataFrame({"class": classes, "f1_hardvote": f1_score(yte, hard, average=None).round(4)})
    pc.to_csv(OUT / f"per_class_f1_{MODEL_NAME}.csv", index=False)
    cm = pd.DataFrame(confusion_matrix(yte, hard, normalize="true").round(4), index=classes, columns=classes)
    cm.to_csv(OUT / f"confusion_{MODEL_NAME}.csv")
    print("\n" + pc.to_string(index=False) + "\n\n" + cm.to_string())

    # 2,000 balanced rows for the C reference (step 6) and the board (step 8)
    rng = np.random.default_rng(0)
    per = 2000 // K
    idx = np.concatenate([np.sort(rng.choice(np.where(yte == c)[0], per, replace=False)) for c in range(K)])
    samp = pd.DataFrame(Xte[idx], columns=feats)
    samp["label_idx"] = yte[idx]
    samp["label"] = [classes[i] for i in yte[idx]]
    samp.to_csv(FIRMWARE / "sample_inputs_5class.csv", index=False)
    print(f"\nwrote {len(samp)} sample rows; hard-vote accuracy on them: {accuracy_score(yte[idx], hard[idx]):.4f}")

    json.dump({"name": MODEL_NAME, "classes": classes, "features": feats, "merge": MERGE5,
               **{k: (v.item() if hasattr(v, "item") else v) for k, v in best.items()}},
              open(OUT / "chosen.json", "w"), indent=2)

    if a.compare_groupings:
        print("\nComparing class groupings at the same model size (30 trees, depth 10)...")
        compare_groupings(feats)


if __name__ == "__main__":
    main()
