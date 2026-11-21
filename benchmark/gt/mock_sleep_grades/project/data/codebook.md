# Codebook: Raw Student Sleep Survey 2026

**File:** `data/raw_student_sleep_survey_2026.csv`
**Source:** Online survey of STAT2101 students, Hanbit University, Fall 2026
**Collection window:** 2026-09-21 to 2026-10-02
**Rows:** 32 respondent rows plus one header row
**Unit of observation:** one student per row, identified by `student_id`
**Format:** UTF-8, comma-separated, header in the first line. Missing or unparseable entries are kept as they were typed, so some numeric columns contain text.

## Columns

| Column | Type | Valid values | Description |
|---|---|---|---|
| student_id | text | S001 to S032 | Anonymous respondent ID assigned when the survey closed |
| gender | categorical | F, M | Self-reported gender |
| year | integer | 1 to 4 | Academic year (1 = first year, 4 = fourth year) |
| sleep_hours | numeric | 3 to 12 | Average weeknight sleep, in hours. Some answers were typed as text (for example "7h" or "six and half") |
| work_hours | numeric | 0 to 40 | Part-time work, in hours per week |
| study_hours | numeric | 0 to 30 | Self-study outside class, in hours per week |
| caffeine_cups | numeric | 0 to 8 | Average caffeinated drinks per day. Collected but not used in the final model |
| course_grade | numeric | 0 to 100 | Final STAT2101 score |

The outcome of interest is `course_grade`. The main predictors are `sleep_hours` and `work_hours`, with `study_hours` as a control.

## Known Problems in the Raw File

| Student | Column | Raw value | Handling in cleaning |
|---|---|---|---|
| S003 | sleep_hours | "7h" | Converted to 7.0 |
| S017 | sleep_hours | "six and half" | Converted to 6.5 |
| S005 | work_hours | missing | Imputed with the median (10.0) |
| S011 | study_hours | "N/A" | Imputed with the median (8.0) |
| S014 | (whole row) | appears twice | One copy dropped as a duplicate |
| S022 | course_grade | missing | Row dropped |
| S027 | sleep_hours | 25 | Row dropped (outside valid range 3 to 12) |
| S030 | course_grade | "abc" | Row dropped |

## Cleaning Summary

- Raw rows: 32
- Rows dropped: 4 (1 duplicate, 3 invalid)
- Clean rows: 28
- Values imputed by median: 2 (S005 work_hours, S011 study_hours)

Median imputation was used only for two cells, so the conclusions should be read with that in mind (see the Limitations section of the report).

## Cleaned Version

The cleaned dataset has the same eight columns, with the same names and meanings described above. Its numeric columns have the correct types, it has no missing values, and it contains 28 rows. Everything in this codebook applies to the cleaned data as well.

## Notes for Users

- `student_id` is an identifier and should not be used as a predictor.
- Values are self-reported. Sleep and work hours are estimates from memory, not logged measurements.
- The survey covers one course in one term. Results should not be generalized to other students without further data.
- Derived variables (for example, a work-heavy flag or a sleep-deficit score) are not stored in this file. They are computed in the analysis code from the columns above.
