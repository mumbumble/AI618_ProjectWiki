# Rides & Rain

Hourly bike-sharing demand in Seoul compared against weather and holidays.
Course project for DATA2201 Data Analysis, Hanbit University, Fall 2026.

Instructor: Prof. Seo Jung-min
TA: Moon Ji-woo

## Research question

How much of hourly bike-sharing demand in Seoul is explained by weather and holidays, and which factors matter most?

## Team

| Member | Role |
|---|---|
| Kim Min-jun | Team lead, report writing |
| Lee Seo-yeon | Data cleaning |
| Park Do-hyun | Feature engineering |
| Choi Ha-eun | EDA and figures |

## Data

Dataset slug: `seoul_bike_2025`. The raw file in `data/` has 10 columns, in this order:

`datetime, rented_bikes, hour, temp_c, humidity_pct, wind_ms, rain_mm, snow_cm, season, holiday`

- `rented_bikes` is the target: bikes rented in that hour.
- `temp_c` is in Celsius, `humidity_pct` is 0-100, `wind_ms` is m/s, `rain_mm` and `snow_cm` are the amount in that hour.
- `season` is one of Winter, Spring, Summer, Autumn. `holiday` is Holiday or No Holiday.

The raw data has known problems: `temp_c` is missing in 2 rows, `humidity_pct` in 1 row, `rented_bikes` is stored as text (for example "1,204" or "n/a") in 2 rows, `holiday` is misspelled ("no holiday", "Holliday") in 2 rows, and one row has `hour` = 24.

## Cleaning rules

The cleaning script is `src/clean_data.py`. It applies these rules:

1. Strip commas from `rented_bikes` and cast it to integer.
2. Fill missing `temp_c` and `humidity_pct` with the median of the same season. Rows are not dropped for missing values.
3. Normalize the holiday labels to `Holiday` and `No Holiday`.
4. Drop rows where `hour` is outside 0-23.
5. Parse `datetime` as `YYYY-MM-DD HH:MM:SS`.
6. Drop duplicate rows.

The output is the clean file in `data/`, with 20-35 rows and the same 10 columns.

## Methods

Feature functions live in `src/`:

- `add_time_features(df)`: cyclic hour encoding (`hour_sin`, `hour_cos`) and `is_weekend`.
- `add_weather_features(df)`: `temp_humidity` (temp times humidity) and `is_rainy` (rain above 0 mm).
- `encode_season(df)`: one-hot season columns.
- `build_feature_matrix(df)`: returns `X, y`.

Modelling:

- Split: 80/20 train/test, `random_state=42`, on the clean data.
- Main model: Random Forest Regressor (`n_estimators=200`, `max_depth=8`, `random_state=42`).
- Baseline: Linear Regression.
- Metrics on the held-out test set: RMSE, MAE, R2.

## Results

| Model | RMSE (bikes) | R2 | MAE (bikes) |
|---|---|---|---|
| Random Forest | 318.4 | 0.71 | 224.6 |
| Linear Regression (baseline) | 441.9 | 0.43 | not reported |

Top Random Forest feature importances: `temp_c` 0.34, `hour_sin` 0.21, `hour_cos` 0.14, `humidity_pct` 0.09, `rain_mm` 0.07, `is_rainy` 0.05, others 0.10.

Descriptive findings: mean demand is 214 bikes in rainy hours versus 812 in dry hours. Holiday mean is 562 versus 733 on non-holidays. Summer averages 1,020 and Winter 305. The Pearson correlation between `temp_c` and `rented_bikes` is 0.54.

Comparison with Han, Oh & Yoon (2023), a bike-rental study in Daejeon: they reported R2 = 0.66 and RMSE = 355 with gradient boosting, and a rain effect of about a 70% reduction in demand. Our Random Forest gives R2 = 0.71. Our rainy-hour drop (214 versus 812) is about 74%, which is similar to their estimate.

Figures are saved in `report/figures/`.

## Limitations

- The course subset has only about 30 hourly rows, so results are unstable.
- The train/test split is random, not chronological.
- There is no bike-station-level data.
- Air quality is not included.

## How to reproduce

1. Use Python 3.11.
2. Install the dependencies: `pip install -r requirements.txt` (pandas 2.1, scikit-learn 1.4, matplotlib 3.8).
3. Clean the data: `python src/clean_data.py`.
4. Run the two notebooks in order: first the EDA notebook, then the modelling notebook.
5. The written report is `report/final_report.md`.

## Deliverables and dates

- Deliverables: report, code, clean data, and this README.
- Draft report for TA review: 2026-11-27.
- Final submission via LMS: 2026-12-11, 23:59.
