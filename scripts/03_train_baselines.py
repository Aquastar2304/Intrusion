"""
STEP 3 - TRAIN BASELINES: compare four model families on the original 8 categories.

Models (all on the same 37 features and the same leak-free split from step 2):
  rf   Random forest, 200 trees, unlimited depth, balanced class weights   (scikit-learn)
  xgb  XGBoost, 400 rounds, depth 8, balanced sample weights               (xgboost)
  mlp  Neural net 37 -> 128 -> 64 -> 8, ReLU + dropout                      (PyTorch)
  cnn  1-D CNN: 2 conv layers (32, 64 filters) -> pool to 8 -> 64 -> 8      (PyTorch)

The forest and XGBoost settings, and the network layer sizes, were read back from the
saved models in models/baselines/. Learning rate and epoch count for the networks are
standard defaults, so a re-run reproduces the ranking (forest first) with numbers that
may differ in the second decimal.

Why it matters: the forest scores best (macro-F1 0.672) but is 958 MB, and the ESP32
has 4 MB of flash. That is what motivates steps 4 to 6.

Inputs : data_out/train.parquet, data_out/test.parquet
Outputs: models/baselines/{rf.joblib, xgb.json, mlp.pt, cnn.pt, preprocess.joblib}
         results/baselines/{summary.csv, metrics.json, confusion_<m>.csv, report_<m>.txt}

Usage:
    python scripts/03_train_baselines.py                    # all four, full data (slow)
    python scripts/03_train_baselines.py --models rf xgb    # only some
    python scripts/03_train_baselines.py --sample 50000 --out-models tmp/m --out-results tmp/r   # quick check
"""
import argparse
import json
import os
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.utils.class_weight import compute_class_weight

from common import DATA, META, MODELS, RESULTS


def load(split):
    df = pd.read_parquet(DATA / f"{split}.parquet")
    feats = [c for c in df.columns if c not in META]
    return df[feats].astype("float32").to_numpy(), df["label"].astype(str).to_numpy(), feats


# ---------------------------------------------------------------- neural nets
def make_mlp(n_in, n_out):
    import torch.nn as nn
    return nn.Sequential(nn.Linear(n_in, 128), nn.ReLU(), nn.Dropout(0.2),
                         nn.Linear(128, 64), nn.ReLU(), nn.Dropout(0.2),
                         nn.Linear(64, n_out))


class CNN1D:
    """Built lazily so the file imports without torch when only rf/xgb are requested."""
    @staticmethod
    def make(n_out):
        import torch.nn as nn

        class Net(nn.Module):
            def __init__(self):
                super().__init__()
                self.net = nn.Sequential(
                    nn.Conv1d(1, 32, 3), nn.ReLU(),
                    nn.Conv1d(32, 64, 3), nn.ReLU(),
                    nn.AdaptiveMaxPool1d(8), nn.Flatten(),
                    nn.Linear(64 * 8, 64), nn.ReLU(), nn.Dropout(0.2),
                    nn.Linear(64, n_out))

            def forward(self, x):
                return self.net(x.unsqueeze(1))
        return Net()


def train_torch(model, Xtr, ytr, class_w, epochs, device):
    import torch
    model.to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = torch.nn.CrossEntropyLoss(weight=torch.tensor(class_w, dtype=torch.float32, device=device))
    Xt, yt = torch.tensor(Xtr), torch.tensor(ytr, dtype=torch.long)
    for ep in range(epochs):
        model.train()
        perm = torch.randperm(len(Xt))
        total = 0.0
        for i in range(0, len(Xt), 1024):
            idx = perm[i:i + 1024]
            xb, yb = Xt[idx].to(device), yt[idx].to(device)
            opt.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
            total += loss.item() * len(idx)
        print(f"     epoch {ep + 1:2d}/{epochs}  loss {total / len(Xt):.4f}", flush=True)
    return model


def predict_torch(model, X, device):
    import torch
    model.eval()
    out = []
    with torch.no_grad():
        for i in range(0, len(X), 8192):
            out.append(model(torch.tensor(X[i:i + 8192]).to(device)).argmax(1).cpu().numpy())
    return np.concatenate(out)


