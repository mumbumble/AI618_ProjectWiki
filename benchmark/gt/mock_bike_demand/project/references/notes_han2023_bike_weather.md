# Notes: Han, Oh & Yoon (2023), "Weather effects on public bike rental in Daejeon"

Status: read and summarised for the team, 2026-11-14 (Choi Ha-eun)
Used for: literature comparison in the report (Discussion section)

## 1. Research question

Han, Oh and Yoon ask how much hourly public bike rental in Daejeon depends on weather conditions. Their focus is weather only. They want to know which weather variable is the strongest predictor and whether rain has a measurable effect on how many bikes are rented.

Relevance to us: our question is similar (weather and holidays against hourly demand in Seoul), so this paper is the closest prior work we found. The main difference is that we add holidays and calendar structure.

## 2. Data

- City: Daejeon, South Korea (mid-sized city, not the capital).
- Unit: hourly rental counts with matching hourly weather.
- Size: 8,400 hourly rows covering 2021 and 2022.
- Weather variables used: temperature, humidity, wind speed, precipitation. Snow was reported separately and had little effect in their results.
- Holidays: not included. This is the main gap compared with our dataset.
- Station-level data: aggregated to the city level. No station breakdown.

Notes for us: their sample is roughly 270 times larger than the course subset we used (about 30 hourly rows). Their results are therefore more stable, but we cannot test whether their ranking of variables holds for a small sample.

## 3. Methods

- Model: gradient boosting regression. The paper compares it with a linear baseline but the detailed hyperparameters were not in the summary we read.
- Split: the paper used a held-out test set. We could not confirm whether the split was random or chronological. Check the original PDF before quoting this detail.
- Evaluation: R2 and RMSE on the test set.
- Feature importance: reported for weather variables only.

## 4. Results

- Test R2 = 0.66.
- Test RMSE = 355 rentals per hour.
- Top predictor: temperature. Higher temperature was linked to more rentals, up to a comfortable range.
- Rain: rainy hours had far lower demand. The authors estimate that rain reduces demand by about 70% compared with dry hours.
- Humidity and wind had smaller, secondary effects.

## 5. Discussion points from the paper

- Weather explains a large share of rental variation, but not all of it. The authors mention that the remaining error is probably linked to commuting patterns and calendar effects.
- Rain is the most useful single signal for planning bike redistribution, because a rainy hour can cut demand sharply.
- They suggest that operators could use weather forecasts for short-term fleet planning.

## 6. Limitations stated by the authors

- No holiday variable. The authors say this is a gap because holidays change commuting demand.
- One city only. Results may not transfer to Seoul, which is larger and has a different bike system.
- Two years of data only. Seasonal patterns from a single year are not repeated.

## 7. Comparison with our project

| Item | Han, Oh & Yoon (2023) | Our project (Seoul, DATA2201) |
|---|---|---|
| City | Daejeon | Seoul |
| Rows | 8,400 hourly (2021-2022) | About 30 hourly rows (course subset) |
| Model | Gradient boosting | Random Forest (n_estimators=200, max_depth=8) |
| Baseline | Linear model | Linear Regression |
| Test R2 | 0.66 | 0.71 (RF) vs 0.43 (linear baseline) |
| Test RMSE | 355 | 318.4 bikes (RF) vs 441.9 (linear baseline) |
| Rain effect | About 70% lower demand | Mean 214 rainy hours vs 812 dry hours, about 74% lower |
| Top predictor | Temperature | Temperature (r = 0.54 with demand); RF importance 0.34 |
| Holidays | Not included | Included: holiday mean 562 vs non-holiday 733 |

Key points for the report:

1. Our R2 of 0.71 is slightly higher than their 0.66. The two numbers are not directly comparable because the datasets, cities, and sample sizes differ, and our test set is very small.
2. Our rain reduction (about 74%) is close to their estimate (about 70%). Both studies point to rain as a strong negative factor.
3. Both studies find temperature to be the most important weather variable. Our Random Forest importance for temperature (0.34) is the largest single feature.
4. Their main limitation, the missing holiday variable, is one thing our project adds. Holidays improve the story but our holiday effect is a simple mean comparison, not a tested coefficient.

## 8. Open questions

- Check whether the paper used a time-based or random split. This affects how fair the R2 comparison is.
- Find the exact gradient boosting settings if we want a like-for-like model comparison.
- Confirm the 70% rain figure from the paper's own table, not from our summary.
