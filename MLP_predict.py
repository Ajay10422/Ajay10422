# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
MLP (Multi-Layer Perceptron) for Cp Time-Series Prediction
===========================================================
DATA FORMAT (your CSV):
    Named columns (inputs):
        Re          — Reynolds number          (e.g. 96000)
        TI          — Turbulence intensity      (e.g. 0.51)
        AOA         — Angle of attack (degrees) (e.g. 0, 5, 10 ...)
        x/C         — Chord-normalised x coord  (e.g. -1)
        y/C         — Chord-normalised y coord  (e.g. 0.0)
        port angle  — Port angle (degrees)      (e.g. 0)

    Unnamed columns (outputs, col 7 → NTV):
        Cp values at each time step  (~10 000 values per row)

WHY MLP (not LSTM)?
    Each ROW is independent — the 6 inputs map to the full Cp time series.
    The time dimension is IN THE OUTPUT (one value per time step), not in
    the input.  MLP handles multi-output regression directly.
    LSTM would be needed only if inputs were also a time sequence.

PLUG AND PLAY:
  Step 1 — Train:
      python MLP_predict.py --csv your_data.csv --train

  Step 2 — Predict (provide Re, TI, AOA; x/C + y/C + port-angle loop from CSV):
      python MLP_predict.py --csv your_data.csv --predict \\
             --Re 96000 --TI 0.51 --AOA 10
