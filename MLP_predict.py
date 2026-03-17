# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
MLP (Multi-Layer Perceptron) for Cp Prediction
===============================================
WHY MLP?
  - Your data is tabular: each row has 6 fixed inputs and maps to a Cp output.
  - There is no time or sequence involved — each row is independent.
  - MLP is the standard and most reliable model for this type of regression.
  - LSTM/GRU/Transformer are sequence models and are NOT suitable here.

PLUG AND PLAY:
  Step 1 — Train:
      python MLP_predict.py --csv your_data.csv --train

  Step 2 — Predict:
      python MLP_predict.py --csv your_data.csv --predict --f1 1.0 --f2 2.0 --f3 5.0

  CSV FORMAT:
      Columns 0-5  → 6 input features  (f1, f2, f3, f4, f5, f6)
      Columns 6+   → target output(s)  (Cp values)
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

# StandardScaler is used instead of MinMaxScaler because:
#   - Cp can have large negative spikes (e.g. -5 near leading edge)
#   - MinMaxScaler compresses everything to [0,1] and gets distorted by outliers
#   - StandardScaler (mean=0, std=1) is more robust for physics data
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
# OUTPUT DIRECTORY
# ==============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR  = os.path.join(BASE_DIR, "out_mlp")
os.makedirs(OUT_DIR, exist_ok=True)

# ==============================================================
# HYPERPARAMETERS — adjust these if needed
# ==============================================================
EPOCHS        = 500         # max training epochs (EarlyStopping will stop earlier if needed)
BATCH_SIZE    = 128         # samples per gradient update
LEARNING_RATE = 0.001       # Adam optimizer starting learning rate
TEST_RATIO    = 0.2         # 20% of data used for testing
LOG_EVERY     = 10          # print metrics every N epochs

# Network layers: [256 neurons] → [128] → [64]
# These sizes work well for 6 inputs. Increase if Cp distribution is complex.
HIDDEN_UNITS  = [256, 128, 64]
DROPOUT_RATE  = 0.1         # randomly drops 10% of neurons each step — prevents overfitting

# ==============================================================
# READ CSV
# ==============================================================
def read_csv(csv_path):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"[INFO] Loaded: {csv_path} — shape: {df.shape}")
    return df

# ==============================================================
# METRICS — computed in REAL (physical) units, not scaled
# ==============================================================
def evaluate(y_true, y_pred, label=""):
    """
    All metrics are in original Cp units (after inverse_transform).
    RMSE here is the true physical error — not the misleading scaled version.
    """
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
        print(f"  [{label}] RMSE={metrics['RMSE']:.5f} | MAE={metrics['MAE']:.5f} | R²={metrics['R2']:.5f}")
    return metrics

