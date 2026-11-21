"""Feature engineering for the SleepWork-Grade project.

Owner: Lee Seo-yeon (feature engineering).

Team decisions from the 2026-11-03 meeting that shape this module:
- Plain linear regression only (no tree models, the sample is small).
- The final model uses sleep_hours, work_hours and study_hours.
- sleep_deficit and work_heavy are kept as helper columns for exploration,
  but they are NOT in the model matrix. Adding them made the leave-one-out
  CV results worse, so build_feature_matrix() leaves them out.

Usage (from the modeling notebook):
    from features import add_sleep_deficit, add_work_heavy, build_feature_matrix
"""

FEATURE_COLUMNS = ["sleep_hours", "work_hours", "study_hours"]
TARGET_COLUMN = "course_grade"


def add_sleep_deficit(df, threshold=7.0):
    """Add sleep_deficit = max(0, threshold - sleep_hours).

    Students who sleep at or above the threshold get 0.
    """
    out = df.copy()
    out["sleep_deficit"] = out["sleep_hours"].apply(
        lambda h: max(0.0, threshold - h)
    )
    return out


def add_work_heavy(df, cutoff=15):
    """Add work_heavy = 1 if work_hours >= cutoff, else 0.

    The default cutoff of 15 h/week is the group used in the EDA figure.
    """
    out = df.copy()
    out["work_heavy"] = (out["work_hours"] >= cutoff).astype(int)
    return out


def check_required_columns(df):
    """Raise a clear error if the cleaned data is missing a needed column."""
    required = FEATURE_COLUMNS + [TARGET_COLUMN]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns for modeling: {missing}")


def build_feature_matrix(df):
    """Return (X, y) for the linear model.

    X has sleep_hours, work_hours, study_hours.
    y is course_grade.
    """
    check_required_columns(df)
    X = df[FEATURE_COLUMNS].copy()
    y = df[TARGET_COLUMN].copy()
    if X.isnull().any().any() or y.isnull().any():
        raise ValueError("Feature matrix still has missing values; run the cleaning step first.")
    return X, y


if __name__ == "__main__":
    # Quick self-check on the cleaned file. Run from the repo root.
    # This block is only for a manual check; the notebooks import the functions.
    print("Feature columns:", FEATURE_COLUMNS)
    print("Target column:", TARGET_COLUMN)
