"""Feature engineering for the Rides & Rain project (DATA2201, Fall 2026).

Owner: Park Do-hyun.
Team decisions (Nov 6 meeting): cyclic hour encoding, rain flag, season one-hot.
Input is the cleaned hourly table (same 10 columns as the raw data, after cleaning).
"""
import numpy as np
import pandas as pd

TARGET = "rented_bikes"
SEASONS = ["Winter", "Spring", "Summer", "Autumn"]
FEATURE_COLUMNS = [
    "temp_c",
    "humidity_pct",
    "wind_ms",
    "rain_mm",
    "snow_cm",
    "hour_sin",
    "hour_cos",
    "is_weekend",
    "temp_humidity",
    "is_rainy",
    "is_holiday",
] + [f"season_{s}" for s in SEASONS]


def add_time_features(df):
    """Add cyclic hour encoding and a weekend flag.

    hour_sin / hour_cos put hour 23 next to hour 0 instead of treating
    them as far apart integers.
    """
    out = df.copy()
    out["datetime"] = pd.to_datetime(out["datetime"])
    out["hour_sin"] = np.sin(2 * np.pi * out["hour"] / 24)
    out["hour_cos"] = np.cos(2 * np.pi * out["hour"] / 24)
    out["is_weekend"] = (out["datetime"].dt.dayofweek >= 5).astype(int)
    return out


def add_weather_features(df):
    """Add the temperature x humidity interaction and the rain flag."""
    out = df.copy()
    out["temp_humidity"] = out["temp_c"] * out["humidity_pct"] / 100
    out["is_rainy"] = (out["rain_mm"] > 0).astype(int)
    return out


def encode_season(df):
    """One-hot encode the season column into season_<name> columns."""
    out = df.copy()
    for season in SEASONS:
        out[f"season_{season}"] = (out["season"] == season).astype(int)
    return out


def add_holiday_flag(df):
    """Turn the holiday label into a 0/1 column (1 = Holiday)."""
    out = df.copy()
    out["is_holiday"] = (out["holiday"] == "Holiday").astype(int)
    return out


def build_feature_matrix(df):
    """Return (X, y) for the regression models.

    X holds the FEATURE_COLUMNS in a fixed order so that the Random Forest
    and the linear baseline see identical inputs.
    y is the hourly rented_bikes count.
    """
    out = add_time_features(df)
    out = add_weather_features(out)
    out = encode_season(out)
    out = add_holiday_flag(out)

    missing = [c for c in FEATURE_COLUMNS if c not in out.columns]
    if missing:
        raise ValueError(f"Missing feature columns: {missing}")

    X = out[FEATURE_COLUMNS].astype(float)
    y = out[TARGET].astype(float)
    return X, y
