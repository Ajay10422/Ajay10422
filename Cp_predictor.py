# -*- coding: utf-8 -*-
#!/usr/bin/env python3
"""
============================================================
  Cp (Coefficient of Pressure) Predictor
  Algorithm: PCA + MLP
  Input:  .xlsx file
  Output: .xlsx file  (one sheet per predicted condition)
============================================================

HOW TO USE — 3 easy steps:
  1. Open this file in any text editor
  2. Change the paths in the CONFIG section below
  3. Run:
       python Cp_predictor.py --train      ← first time only
       python Cp_predictor.py --predict    ← every time you want results

INSTALL required packages (run once in terminal):
  pip install tensorflow scikit-learn pandas numpy openpyxl scipy joblib

YOUR EXCEL FILE FORMAT:
  Row 1  = column headers (exactly as shown below)
  Col A  = Re          (Reynolds number,     e.g. 96000)
  Col B  = TI          (Turbulence intensity, e.g. 0.51)
  Col C  = AOA         (Angle of attack,      e.g. 0, 5, 10 ...)
  Col D  = x/C         (x/chord,              e.g. -1)
  Col E  = y/C         (y/chord,              e.g. 0)
  Col F  = port angle  (port angle,           e.g. 0)
  Col G+ = (no header) Cp values at each time step
"""

# ============================================================
#  ★  CONFIG — CHANGE THESE PATHS  ★
# ============================================================

# Path to your Excel file that contains all the training data
TRAIN_XLSX = "data.xlsx"

# Sheet name inside the Excel file  (use 0 for the first sheet)
SHEET_NAME = 0

# When predicting, loop over these conditions.
# Add or remove rows as needed.  Format: [Re, TI, AOA]
PREDICT_CONDITIONS = [
    [96000, 0.51,  0],
    [96000, 0.51,  5],
    [96000, 0.51, 10],
    [96000, 0.51, 15],
    [96000, 0.51, 20],
    [96000, 0.51, 25],
    [96000, 0.51, 30],
    [96000, 0.51, 35],
    [96000, 0.51, 40],
]

# Folder where trained model and results will be saved
OUTPUT_FOLDER = "Cp_results"

# ============================================================
#  ADVANCED SETTINGS  (only change if you know what you are doing)
# ============================================================
PCA_VARIANCE  = 0.99    # keep PCA modes until 99 % of Cp variance is captured
EPOCHS        = 500
BATCH_SIZE    = 32
LEARNING_RATE = 0.001
TEST_RATIO    = 0.20    # 20 % of data used for validation
HIDDEN_UNITS  = [256, 128, 64]
DROPOUT_RATE  = 0.10

# ============================================================
#  DO NOT EDIT BELOW THIS LINE
# ============================================================
import os, sys, time, warnings
warnings.filterwarnings("ignore")

os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TF_CPP_MIN_LOG_LEVEL"]  = "3"

import numpy  as np
import pandas as pd
import joblib

from sklearn.preprocessing  import StandardScaler
from sklearn.decomposition   import PCA
from sklearn.model_selection import train_test_split
from sklearn.metrics         import (mean_squared_error,
                                     mean_absolute_error,
                                     r2_score,
                                     median_absolute_error)
from scipy.stats import skew, kurtosis

import tensorflow as tf
from tensorflow.keras.models   import Sequential, load_model
from tensorflow.keras.layers   import Dense, Input, BatchNormalization, Dropout
from tensorflow.keras.callbacks import (Callback,
                                        ReduceLROnPlateau,
                                        EarlyStopping)

RANDOM_STATE = 42
tf.random.set_seed(RANDOM_STATE)
np.random.seed(RANDOM_STATE)

INPUT_COLS = ["Re", "TI", "AOA", "x/C", "y/C", "port angle"]

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ------------------------------------------------------------
def banner(text):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)

# ------------------------------------------------------------
def load_excel(path, sheet=0):
    if not os.path.exists(path):
        sys.exit(f"\n[ERROR]  File not found: {path}\n"
                 f"         Please update TRAIN_XLSX in the CONFIG section.\n")
    df = pd.read_excel(path, sheet_name=sheet)
    print(f"[INFO]  Loaded: {path}  —  {df.shape[0]} rows, {df.shape[1]} cols")

    missing = [c for c in INPUT_COLS if c not in df.columns]
    if missing:
        sys.exit(
            f"\n[ERROR]  These column headers are missing from your Excel:\n"
            f"         {missing}\n"
            f"         Your Excel headers (first 10): {list(df.columns[:10])}\n"
            f"         Please check Row 1 of your Excel file.\n"
        )
    return df

# ------------------------------------------------------------
def split_X_y(df):
    X       = df[INPUT_COLS].values.astype(np.float32)
    cp_cols = [c for c in df.columns if c not in INPUT_COLS]
    y       = df[cp_cols].values.astype(np.float32)
    print(f"[INFO]  Input  shape : {X.shape}   (6 features per row)")
    print(f"[INFO]  Output shape : {y.shape}   ({y.shape[1]} Cp time steps per row)")
    return X, y, cp_cols

