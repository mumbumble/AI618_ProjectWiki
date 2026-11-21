# Codebook: Seoul Bike-Sharing Raw Data (seoul_bike_2025)

Project: Rides & Rain, DATA2201 Data Analysis, Hanbit University, Fall 2026
Team: Kim Min-jun, Lee Seo-yeon, Park Do-hyun, Choi Ha-eun
Instructor: Prof. Seo Jung-min. TA: Moon Ji-woo.

This codebook describes every column in the raw file `data/raw_seoul_bike_2025.csv`. The raw file is kept as delivered. All fixes happen in the cleaning step, and the cleaned data keeps the same documented columns with fixed types and no missing values.

## File summary

- File: `data/raw_seoul_bike_2025.csv`
- Format: comma-separated, UTF-8, header row included
- Columns: 10, in the order listed below
- Unit of observation: one row per hour (system-wide counts, no station-level detail)
- Target variable: `rented_bikes`
- Time coverage: hourly rows from the course subset (about 30 hours)

## Columns

| # | Column | Raw type | Unit | Allowed values / range | Description |
|---|---|---|---|---|---|
| 1 | datetime | text | timestamp | `YYYY-MM-DD HH:MM:SS` | Date and time of the hour the row describes |
| 2 | rented_bikes | integer (some values stored as text) | bikes per hour | 0 or more | Number of bikes rented in that hour. This is the target variable |
| 3 | hour | integer | hour of day | 0 to 23 | Hour of day, taken from the timestamp |
| 4 | temp_c | float | degrees Celsius | realistic air temperature | Air temperature in that hour |
| 5 | humidity_pct | float | percent | 0 to 100 | Relative humidity in that hour |
| 6 | wind_ms | float | metres per second | 0 or more | Mean wind speed in that hour |
| 7 | rain_mm | float | millimetres | 0 or more | Rainfall during the hour. Zero means a dry hour |
| 8 | snow_cm | float | centimetres | 0 or more | Snowfall during the hour |
| 9 | season | text (category) | category | Winter, Spring, Summer, Autumn | Season of the year |
| 10 | holiday | text (category) | category | Holiday, No Holiday | Whether the day is a public holiday |

## Known issues in the raw file

The raw file has the following problems. Each one is handled in the cleaning step.

- `temp_c` is missing in 2 rows.
- `humidity_pct` is missing in 1 row.
- `rented_bikes` is written as text in 2 rows. Some values contain a thousands comma (for example "1,204"), and 2 rows contain "n/a".
- `holiday` is misspelled in 2 rows ("no holiday" or "Holliday").
- One row has `hour` = 24, which is outside the valid range of 0 to 23.

## How each issue is handled

- **rented_bikes text values:** commas are stripped and the value is cast to an integer. Rows whose count is "n/a" have no usable target value, so they are dropped.
- **Missing temp_c and humidity_pct:** filled with the median of the same season. Rows are not dropped for these gaps.
- **holiday labels:** normalized to exactly `Holiday` or `No Holiday`.
- **hour outside 0 to 23:** the row is dropped.
- **datetime:** parsed into a proper timestamp.
- **Duplicates:** removed.

## Cleaned data

The cleaned data has the same 10 columns, with the same names and meanings as above. Types are fixed: `datetime` is a timestamp, `rented_bikes` and `hour` are integers, and the weather columns are floats. The cleaned data has no missing values and contains 20 to 35 rows.

## Notes for users

- Derived features (cyclic hour encoding, rain flag, season one-hot columns, and similar) are not stored in the raw file. They are built later in the analysis from the columns above.
- The data is a small course subset. Results should be read as a demonstration of the method, not as a estimate of citywide demand.
- Station-level data and air quality measurements are not included.
