# Lightweight IoT Intrusion Detection on an ESP32

A random forest trained on the CIC-IoT-2023 dataset, compressed from 958 MB to 240 KB,
converted to C and running on a $5 ESP32. It sorts network flows into five classes:
Benign, Flood, Mirai, Probe and Spoofing.

| Result | Value |
|---|---|
| Accuracy on a real traffic mix | 98.6% |
| Balanced accuracy, every class weighted equally | 84.3% |
| Macro-F1 | 0.82 |
| Board matches laptop, row for row | 2,000 of 2,000 |
| Time per flow on the ESP32 | 295 µs mean, 541 µs max |
| Model size on the chip | 240 KB flash, 0 B RAM |

## Folder layout

```
Project Intrution/
├── README.md                  this file
├── requirements.txt           Python libraries
├── scripts/                   the pipeline, run in number order
│   ├── common.py              shared folders, class names, voting rule
│   ├── 01_inventory.py
│   ├── 02_build_dataset.py
│   ├── 03_train_baselines.py
│   ├── 04_select_features.py
│   ├── 05_train_final_model.py
│   ├── 06_export_to_c.py
│   ├── 07_measure_footprint.py
│   ├── 08_parity_test.py
│   └── 09_live_demo.py
├── Dataset/CSV/CSV/           raw CIC-IoT-2023: 309 CSV files, 8.4 GB (not edited)
├── data_out/                  cleaned data made by steps 1 and 2
│   ├── inventory.csv          rows per file and per attack
│   ├── train/val/test.parquet 37 features + label, leak-free split
│   ├── split_manifest.csv     which rows of which file went to which split
│   └── build_report.txt       duplicate counts, leak check, dropped columns
├── models/
│   ├── selected_features.json the 25 features the chip uses, in order
│   ├── rf5_n30_d10_f25.joblib THE DEPLOYED MODEL
│   ├── rf5_n20_d6_f25.joblib  small comparison model
│   └── baselines/             the four step-3 models (rf.joblib is 958 MB)
├── firmware/
│   ├── esp32_ids_demo/        UPLOAD THIS SKETCH TO THE BOARD
│   │   ├── esp32_ids_demo.ino
│   │   └── model_rf5_n30_d10_f25.h   the forest as C code
│   ├── desktop_test/main.c    runs the same C model on the laptop
│   ├── sample_inputs_5class.csv       2,000 test rows for the board
│   └── desktop_preds_rf5_n30_d10_f25.csv  laptop C answers the board must match
├── results/                   every number used in the slides
│   ├── baselines/             step 3
│   ├── feature_selection/     step 4
│   ├── final_model/           step 5: sweep, confusion matrix, per-class F1
│   └── device/                steps 7 to 9: footprint, parity, demo logs
├── presentation/
│   ├── presentation_script.md what to say on each slide
│   └── src/                   code and images that build the deck
├── docs/                      original project plan
└── _archive/                  earlier experiments, not needed for the demo
```

## The pipeline, step by step

Run every script from the project folder, for example `python scripts/05_train_final_model.py`.

| Step | Script | What it does | Takes |
|---|---|---|---|
| 1 | `01_inventory.py` | Counts every file and row in the raw data, maps each attack to one of 8 categories, writes `data_out/inventory.csv` | 2 min |
| 2 | `02_build_dataset.py` | Drops 2 duplicate columns (39 to 37 features), removes duplicate rows, fills missing values with training medians, caps each category, splits 70/15/15 so no capture is shared between train and test | 10 min |
| 3 | `03_train_baselines.py` | Trains a random forest, XGBoost, an MLP and a CNN on 8 categories. The forest wins but is 958 MB | 15 min |
| 4 | `04_select_features.py` | Ranks the 37 features by importance and keeps the smallest set with no real loss: 25 | 5 min |
| 5 | `05_train_final_model.py` | Merges attacks into 5 classes, trains the 30-tree, depth-10 forest, scores it with majority voting, writes the 2,000-row board sample | 1 min |
| 6 | `06_export_to_c.py` | Converts the forest to C with emlearn, compiles it on the laptop with gcc, checks C and Python agree on all 2,000 rows | 30 s |
| 7 | `07_measure_footprint.py` | Compiles the sketch with and without the forest; the difference is the model's flash size | 2 min |
| 8 | `08_parity_test.py` | Sends the 2,000 rows to the board and checks every answer against the laptop C | 35 s |
| 9 | `09_live_demo.py` | The live demo: replays normal traffic and attacks, the chip classifies each flow and lights its LED | 1 min |

Steps 1 to 7 are already done and their results are saved. For the demo you only need steps 8 and 9.

## Running the demo

1. Open `firmware/esp32_ids_demo/esp32_ids_demo.ino` in the Arduino IDE. Choose board **ESP32 Dev Module**, flash size **4MB**, partition **Default 4MB with spiffs**, and upload. The LED blinks three times on boot.
2. Close the Arduino Serial Monitor. Only one program can use the COM port.
3. Optional check that the board runs the same model:

```bash
python scripts/08_parity_test.py --port COM15
```

4. The demo:

```bash
python scripts/09_live_demo.py --port COM15 --led --delay 0.5
```

5. Without the board, for rehearsal only:

```bash
python scripts/09_live_demo.py --dry-run
```

## Getting the data

The raw dataset is not in this repository. It is 8.4 GB and belongs to the Canadian Institute for Cybersecurity.

1. Request CIC-IoT-2023 from the official page: https://www.unb.ca/cic/datasets/iotdataset-2023.html
2. Download the CSV version and place the 34 attack folders in `Dataset/CSV/CSV/`.
3. Rebuild the cleaned splits, then the models:

```bash
pip install -r requirements.txt
python scripts/01_inventory.py
python scripts/02_build_dataset.py
python scripts/03_train_baselines.py
```

The deployed model, `models/rf5_n30_d10_f25.joblib`, and its C header are included, so steps 6 to 9 and the demo work without the dataset.
Two things are left out because of size: the cleaned `data_out/*.parquet` splits and the 958 MB baseline forest, `models/baselines/rf.joblib`. Steps 2 and 3 rebuild them.
The live demo, `scripts/09_live_demo.py`, needs `data_out/test.parquet`, so run steps 1 and 2 first.

## Key design choices

- **Leak-free split.** Attacks with 3 or more capture files are split by whole file. Attacks with 1 or 2 files are split into separate, non-overlapping row blocks in capture order. No row appears in two splits.
- **Majority voting everywhere.** The C code counts one vote per tree. scikit-learn averages probabilities instead, so every score is computed with the same voting the chip uses. That is why the laptop numbers predict the chip numbers.
- **Five classes.** DDoS and DoS look identical in these features, and so do Recon, Web and BruteForce. Merging them raised balanced accuracy from 78% to 84% at the same model size.
- **Two accuracy numbers.** Real-traffic accuracy, 98.6%, weights each class by how common it is in the full dataset, where floods dominate. Balanced accuracy, 84.3%, weights every class equally.