# ------------------------------------------------------------
def metrics_table(y_true, y_pred, label):
    err = y_true - y_pred
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae  = mean_absolute_error(y_true, y_pred)
    r2   = r2_score(y_true, y_pred)
    print(f"  [{label}]  RMSE = {rmse:.5f}   MAE = {mae:.5f}   R² = {r2:.5f}")
    return {"Set": label, "RMSE": rmse, "MAE": mae, "R2": r2,
            "MedianAE": median_absolute_error(y_true, y_pred),
            "StdDev"  : float(np.std(err)),
            "Skewness": float(skew(err.flatten())),
            "Kurtosis": float(kurtosis(err.flatten()))}

# ------------------------------------------------------------
class ProgressCallback(Callback):
    LOG = 10

    def __init__(self, Xtr, Xte, ytr, yte, pca):
        super().__init__()
        self.Xtr = Xtr; self.Xte = Xte
        self.ytr = ytr; self.yte = yte
        self.pca = pca
        self.rows = []

    def on_epoch_end(self, epoch, logs=None):
        if (epoch + 1) % self.LOG:
            return
        ytr_p = self.pca.inverse_transform(self.model.predict(self.Xtr, verbose=0))
        yte_p = self.pca.inverse_transform(self.model.predict(self.Xte, verbose=0))
        rmse_tr = np.sqrt(mean_squared_error(self.ytr, ytr_p))
        rmse_te = np.sqrt(mean_squared_error(self.yte, yte_p))
        r2_tr   = r2_score(self.ytr, ytr_p)
        r2_te   = r2_score(self.yte, yte_p)
        self.rows.append({"Epoch": epoch+1,
                          "Train_RMSE": rmse_tr, "Train_R2": r2_tr,
                          "Test_RMSE" : rmse_te, "Test_R2" : r2_te})
        print(f"  Epoch {epoch+1:04d}  │  "
              f"Train RMSE {rmse_tr:.5f}  R² {r2_tr:.4f}  │  "
              f"Test  RMSE {rmse_te:.5f}  R² {r2_te:.4f}")

# ============================================================
#  TRAIN
# ============================================================
def run_train():
    banner("STEP 1 OF 2 — TRAINING THE MODEL")

    df      = load_excel(TRAIN_XLSX, SHEET_NAME)
    X, y, _ = split_X_y(df)

    # Scale inputs
    sx = StandardScaler()
    Xs = sx.fit_transform(X)

    # PCA — compress Cp from ~10 000 columns to ~20-50 modes
    print(f"\n[PCA]  Fitting PCA (keeping {int(PCA_VARIANCE*100)}% variance)...")
    pca   = PCA(n_components=PCA_VARIANCE, svd_solver="full")
    y_pca = pca.fit_transform(y)
    n_modes   = y_pca.shape[1]
    var_pct   = pca.explained_variance_ratio_.sum() * 100
    print(f"[PCA]  {y.shape[1]} Cp columns  →  {n_modes} PCA modes  "
          f"({var_pct:.3f}% variance kept)\n")

    # Train / test split
    Xtr, Xte, ytr_p, yte_p = train_test_split(
        Xs, y_pca,
        test_size=TEST_RATIO, random_state=RANDOM_STATE, shuffle=True)

    ytr_real = pca.inverse_transform(ytr_p)
    yte_real = pca.inverse_transform(yte_p)
    print(f"[INFO]  Training rows: {Xtr.shape[0]}   Validation rows: {Xte.shape[0]}")

    # Build MLP
    layers = [Input(shape=(6,))]
    for u in HIDDEN_UNITS:
        layers += [Dense(u, activation="relu"), BatchNormalization(), Dropout(DROPOUT_RATE)]
    layers.append(Dense(n_modes, activation="linear"))

    model = Sequential(layers)
    model.compile(optimizer=tf.keras.optimizers.Adam(LEARNING_RATE), loss="mse")
    model.summary()

    cb_prog   = ProgressCallback(Xtr, Xte, ytr_real, yte_real, pca)
    cb_reduce = ReduceLROnPlateau(monitor="val_loss", factor=0.5,
                                  patience=20, min_lr=1e-6, verbose=0)
    cb_stop   = EarlyStopping(monitor="val_loss", patience=50,
                               restore_best_weights=True, verbose=1)

    print("\n[Training progress — every 10 epochs]\n")
    t0 = time.time()
    model.fit(Xtr, ytr_p,
              epochs=EPOCHS, batch_size=BATCH_SIZE,
              validation_data=(Xte, yte_p),
              callbacks=[cb_prog, cb_reduce, cb_stop],
              verbose=0)
    print(f"\n[INFO]  Training finished in {time.time()-t0:.1f}s")

    # Final accuracy report
    banner("ACCURACY REPORT  (real Cp units)")
    rows = []
    rows.append(metrics_table(
        ytr_real, pca.inverse_transform(model.predict(Xtr, verbose=0)), "Train"))
    rows.append(metrics_table(
        yte_real, pca.inverse_transform(model.predict(Xte, verbose=0)), "Test "))

    # Save everything
    prog_df    = pd.DataFrame(cb_prog.rows)
    metrics_df = pd.DataFrame(rows)

    result_xlsx = os.path.join(OUTPUT_FOLDER, "training_report.xlsx")
    with pd.ExcelWriter(result_xlsx, engine="openpyxl") as w:
        prog_df.to_excel(w,    sheet_name="Training_Progress", index=False)
        metrics_df.to_excel(w, sheet_name="Final_Accuracy",    index=False)

    model.save(os.path.join(OUTPUT_FOLDER, "model.keras"))
    joblib.dump(sx,  os.path.join(OUTPUT_FOLDER, "scaler.joblib"))
    joblib.dump(pca, os.path.join(OUTPUT_FOLDER, "pca.joblib"))

    print(f"\n[SAVED]  Model      →  {OUTPUT_FOLDER}/model.keras")
    print(f"[SAVED]  Report     →  {result_xlsx}")
    print(f"\n  Run  python Cp_predictor.py --predict  to generate Cp predictions.\n")

