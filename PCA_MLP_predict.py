# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
PCA + MLP  —  Cp Time-Series Prediction
=========================================
ALGORITHM:  PCA  +  MLP  (recommended over plain MLP for large outputs)

WHY PCA + MLP?
  Your Cp time series (~10 000 values per row) is NOT random — it is
  periodic and spatially correlated.  PCA finds the ~20-50 dominant
  "shapes" (modes) that explain 99 % of the variance.
  The MLP only needs to learn 6 inputs → 20-50 numbers, NOT 6 → 10 000.

  Comparison:
  ┌─────────────────────┬───────────────────┬──────────────────┐
  │                     │  Plain MLP        │  PCA + MLP       │
  ├─────────────────────┼───────────────────┼──────────────────┤
  │ Output neurons      │ ~10 000           │ ~30 (99 % var)   │
  │ Last-layer params   │ 128 × 10k = 1.28M │ 128 × 30 = 3 840 │
  │ Training speed      │ slow              │ 10× faster       │
  │ Overfitting risk    │ high              │ low              │
  │ Physics-aware       │ no                │ yes (POD modes)  │
  └─────────────────────┴───────────────────┴──────────────────┘

DATA FORMAT (your CSV):
  Named columns  → inputs (6):
      Re, TI, AOA, x/C, y/C, port angle
  Unnamed columns → Cp time steps (outputs, col 7 → NTV)

USAGE:
  # Train
  python PCA_MLP_predict.py --csv your_data.csv --train

  # Predict  (loop over all x/C, y/C, port angle in the CSV)
  python PCA_MLP_predict.py --csv your_data.csv --predict \\
         --Re 96000 --TI 0.51 --AOA 10

HOW IT WORKS (step by step):
  TRAIN:
    1. Load CSV  →  X (n, 6),  y (n, ~10 000)
    2. Scale X with StandardScaler
    3. Apply PCA to y  →  keep modes that explain >= PCA_VARIANCE (99 %)
       y becomes  (n, n_modes)  where  n_modes << 10 000
    4. Train MLP:  X_scaled  →  y_pca   (small multi-output regression)
    5. Save: model, X-scaler, PCA object

  PREDICT:
    1. Build input vector  [Re, TI, AOA, x/C, y/C, port angle]
    2. Scale with saved X-scaler
    3. MLP predicts PCA coefficients  (n_modes values)
    4. PCA.inverse_transform  →  full Cp time series  (~10 000 values)
    5. Save as Excel
