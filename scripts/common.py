"""
Shared settings for every numbered script.

Importing this file also moves the working directory to the project root, so each
script can be run from anywhere:   python scripts/05_train_final_model.py
"""
import json
import os
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)

# ---- folders ---------------------------------------------------------------
RAW_CSV = Path("Dataset/CSV/CSV")          # the 309 CIC-IoT-2023 CSV files
DATA = Path("data_out")                    # cleaned parquet splits + inventory
MODELS = Path("models")                    # trained models
RESULTS = Path("results")                  # every number the slides quote
FIRMWARE = Path("firmware")                # ESP32 sketches, C reference, samples
SKETCH = FIRMWARE / "esp32_ids_demo"       # the sketch that is flashed to the board

# ---- the deployed model ----------------------------------------------------
MODEL_NAME = "rf5_n30_d10_f25"             # 5 classes, 30 trees, depth 10, 25 features
FEATURES_FILE = MODELS / "selected_features.json"

# Columns added by 02_build_dataset.py that are bookkeeping, not features.
META = ["label", "fine_label", "src_file"]

# 8 original categories -> 5 classes used on the chip.
MERGE5 = {"DDoS": "Flood", "DoS": "Flood",
          "Recon": "Probe", "Web": "Probe", "BruteForce": "Probe"}
CLASSES5 = ["Benign", "Flood", "Mirai", "Probe", "Spoofing"]   # alphabetical = label index


def selected_features():
    """The 25 features chosen by 04_select_features.py, in the order the C code expects."""
    return json.load(open(FEATURES_FILE))


def hard_vote(forest, X, n_classes):
    """Majority vote, one vote per tree.

    This is exactly what the emlearn C code does on the ESP32. scikit-learn's own
    predict() averages probabilities instead, which disagrees on about 2% of rows,
    so every score in this project is computed with this function.
    """
    votes = np.zeros((len(X), n_classes), np.int32)
    rows = np.arange(len(X))
    for tree in forest.estimators_:
        votes[rows, tree.predict(X).astype(int)] += 1
    return votes.argmax(1)


def natural_weights(original_categories):
    """Per-row weights so accuracy reflects a real traffic mix.

    Each test row is weighted by how common its original category is in the full
    46.8M-row dataset (from data_out/inventory.csv), divided by how many test rows
    that category has. Floods dominate real traffic, so they dominate this score.
    """
    import pandas as pd
    inv = pd.read_csv(DATA / "inventory.csv")
    share = inv.groupby("category").n_rows.sum()
    share = share / share.sum()
    cats = pd.Series(original_categories)
    counts = cats.value_counts()
    return cats.map(lambda c: share[c] / counts[c]).to_numpy()