# ============================================================
#  PREDICT
# ============================================================
def run_predict():
    banner("STEP 2 OF 2 — PREDICTING Cp")

    model_path = os.path.join(OUTPUT_FOLDER, "model.keras")
    if not os.path.exists(model_path):
        sys.exit("\n[ERROR]  No trained model found.\n"
                 "         Run  python Cp_predictor.py --train  first.\n")

    model = load_model(model_path, compile=False)
    sx    = joblib.load(os.path.join(OUTPUT_FOLDER, "scaler.joblib"))
    pca   = joblib.load(os.path.join(OUTPUT_FOLDER, "pca.joblib"))

    df     = load_excel(TRAIN_XLSX, SHEET_NAME)
    coords = (df[["x/C", "y/C", "port angle"]]
              .drop_duplicates().reset_index(drop=True))

    print(f"[INFO]  Conditions to predict : {len(PREDICT_CONDITIONS)}")
    print(f"[INFO]  Unique spatial points  : {len(coords)}")
    print(f"[INFO]  Total predictions      : "
          f"{len(PREDICT_CONDITIONS) * len(coords)}\n")

    all_rows = []   # collect summary for final Excel report

    for Re, TI, AOA in PREDICT_CONDITIONS:
        sheets = {}
        for _, row in coords.iterrows():
            xc, yc, pa = row["x/C"], row["y/C"], row["port angle"]

            X_raw    = np.array([[Re, TI, AOA, xc, yc, pa]], dtype=np.float32)
            X_scaled = sx.transform(X_raw)
            pca_pred = model.predict(X_scaled, verbose=0)
            cp_pred  = pca.inverse_transform(pca_pred).flatten()

            sheet_name = f"xC{xc:.3f}_yC{yc:.3f}_pa{pa:.0f}"[:31]  # Excel limit
            sheets[sheet_name] = pd.DataFrame({
                "time_step": np.arange(len(cp_pred)),
                "Cp"       : cp_pred,
            })

            all_rows.append({
                "Re": Re, "TI": TI, "AOA": AOA,
                "x/C": xc, "y/C": yc, "port_angle": pa,
                "Cp_mean": float(np.mean(cp_pred)),
                "Cp_min" : float(np.min(cp_pred)),
                "Cp_max" : float(np.max(cp_pred)),
                "Cp_std" : float(np.std(cp_pred)),
            })

        out_file = os.path.join(
            OUTPUT_FOLDER,
            f"Cp_Re{int(Re)}_TI{TI}_AOA{AOA}.xlsx")

        with pd.ExcelWriter(out_file, engine="openpyxl") as w:
            for sname, sdf in sheets.items():
                sdf.to_excel(w, sheet_name=sname, index=False)

        print(f"  [AOA={AOA:3.0f}°]  saved  →  {out_file}")

    # Summary Excel — all predictions, one row per condition+point
    summary_path = os.path.join(OUTPUT_FOLDER, "summary_all_predictions.xlsx")
    pd.DataFrame(all_rows).to_excel(summary_path, index=False)

    banner("DONE")
    print(f"  Results folder : {os.path.abspath(OUTPUT_FOLDER)}")
    print(f"  Summary file   : summary_all_predictions.xlsx")
    print(f"  Per-condition  : Cp_Re<...>_TI<...>_AOA<...>.xlsx\n")

# ============================================================
#  MAIN
# ============================================================
def main():
    import argparse
    p = argparse.ArgumentParser(
        description="Cp Predictor  —  PCA + MLP",
        formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--train",   action="store_true",
                   help="Train the model on your Excel data")
    p.add_argument("--predict", action="store_true",
                   help="Predict Cp for conditions in PREDICT_CONDITIONS")
    args = p.parse_args()

    if not args.train and not args.predict:
        p.print_help()
        print("\nQuick start:")
        print("  python Cp_predictor.py --train")
        print("  python Cp_predictor.py --predict\n")
        return

    if args.train:
        run_train()
    if args.predict:
        run_predict()

if __name__ == "__main__":
    main()