# ==============================================================
# TRAINING CALLBACK — logs real-unit metrics every LOG_EVERY epochs
# ==============================================================
class MetricsCallback(Callback):
    def __init__(self, Xtr, ytr_real, Xte, yte_real, sy):
        """
        ytr_real / yte_real : labels in original Cp units
        sy                  : y-scaler, used to inverse-transform predictions
        """
        super().__init__()
        self.Xtr      = Xtr
        self.Xte      = Xte
        self.ytr_real = ytr_real
        self.yte_real = yte_real
        self.sy       = sy
        self.train_hist = []
        self.test_hist  = []

    def on_epoch_end(self, epoch, logs=None):
        if (epoch + 1) % LOG_EVERY != 0:
            return

        # Predict in scaled space, then convert back to real units
        ytr_pred = self.sy.inverse_transform(self.model.predict(self.Xtr, verbose=0))
        yte_pred = self.sy.inverse_transform(self.model.predict(self.Xte, verbose=0))

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
    df = read_csv(csv_path)

    # First 6 columns = inputs, remaining = Cp outputs
    X = df.iloc[:, :6].values.astype(np.float32)
    y = df.iloc[:, 6:].values.astype(np.float32)

    print(f"[INFO] Inputs: {X.shape} | Outputs: {y.shape}")

    # ----------------------------------------------------------
    # SCALE INPUTS AND OUTPUTS
    # StandardScaler: transforms each feature to mean=0, std=1
    # This is critical — neural networks train poorly on raw unscaled data
    # ----------------------------------------------------------
    sx = StandardScaler()
    sy = StandardScaler()
    Xs = sx.fit_transform(X)
    ys = sy.fit_transform(y)

    # ----------------------------------------------------------
    # SHUFFLE + SPLIT
    # shuffle=True ensures the model sees all regions of parameter
    # space during training, not just the first 80% of rows.
    # This was the primary cause of high prediction variance before.
    # ----------------------------------------------------------
    Xtr, Xte, ytr_s, yte_s = train_test_split(
        Xs, ys,
        test_size=TEST_RATIO,
        random_state=RANDOM_STATE,
        shuffle=True           # KEY FIX: prevents ordered-data bias
    )

    # Keep real-unit labels for metric logging
    ytr_real = sy.inverse_transform(ytr_s)
    yte_real = sy.inverse_transform(yte_s)

    print(f"[INFO] Train: {Xtr.shape[0]} samples | Test: {Xte.shape[0]} samples")

    # ----------------------------------------------------------
    # MODEL ARCHITECTURE
    #
    # Input(6) → Dense(256) → BN → Dropout
    #          → Dense(128) → BN → Dropout
    #          → Dense(64)  → BN → Dropout
    #          → Dense(output)
    #
    # BatchNormalization: normalizes activations between layers,
    #   makes training faster and more stable.
    # Dropout(0.1): randomly disables 10% of neurons during training,
    #   prevents the model from memorizing rather than learning.
    # ----------------------------------------------------------
    model = Sequential([
        Input(shape=(X.shape[1],)),

        Dense(HIDDEN_UNITS[0], activation="relu"),
        BatchNormalization(),
        Dropout(DROPOUT_RATE),

        Dense(HIDDEN_UNITS[1], activation="relu"),
        BatchNormalization(),
        Dropout(DROPOUT_RATE),

        Dense(HIDDEN_UNITS[2], activation="relu"),
        BatchNormalization(),
        Dropout(DROPOUT_RATE),

        Dense(y.shape[1], activation="linear")   # linear output for regression
    ])

    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=LEARNING_RATE),
        loss="mse"
    )

    model.summary()

    # ----------------------------------------------------------
    # CALLBACKS
    # ReduceLROnPlateau: halves learning rate if validation loss
    #   stops improving for 20 epochs — avoids getting stuck.
    # EarlyStopping: stops training when test loss stops improving
    #   for 50 epochs — saves time and prevents overfitting.
    # ----------------------------------------------------------
    reduce_lr = ReduceLROnPlateau(
        monitor="val_loss", factor=0.5,
        patience=20, min_lr=1e-6, verbose=1
    )
    early_stop = EarlyStopping(
        monitor="val_loss", patience=50,
        restore_best_weights=True, verbose=1
    )
    metrics_cb = MetricsCallback(Xtr, ytr_real, Xte, yte_real, sy)

    # ----------------------------------------------------------
    # TRAIN
    # ----------------------------------------------------------
    print("[INFO] Training started...")
    t0 = time.time()

    history = model.fit(
        Xtr, ytr_s,
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        validation_data=(Xte, yte_s),
        callbacks=[metrics_cb, reduce_lr, early_stop],
        verbose=0
    )

    print(f"[INFO] Training finished in {time.time() - t0:.1f}s")

    # ----------------------------------------------------------
    # FINAL EVALUATION IN REAL UNITS
    # ----------------------------------------------------------
    print("\n[FINAL METRICS — real Cp units]")
    ytr_pred = sy.inverse_transform(model.predict(Xtr, verbose=0))
    yte_pred = sy.inverse_transform(model.predict(Xte, verbose=0))
    evaluate(ytr_real, ytr_pred, label="Train")
    evaluate(yte_real, yte_pred, label="Test ")

    # ----------------------------------------------------------
    # SAVE
    # ----------------------------------------------------------
    train_df = pd.DataFrame(metrics_cb.train_hist)
    test_df  = pd.DataFrame(metrics_cb.test_hist)

    with pd.ExcelWriter(os.path.join(OUT_DIR, "metrics_vs_epochs.xlsx")) as w:
        train_df.to_excel(w, sheet_name="Train", index=False)
        test_df.to_excel(w, sheet_name="Test",  index=False)

    model.save(os.path.join(OUT_DIR, "mlp_model.keras"))
    joblib.dump(sx, os.path.join(OUT_DIR, "scaler_X.joblib"))
    joblib.dump(sy, os.path.join(OUT_DIR, "scaler_Y.joblib"))

    print(f"[INFO] Model and scalers saved to: {OUT_DIR}")

# ==============================================================
# PREDICT
# ==============================================================
def run_predict(csv_path, f1, f2, f3):
    if None in (f1, f2, f3):
        raise ValueError("Provide --f1, --f2, --f3")

    # Load trained model and scalers
    model = load_model(os.path.join(OUT_DIR, "mlp_model.keras"), compile=False)
    sx    = joblib.load(os.path.join(OUT_DIR, "scaler_X.joblib"))
    sy    = joblib.load(os.path.join(OUT_DIR, "scaler_Y.joblib"))

    df     = read_csv(csv_path)
    coords = df.iloc[:, 3:6].drop_duplicates().values  # unique (f4, f5, f6) combos

    print(f"[INFO] Predicting for f3={f3} across {len(coords)} coordinate points")

    for f4, f5, f6 in coords:
        # Build input vector — same 6 features the model was trained on
        X_raw    = np.array([[f1, f2, f3, f4, f5, f6]], dtype=np.float32)

        # Scale using the SAME scaler fitted during training
        X_scaled = sx.transform(X_raw)

        # Predict in scaled space, invert back to real Cp units
        y_scaled = model.predict(X_scaled, verbose=0)
        y_pred   = sy.inverse_transform(y_scaled)

        filename = (
            f"pred_f3_{float(f3):.1f}"
            f"_x_{float(f4):.5f}"
            f"_y_{float(f5):.5f}"
            f"_f6_{float(f6):.3f}.xlsx"
        )
        pd.DataFrame(y_pred).to_excel(os.path.join(OUT_DIR, filename), index=False)

    print(f"[INFO] All predictions saved to: {OUT_DIR}")

# ==============================================================
# CLI
# ==============================================================
def parse_args():
    p = argparse.ArgumentParser(description="MLP Cp Predictor")
    p.add_argument("--csv",     required=True,       help="Path to your CSV file")
    p.add_argument("--train",   action="store_true",  help="Run training")
    p.add_argument("--predict", action="store_true",  help="Run prediction")
    p.add_argument("--f1",      type=float,           help="Feature 1 value")
    p.add_argument("--f2",      type=float,           help="Feature 2 value")
    p.add_argument("--f3",      type=float,           help="Feature 3 / AOA value")
    return p.parse_args()

# ==============================================================
# MAIN
# ==============================================================
if __name__ == "__main__":
    args = parse_args()

    if args.train:
        run_train(args.csv)
    elif args.predict:
        run_predict(args.csv, args.f1, args.f2, args.f3)
    else:
        print("Use --train or --predict. See file header for usage.")
