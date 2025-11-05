#!/usr/bin/env python3
"""
Run a trained sklearn/Joblib pipeline on a CSV input and save predictions.

Example:
    python "run_model.py" --input "data_test_example.csv" --output "prediction_result.csv"

-------------------------------------------------------------------------------

EXPECTED RAW COLUMNS IN THE INPUT CSV (verbatim header strings)

Required (exact letter, space, and capital):
- "Gender"
- "Age"
- "Height"
- "Weight"
- "BMI"
- "Systolic"
- "Diastolic"
- "Smoker"
- "Hemoglobin"
- "Random Blood Glucose"
- "SGOT"
- "SGPT"
- "Alkaline Phosphatase"
- "SIN"
- "Subject Initials"
"""

import argparse
from pathlib import Path
import sys
import pandas as pd
import joblib

# Column mapping (raw -> model feature)
COLMAP = {
    "Gender": "gender",
    "Age": "age_recruitment",
    "Height": "height",
    "Weight": "weight",
    "BMI": "bmi",
    "Systolic": "systolic",
    "Diastolic": "diastolic",
    "Smoker": "smoking_per_day",
    "Hemoglobin": "hemoglobin",
    "Random Blood Glucose": "random_blood_glucose",
    "SGOT": "sgot",
    "SGPT": "sgpt",
    "Alkaline Phosphatase": "alp",
}

AUX_COLS = ["SIN", "Subject Initials"]  # carried through if present

# Map numeric classes to human-readable labels
CLASS_LABELS = {0: "low", 1: "normal", 2: "high"}


def coalesce_duplicate_targets(df: pd.DataFrame) -> pd.DataFrame:
    """
    If multiple source columns map to the same COLMAP target, coalesce them by first non-null.
    Implemented via transpose-groupby-backfill trick to preserve order.
    """
    df2 = (
        df.T
        .groupby(level=0, sort=False)
        .apply(lambda g: g.bfill().iloc[0])
        .T
    )
    return df2


def build_filtered_frame(df_raw: pd.DataFrame) -> pd.DataFrame:
    # 1) Rename columns
    df = df_raw.rename(columns=COLMAP)

    # 2) Coalesce duplicates that now share the same target name
    df = coalesce_duplicate_targets(df)

    # 3) Keep only mapped columns (create missing as NaN) in COLMAP order
    target_cols = list(dict.fromkeys(COLMAP.values()))  # preserve order and drop dups
    df = df.reindex(columns=target_cols)
    return df


def load_pipeline(model_path: Path):
    """Load either a bare sklearn Pipeline or a bundle dict with {'pipeline': pipe, ...}"""
    obj = joblib.load(model_path)
    if isinstance(obj, dict) and "pipeline" in obj:
        return obj["pipeline"]
    return obj


def main():
    parser = argparse.ArgumentParser(description="Run a joblib sklearn pipeline on CSV input.")
    parser.add_argument("--input", required=True, help="Path to input CSV (raw, unmapped headers are OK).")
    parser.add_argument("--output", required=True, help="Path to output CSV for predictions.")
    parser.add_argument(
        "--model",
        default="model_logreg.joblib",
        help="Path to joblib model/pipeline. Default: model_logreg.joblib",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    model_path = Path(args.model)

    if not input_path.exists():
        print(f"[error] Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)
    if not model_path.exists():
        print(f"[error] Model file not found: {model_path}", file=sys.stderr)
        sys.exit(1)

    # Load data & model
    df_raw = pd.read_csv(input_path)
    pipe = load_pipeline(model_path)

    # Prepare features
    df_features = build_filtered_frame(df_raw)

    # Ensure model feature alignment (create any missing columns the model expects)
    if hasattr(pipe, "feature_names_in_"):
        expected = list(pipe.feature_names_in_)
        for col in expected:
            if col not in df_features.columns:
                df_features[col] = pd.NA
        df_features = df_features.reindex(columns=expected)
    else:
        expected = list(df_features.columns)

    # Predict numeric classes (0/1/2)
    numeric_preds = pipe.predict(df_features)

    # Map numeric classes to text labels using the model's own class ordering (robust)
    try:
        model = pipe.named_steps.get("model", None)
        if hasattr(model, "classes_"):
            mapping = {int(k): CLASS_LABELS.get(int(k), str(k)) for k in model.classes_}
        else:
            # Fallback to default mapping 0/1/2 -> low/normal/high
            mapping = CLASS_LABELS
    except Exception:
        mapping = CLASS_LABELS

    pred_labels = pd.Series([mapping.get(int(c), str(c)) for c in numeric_preds], name="prediction")

    # Carry through AUX_COLS if present (otherwise skip gracefully)
    carry_cols = [c for c in AUX_COLS if c in df_raw.columns]
    if carry_cols:
        result = pd.concat([df_raw[carry_cols].reset_index(drop=True), pred_labels.reset_index(drop=True)], axis=1)
    else:
        result = pred_labels.to_frame()

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)

    # Minimal stdout status
    print(f"[ok] Wrote predictions to: {output_path}")
    if carry_cols:
        print(f"[info] Included columns: {', '.join(carry_cols)}")
    print(f"[info] Feature columns used ({len(expected)}): {', '.join(map(str, expected))}")


if __name__ == "__main__":
    main()