"""

# ==============================================================
# FORCE CPU  (safe for clusters / nohup)
# ==============================================================
import os
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

# ==============================================================
# IMPORTS
# ==============================================================
import argparse
import time
import numpy as np
import pandas as pd
import joblib

from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.metrics import median_absolute_error
from scipy.stats import skew, kurtosis

import tensorflow as tf
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import Dense, Input, BatchNormalization, Dropout
from tensorflow.keras.callbacks import Callback, ReduceLROnPlateau, EarlyStopping

# ==============================================================
# REPRODUCIBILITY
# ==============================================================
RANDOM_STATE = 42
tf.random.set_seed(RANDOM_STATE)
np.random.seed(RANDOM_STATE)

# ==============================================================
# COLUMN NAMES — must match your CSV header exactly
# ==============================================================
INPUT_COLS = ["Re", "TI", "AOA", "x/C", "y/C", "port angle"]

# ==============================================================
# OUTPUT DIRECTORY
# ==============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR  = os.path.join(BASE_DIR, "out_pca_mlp")
os.makedirs(OUT_DIR, exist_ok=True)

# ==============================================================
# HYPERPARAMETERS
# ==============================================================
PCA_VARIANCE  = 0.99    # keep modes until 99 % of Cp variance is captured
                        # increase to 0.9999 if you need more accuracy

EPOCHS        = 500
BATCH_SIZE    = 32      # small — few rows after PCA
LEARNING_RATE = 0.001
TEST_RATIO    = 0.2
LOG_EVERY     = 10

# Compact network — output is now only ~30 modes, not 10 000
HIDDEN_UNITS = [256, 128, 64]
DROPOUT_RATE = 0.1

# ==============================================================
# READ CSV
# ==============================================================
def read_csv(csv_path):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"[INFO] Loaded: {csv_path}  shape: {df.shape}")
    missing = [c for c in INPUT_COLS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Missing columns: {missing}\n"
            f"CSV has: {list(df.columns[:10])} ...")
    return df

# ==============================================================
# SPLIT INPUTS / OUTPUTS
# ==============================================================
def split_X_y(df):
    X       = df[INPUT_COLS].values.astype(np.float32)
    cp_cols = [c for c in df.columns if c not in INPUT_COLS]
    y       = df[cp_cols].values.astype(np.float32)
    print(f"[INFO] Inputs : {X.shape}   ({len(INPUT_COLS)} features)")
    print(f"[INFO] Outputs: {y.shape}   ({len(cp_cols)} Cp time steps)")
    return X, y, cp_cols

# ==============================================================
# METRICS  (in real Cp units)
# ==============================================================
def evaluate(y_true, y_pred, label=""):
    err = y_true - y_pred
    m = {
        "RMSE"     : np.sqrt(mean_squared_error(y_true, y_pred)),
        "MAE"      : mean_absolute_error(y_true, y_pred),
        "R2"       : r2_score(y_true, y_pred),
        "MedianAE" : median_absolute_error(y_true, y_pred),
        "StdDev"   : float(np.std(err)),
        "Skewness" : float(skew(err.flatten())),
        "Kurtosis" : float(kurtosis(err.flatten())),
    }
    if label:
        print(f"  [{label}]  RMSE={m['RMSE']:.5f}  "
              f"MAE={m['MAE']:.5f}  R²={m['R2']:.5f}")
    return m

# ==============================================================
# TRAINING CALLBACK
# ==============================================================
class MetricsCallback(Callback):
    """Logs metrics in real Cp units every LOG_EVERY epochs."""

    def __init__(self, Xtr, Xte, ytr_real, yte_real, pca):
        super().__init__()
        self.Xtr = Xtr; self.Xte = Xte
        self.ytr_real = ytr_real; self.yte_real = yte_real
        self.pca = pca
        self.train_hist = []; self.test_hist = []

    def on_epoch_end(self, epoch, logs=None):
        if (epoch + 1) % LOG_EVERY != 0:
            return
        # Predict PCA modes, then reconstruct full Cp
        ytr_pred = self.pca.inverse_transform(
            self.model.predict(self.Xtr, verbose=0))
        yte_pred = self.pca.inverse_transform(
            self.model.predict(self.Xte, verbose=0))

        tr = evaluate(self.ytr_real, ytr_pred)
        te = evaluate(self.yte_real, yte_pred)
        self.train_hist.append({"Epoch": epoch + 1, **tr})
        self.test_hist.append( {"Epoch": epoch + 1, **te})
        print(
            f"[Epoch {epoch+1:04d}]  "
            f"Train RMSE={tr['RMSE']:.5f}  R²={tr['R2']:.4f}  |  "
            f"Test  RMSE={te['RMSE']:.5f}  R²={te['R2']:.4f}"
        )

# ==============================================================
# TRAIN
# ==============================================================
def run_train(csv_path):
    df        = read_csv(csv_path)
    X, y, _   = split_X_y(df)

    # ── 1. Scale inputs ────────────────────────────────────────
    sx = StandardScaler()
    Xs = sx.fit_transform(X)

    # ── 2. PCA on Cp outputs ───────────────────────────────────
    # PCA finds the fewest modes that capture PCA_VARIANCE of the
    # total Cp variance.  Typically 20-50 modes for CFD data.
    pca = PCA(n_components=PCA_VARIANCE, svd_solver="full")
    y_pca = pca.fit_transform(y)          # (n_rows, n_modes)
    n_modes = y_pca.shape[1]
    var_explained = pca.explained_variance_ratio_.sum() * 100

    print(f"\n[PCA]  {n_modes} modes explain {var_explained:.3f}% of Cp variance")
    print(f"[PCA]  Output reduced: {y.shape[1]} → {n_modes} dimensions\n")

    # ── 3. Train / test split ──────────────────────────────────
    Xtr, Xte, ytr_pca, yte_pca = train_test_split(
        Xs, y_pca,
        test_size=TEST_RATIO,
        random_state=RANDOM_STATE,
        shuffle=True)

    # Real Cp for metric logging
    ytr_real = pca.inverse_transform(ytr_pca)
    yte_real = pca.inverse_transform(yte_pca)

    print(f"[INFO] Train: {Xtr.shape[0]} rows  |  Test: {Xte.shape[0]} rows")

    # ── 4. Build MLP ───────────────────────────────────────────
    # Input: 6  →  hidden layers  →  Output: n_modes  (~20-50)
    # Much smaller than 10 000 — trains fast, generalises well.
    layers = [Input(shape=(X.shape[1],))]
    for units in HIDDEN_UNITS:
        layers += [
            Dense(units, activation="relu"),
            BatchNormalization(),
            Dropout(DROPOUT_RATE),
        ]
    layers.append(Dense(n_modes, activation="linear"))

    model = Sequential(layers)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=LEARNING_RATE),
        loss="mse")
    model.summary()

    # ── 5. Callbacks ───────────────────────────────────────────
    reduce_lr  = ReduceLROnPlateau(
        monitor="val_loss", factor=0.5, patience=20,
        min_lr=1e-6, verbose=1)
    early_stop = EarlyStopping(
        monitor="val_loss", patience=50,
        restore_best_weights=True, verbose=1)
    metrics_cb = MetricsCallback(Xtr, Xte, ytr_real, yte_real, pca)

    # ── 6. Train ───────────────────────────────────────────────
    print("[INFO] Training started ...")
    t0 = time.time()
    model.fit(
        Xtr, ytr_pca,
        epochs=EPOCHS, batch_size=BATCH_SIZE,
        validation_data=(Xte, yte_pca),
        callbacks=[metrics_cb, reduce_lr, early_stop],
        verbose=0)
    print(f"[INFO] Training done in {time.time()-t0:.1f}s")

    # ── 7. Final metrics ───────────────────────────────────────
    print("\n[FINAL METRICS — real Cp units]")
    ytr_pred = pca.inverse_transform(model.predict(Xtr, verbose=0))
    yte_pred = pca.inverse_transform(model.predict(Xte, verbose=0))
    evaluate(ytr_real, ytr_pred, label="Train")
    evaluate(yte_real, yte_pred, label="Test ")

    # ── 8. Save ────────────────────────────────────────────────
    with pd.ExcelWriter(
            os.path.join(OUT_DIR, "metrics_vs_epochs.xlsx")) as w:
        pd.DataFrame(metrics_cb.train_hist).to_excel(
            w, sheet_name="Train", index=False)
        pd.DataFrame(metrics_cb.test_hist).to_excel(
            w, sheet_name="Test", index=False)

    model.save(os.path.join(OUT_DIR, "mlp_model.keras"))
    joblib.dump(sx,  os.path.join(OUT_DIR, "scaler_X.joblib"))
    joblib.dump(pca, os.path.join(OUT_DIR, "pca.joblib"))

    print(f"[INFO] Saved to: {OUT_DIR}")

# ==============================================================
# PREDICT
# ==============================================================
def run_predict(csv_path, Re, TI, AOA):
    """
    For each unique (x/C, y/C, port angle) in the CSV:
      1. Build input [Re, TI, AOA, x/C, y/C, port angle]
      2. MLP → PCA mode coefficients
      3. PCA.inverse_transform → full Cp time series
      4. Save as Excel  (columns: time_step, Cp)
    """
    if None in (Re, TI, AOA):
        raise ValueError("Provide --Re, --TI, and --AOA")

    model = load_model(os.path.join(OUT_DIR, "mlp_model.keras"), compile=False)
    sx    = joblib.load(os.path.join(OUT_DIR, "scaler_X.joblib"))
    pca   = joblib.load(os.path.join(OUT_DIR, "pca.joblib"))

    df     = read_csv(csv_path)
    coords = (df[["x/C", "y/C", "port angle"]]
              .drop_duplicates().values)

    print(f"[INFO] Re={Re}  TI={TI}  AOA={AOA}")
    print(f"[INFO] Predicting for {len(coords)} coordinate points ...")

    for xc, yc, pa in coords:
        # Build + scale input
        X_raw    = np.array([[Re, TI, AOA, xc, yc, pa]], dtype=np.float32)
        X_scaled = sx.transform(X_raw)

        # MLP → PCA modes → Cp time series
        pca_pred = model.predict(X_scaled, verbose=0)          # (1, n_modes)
        cp_pred  = pca.inverse_transform(pca_pred).flatten()   # (n_time,)

        filename = (
            f"pred_Re{int(Re)}_TI{TI}_AOA{AOA}"
            f"_xC{xc:.5f}_yC{yc:.5f}_pa{pa:.1f}.xlsx"
        )
        pd.DataFrame({
            "time_step": np.arange(len(cp_pred)),
            "Cp"       : cp_pred,
        }).to_excel(os.path.join(OUT_DIR, filename), index=False)

    print(f"[INFO] All results saved to: {OUT_DIR}")

# ==============================================================
# CLI
# ==============================================================
def parse_args():
    p = argparse.ArgumentParser(
        description="PCA + MLP — predict Cp time series")
    p.add_argument("--csv",     required=True,      help="Path to CSV")
    p.add_argument("--train",   action="store_true", help="Run training")
    p.add_argument("--predict", action="store_true", help="Run prediction")
    p.add_argument("--Re",  type=float, help="Reynolds number  (e.g. 96000)")
    p.add_argument("--TI",  type=float, help="Turbulence intensity (e.g. 0.51)")
    p.add_argument("--AOA", type=float, help="Angle of attack, deg (e.g. 10)")
    return p.parse_args()

# ==============================================================
# MAIN
# ==============================================================
if __name__ == "__main__":
    args = parse_args()
    if args.train:
        run_train(args.csv)
    elif args.predict:
        run_predict(args.csv, args.Re, args.TI, args.AOA)
    else:
        print("Use --train or --predict. See file header for full usage.")
