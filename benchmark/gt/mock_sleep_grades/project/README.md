# SleepWork-Grade

Team project for **STAT2101 Introduction to Data Analysis**, Fall 2026, Hanbit University.
Instructor: Prof. Yoon Seong-min (윤성민). TA: Jung Da-eun (정다은).

## Research question

Do weeknight sleep duration and weekly part-time work hours predict the final STAT2101 grade?

## Data

The data come from an online survey of STAT2101 students, open from 2026-09-21 to 2026-10-02.
The raw export has 32 rows (student_id S001 to S032). After cleaning, **28 rows** remain.
**4 rows were dropped**:

- S014 appeared twice (duplicate removed)
- S027 reported 25 hours of sleep (out of the valid 3-12 range)
- S022 has no course grade
- S030 has "abc" as the course grade

Values that were repaired rather than dropped:

- S003 sleep "7h" was read as 7.0 hours
- S017 sleep "six and half" was read as 6.5 hours
- S005 missing work_hours was imputed with the median (10.0)
- S011 study_hours "N/A" was imputed with the median (8.0)

Columns (same in raw and clean data):

| column | meaning |
|---|---|
| student_id | S001 to S032 |
| gender | F / M |
| year | academic year, 1-4 |
| sleep_hours | average weeknight sleep (hours, valid 3-12) |
| work_hours | part-time work hours per week (valid 0-40) |
| study_hours | self-study hours per week (valid 0-30) |
| caffeine_cups | cups of coffee/tea per day (0-8) |
| course_grade | final STAT2101 score (0-100) |

## Method

1. Descriptive statistics and Pearson correlations with `course_grade`.
2. Ordinary least squares linear regression (scikit-learn `LinearRegression`) with
   `sleep_hours`, `work_hours` and `study_hours` as predictors.
3. Evaluation by leave-one-out cross-validation (LOO-CV), reporting RMSE and R2.
   Random seed is 2026.

Headline numbers (clean data, n = 28):

- Correlation with grade: sleep_hours r = 0.46, work_hours r = -0.38, study_hours r = 0.44
- LOO-CV RMSE = 6.42, R2 = 0.41 (mean-only baseline RMSE = 9.97)

## Repository layout

```
README.md          this file
data/              raw survey export and cleaned dataset
src/               cleaning script and feature functions
notebooks/         exploratory analysis and model notebooks
report/            final_report.md and report/figures/
```

## How to reproduce

Requires Python 3.11.

```bash
git clone <repo-url> SleepWork-Grade
cd SleepWork-Grade
pip install pandas numpy scikit-learn matplotlib jupyter
python src/clean_data.py
jupyter notebook notebooks/
```

Then:

1. Run the EDA notebook first. It prints `describe()` and the correlation matrix and saves the scatter figure to `report/figures/`.
2. Run the modelling notebook second. It fits the linear model, runs LOO-CV, and saves the predicted-vs-actual figure.
3. Read `report/final_report.md`. It uses the figures from `report/figures/`.

`python src/clean_data.py` reads the raw survey file in `data/` and writes the cleaned dataset back to `data/`.
Run all cells from top to bottom so that the seed (2026) is applied.

## Team

- Kim Min-jun (김민준): team lead, data cleaning
- Lee Seo-yeon (이서연): feature engineering in `src/`
- Park Ji-ho (박지호): EDA notebook and figures
- Choi Yuna (최유나): final report

## Deadline

Submission via LMS by **2026-12-05 23:59**, as a zip of this repository.

## Limitations

The sample is small (n = 28, one course), sleep is self-reported, and the analysis shows
association rather than causation. Two values were median-imputed and the model has no
interaction terms. See Section 6 of the report for details.