# ---------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["rf", "xgb", "mlp", "cnn"])
    ap.add_argument("--sample", type=int, default=0, help="subsample training rows for a quick run")
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--out-models", default=str(MODELS / "baselines"))
    ap.add_argument("--out-results", default=str(RESULTS / "baselines"))
    a = ap.parse_args()
    os.makedirs(a.out_models, exist_ok=True)
    os.makedirs(a.out_results, exist_ok=True)

    Xtr, ytr_raw, feats = load("train")
    Xte, yte_raw, _ = load("test")
    if a.sample and a.sample < len(Xtr):
        idx = np.random.default_rng(42).choice(len(Xtr), a.sample, replace=False)
        Xtr, ytr_raw = Xtr[idx], ytr_raw[idx]
    le = LabelEncoder().fit(ytr_raw)
    ytr, yte = le.transform(ytr_raw), le.transform(yte_raw)
    classes = list(le.classes_)
    K = len(classes)
    class_w = compute_class_weight("balanced", classes=np.arange(K), y=ytr)
    print(f"train {Xtr.shape}  test {Xte.shape}  classes {classes}")

    scaler = StandardScaler().fit(Xtr)
    joblib.dump({"scaler": scaler, "features": feats, "classes": classes},
                os.path.join(a.out_models, "preprocess.joblib"))

    device = "cpu"
    if {"mlp", "cnn"} & set(a.models):
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"

    results = []
    for name in a.models:
        print(f"\n== {name} ==", flush=True)
        t0 = time.time()
        if name == "rf":
            m = RandomForestClassifier(n_estimators=200, n_jobs=-1, random_state=42,
                                       class_weight=dict(enumerate(class_w))).fit(Xtr, ytr)
            pred = m.predict(Xte)
            path = os.path.join(a.out_models, "rf.joblib"); joblib.dump(m, path)
        elif name == "xgb":
            from xgboost import XGBClassifier
            m = XGBClassifier(n_estimators=400, max_depth=8, learning_rate=0.1, tree_method="hist",
                              n_jobs=-1, random_state=42)
            m.fit(Xtr, ytr, sample_weight=class_w[ytr])
            pred = m.predict(Xte)
            path = os.path.join(a.out_models, "xgb.json"); m.save_model(path)
        elif name in ("mlp", "cnn"):
            import torch
            torch.manual_seed(42)
            net = make_mlp(Xtr.shape[1], K) if name == "mlp" else CNN1D.make(K)
            Xs_tr = scaler.transform(Xtr).astype("float32")
            Xs_te = scaler.transform(Xte).astype("float32")
            net = train_torch(net, Xs_tr, ytr, class_w, a.epochs, device)
            pred = predict_torch(net, Xs_te, device)
            path = os.path.join(a.out_models, f"{name}.pt"); torch.save(net.state_dict(), path)
        else:
            raise SystemExit(f"unknown model {name}")
        sec = round(time.time() - t0, 1)

        f1s = f1_score(yte, pred, average=None)
        r = {"model": name, "accuracy": round(accuracy_score(yte, pred), 4),
             "macro_f1": round(f1_score(yte, pred, average="macro"), 4),
             "weighted_f1": round(f1_score(yte, pred, average="weighted"), 4),
             "per_class_f1": {c: round(float(v), 4) for c, v in zip(classes, f1s)},
             "train_sec": sec, "size_mb": round(os.path.getsize(path) / 1e6, 3)}
        if name in ("mlp", "cnn"):
            r["device"] = device
        results.append(r)
        pd.DataFrame(confusion_matrix(yte, pred), index=classes, columns=classes).to_csv(
            os.path.join(a.out_results, f"confusion_{name}.csv"))
        open(os.path.join(a.out_results, f"report_{name}.txt"), "w").write(
            classification_report(yte, pred, target_names=classes, digits=4))
        print(f"   accuracy {r['accuracy']}  macro-F1 {r['macro_f1']}  size {r['size_mb']} MB  ({sec}s)")

    json.dump(results, open(os.path.join(a.out_results, "metrics.json"), "w"), indent=2)
    summary = pd.DataFrame([{k: r[k] for k in ("model", "macro_f1", "weighted_f1", "accuracy", "train_sec", "size_mb")}
                            for r in results])
    summary.to_csv(os.path.join(a.out_results, "summary.csv"), index=False)
    print("\n" + summary.to_string(index=False))


if __name__ == "__main__":
    main()