"""

# ==============================================================
# FORCE CPU (safe for clusters / nohup)
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
# All columns after these 6 are Cp time-series outputs (no header needed)

# ==============================================================
# OUTPUT DIRECTORY
# ==============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR  = os.path.join(BASE_DIR, "out_mlp")
os.makedirs(OUT_DIR, exist_ok=True)

# ==============================================================
# HYPERPARAMETERS
# ==============================================================
EPOCHS        = 500     # EarlyStopping will stop earlier if needed
BATCH_SIZE    = 64      # smaller batch — output is very wide (~10 000)
LEARNING_RATE = 0.001
TEST_RATIO    = 0.2
LOG_EVERY     = 10

# Wider network because output can be ~10 000 time steps.
# The final Dense(n_timesteps) can have 256 * 10000 = 2.56 M params —
# that is fine for a modern GPU/CPU.
HIDDEN_UNITS = [512, 512, 256, 128]
DROPOUT_RATE = 0.1

# ==============================================================
# READ CSV
# ==============================================================
def read_csv(csv_path):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"[INFO] Loaded: {csv_path} — shape: {df.shape}")
    # Validate input columns
    missing = [c for c in INPUT_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in CSV: {missing}\n"
                         f"CSV has: {list(df.columns[:10])} ...")
    return df

# ==============================================================
# SPLIT INPUTS / OUTPUTS
# ==============================================================
def split_X_y(df):
    """
    Returns:
        X  — numpy (n_rows, 6)      — Re, TI, AOA, x/C, y/C, port angle
        y  — numpy (n_rows, n_time) — Cp at each time step
        cp_cols — list of output column names (for saving results)
    """
    X       = df[INPUT_COLS].values.astype(np.float32)
    cp_cols = [c for c in df.columns if c not in INPUT_COLS]
    y       = df[cp_cols].values.astype(np.float32)
    print(f"[INFO] Inputs : {X.shape}  ({len(INPUT_COLS)} features)")
    print(f"[INFO] Outputs: {y.shape}  ({len(cp_cols)} Cp time steps)")
    return X, y, cp_cols

# ==============================================================
# METRICS
# ==============================================================
def evaluate(y_true, y_pred, label=""):
    err = y_true - y_pred
    metrics = {
        "RMSE"     : np.sqrt(mean_squared_error(y_true, y_pred)),
        "MAE"      : mean_absolute_error(y_true, y_pred),
        "R2"       : r2_score(y_true, y_pred),
        "MedianAE" : median_absolute_error(y_true, y_pred),
        "StdDev"   : np.std(err),
        "Skewness" : float(skew(err.flatten())),
        "Kurtosis" : float(kurtosis(err.flatten())),
    }
    if label:
        print(f"  [{label}] RMSE={metrics['RMSE']:.5f} | "
              f"MAE={metrics['MAE']:.5f} | R²={metrics['R2']:.5f}")
    return metrics

# ==============================================================
# TRAINING CALLBACK
# ==============================================================
class MetricsCallback(Callback):
    def __init__(self, Xtr, ytr_real, Xte, yte_real, sy):
        super().__init__()
        self.Xtr = Xtr; self.Xte = Xte
        self.ytr_real = ytr_real; self.yte_real = yte_real
        self.sy = sy
        self.train_hist = []; self.test_hist = []

    def on_epoch_end(self, epoch, logs=None):
        if (epoch + 1) % LOG_EVERY != 0:
            return
        ytr_pred = self.sy.inverse_transform(
            self.model.predict(self.Xtr, verbose=0))
        yte_pred = self.sy.inverse_transform(
            self.model.predict(self.Xte, verbose=0))
        tr = evaluate(self.ytr_real, ytr_pred)
        te = evaluate(self.yte_real, yte_pred)
        self.train_hist.append({"Epoch": epoch + 1, **tr})
        self.test_hist.append( {"Epoch": epoch + 1, **te})
        print(
            f"[Epoch {epoch+1:04d}] "
            f"Train RMSE={tr['RMSE']:.5f}  R²={tr['R2']:.4f} | "
            f"Test  RMSE={te['RMSE']:.5f}  R²={te['R2']:.4f}"
        )

# ==============================================================
# TRAIN
# ==============================================================
def run_train(csv_path):
    df       = read_csv(csv_path)
    X, y, _  = split_X_y(df)

    sx = StandardScaler(); sy = StandardScaler()
    Xs = sx.fit_transform(X)
    ys = sy.fit_transform(y)

    Xtr, Xte, ytr_s, yte_s = train_test_split(
        Xs, ys, test_size=TEST_RATIO,
        random_state=RANDOM_STATE, shuffle=True)

    ytr_real = sy.inverse_transform(ytr_s)
    yte_real = sy.inverse_transform(yte_s)

    print(f"[INFO] Train: {Xtr.shape[0]} rows | Test: {Xte.shape[0]} rows")

    # ----------------------------------------------------------
    # MODEL
    # Input(6) → Dense(512) → BN → Drop
    #          → Dense(512) → BN → Drop
    #          → Dense(256) → BN → Drop
    #          → Dense(128) → BN → Drop
    #          → Dense(n_timesteps)   ← full Cp time series
    # ----------------------------------------------------------
    layers = [Input(shape=(X.shape[1],))]
    for units in HIDDEN_UNITS:
        layers += [
            Dense(units, activation="relu"),
            BatchNormalization(),
            Dropout(DROPOUT_RATE),
        ]
    layers.append(Dense(y.shape[1], activation="linear"))

    model = Sequential(layers)
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=LEARNING_RATE),
        loss="mse")
    model.summary()

    reduce_lr  = ReduceLROnPlateau(
        monitor="val_loss", factor=0.5, patience=20, min_lr=1e-6, verbose=1)
    early_stop = EarlyStopping(
        monitor="val_loss", patience=50,
        restore_best_weights=True, verbose=1)
    metrics_cb = MetricsCallback(Xtr, ytr_real, Xte, yte_real, sy)

    print("[INFO] Training started...")
    t0 = time.time()
    model.fit(
        Xtr, ytr_s,
        epochs=EPOCHS, batch_size=BATCH_SIZE,
        validation_data=(Xte, yte_s),
        callbacks=[metrics_cb, reduce_lr, early_stop],
        verbose=0)
    print(f"[INFO] Training finished in {time.time() - t0:.1f}s")

    # Final metrics
    print("\n[FINAL METRICS — real Cp units]")
    ytr_pred = sy.inverse_transform(model.predict(Xtr, verbose=0))
    yte_pred = sy.inverse_transform(model.predict(Xte, verbose=0))
    evaluate(ytr_real, ytr_pred, label="Train")
    evaluate(yte_real, yte_pred, label="Test ")

    # Save
    with pd.ExcelWriter(os.path.join(OUT_DIR, "metrics_vs_epochs.xlsx")) as w:
        pd.DataFrame(metrics_cb.train_hist).to_excel(
            w, sheet_name="Train", index=False)
        pd.DataFrame(metrics_cb.test_hist).to_excel(
            w, sheet_name="Test", index=False)

    model.save(os.path.join(OUT_DIR, "mlp_model.keras"))
    joblib.dump(sx, os.path.join(OUT_DIR, "scaler_X.joblib"))
    joblib.dump(sy, os.path.join(OUT_DIR, "scaler_Y.joblib"))
    print(f"[INFO] Model and scalers saved to: {OUT_DIR}")

# ==============================================================
# PREDICT
# ==============================================================
def run_predict(csv_path, Re, TI, AOA):
    """
    Given Re, TI, AOA — loop over every unique (x/C, y/C, port angle)
    found in the CSV and predict the full Cp time series for each.
    One Excel file is saved per unique coordinate point.
    """
    if None in (Re, TI, AOA):
        raise ValueError("Provide --Re, --TI, and --AOA")

    model = load_model(os.path.join(OUT_DIR, "mlp_model.keras"), compile=False)
    sx    = joblib.load(os.path.join(OUT_DIR, "scaler_X.joblib"))
    sy    = joblib.load(os.path.join(OUT_DIR, "scaler_Y.joblib"))

    df     = read_csv(csv_path)
    coords = (df[["x/C", "y/C", "port angle"]]
              .drop_duplicates()
              .values)

    print(f"[INFO] Re={Re}  TI={TI}  AOA={AOA}")
    print(f"[INFO] Predicting Cp time series for "
          f"{len(coords)} coordinate points ...")

    for xc, yc, pa in coords:
        X_raw    = np.array([[Re, TI, AOA, xc, yc, pa]], dtype=np.float32)
        X_scaled = sx.transform(X_raw)
        y_scaled = model.predict(X_scaled, verbose=0)          # (1, n_time)
        y_pred   = sy.inverse_transform(y_scaled).flatten()    # (n_time,)

        filename = (
            f"pred_Re{int(Re)}_TI{TI}_AOA{AOA}"
            f"_xC{xc:.5f}_yC{yc:.5f}_pa{pa:.1f}.xlsx"
        )
        # Save as a single column: time_step | Cp
        out_df = pd.DataFrame({
            "time_step": np.arange(len(y_pred)),
            "Cp"       : y_pred,
        })
        out_df.to_excel(os.path.join(OUT_DIR, filename), index=False)

    print(f"[INFO] All predictions saved to: {OUT_DIR}")

# ==============================================================
# CLI
# ==============================================================
def parse_args():
    p = argparse.ArgumentParser(
        description="MLP — predict Cp time series from Re/TI/AOA/x/y/angle")
    p.add_argument("--csv",     required=True,       help="Path to CSV file")
    p.add_argument("--train",   action="store_true",  help="Run training")
    p.add_argument("--predict", action="store_true",  help="Run prediction")
    # Prediction inputs
    p.add_argument("--Re",  type=float, help="Reynolds number  (e.g. 96000)")
    p.add_argument("--TI",  type=float, help="Turbulence intensity (e.g. 0.51)")
    p.add_argument("--AOA", type=float, help="Angle of attack, degrees (e.g. 10)")
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
