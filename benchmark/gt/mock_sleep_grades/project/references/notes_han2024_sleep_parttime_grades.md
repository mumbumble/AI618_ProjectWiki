# Reading notes: Han and Oh (2024)

**Full citation:** Han, Ji-woo and Oh, Sun-young (2024). "Sleep and Part-time Work among University Students and Their Grades."

**Why we read it:** It asks the same question as our STAT2101 project: whether sleep duration and part-time work hours relate to course grades among university students. We use it as the prior study for the comparison section of the final report.

## Study at a glance

- Sample: n = 412 undergraduates from 3 universities.
- Design: cross-sectional survey, one time point.
- Sleep: self-reported average weeknight sleep duration.
- Work: self-reported part-time work hours per week.
- Outcome: grade, GPA-scaled.
- Model: linear regression.

## Research question in their words

Do sleep duration and part-time work hours go together with academic performance in a large, multi-campus sample? The authors frame part-time work as a competing demand on time, and sleep as the recovery resource that work may erode.

## Data and measures

The survey asked about sleep on a typical weeknight and about hours worked per week in a paid job. Grades were collected as GPA and rescaled to a common scale so that students from the three universities could be pooled. Because everything came from one questionnaire, sleep and work hours are both self-reported and may be shaded by recall or social desirability.

## Methods

- Pearson correlations between sleep, work and grade.
- A linear regression of grade on sleep and work hours, with a single fit on the full sample.
- Comparison of mean grades between students who worked over 15 hours per week and those who did not.
- No cross-validation was reported. Fit quality is given as in-sample R2.

## Key findings

- Sleep and grade: r = 0.31, a weak to moderate positive association.
- Working over 15 hours per week was linked to a grade about 3.2 points lower on the GPA-scaled grade.
- The linear model reached R2 = 0.18.
- The direction of both effects matches the expected pattern: more sleep goes with higher grades, and heavier work goes with lower grades.

## Discussion points from the authors

- Heavy part-time work seems to squeeze out sleep, and the two effects may overlap rather than add up. The authors did not fit interaction terms.
- Effects were similar across the three universities, which the authors read as some evidence of generalisability within the country.
- They suggest universities consider work-hour guidance for first-year students.

## Limitations stated by the authors

- Cross-sectional design, so no causal direction can be inferred.
- Self-reported sleep and work hours.
- Grade scale harmonised across campuses, which may hide differences in grading practice.
- The authors did not report a validation split or out-of-sample error.

## Comparison notes for our project

- Our sleep-grade correlation is r = 0.46 (n = 28). That is stronger than their r = 0.31, but with only 28 students the 95% CI is wide, roughly 0.10 to 0.71. The two estimates are compatible with each other.
- Both studies find the same direction for sleep and for work hours. Our work-hours correlation is r = -0.38.
- Their linear model explains R2 = 0.18 in-sample. Our model reaches R2 = 0.41 under leave-one-out cross-validation, which is a stricter test, so the two R2 values should not be read as a direct ranking.
- Their 15-hour threshold for heavy work is the same cutoff we use for the work_heavy indicator. Our heavy-work group (9 of 28 students) has a mean grade of 69.1 against 76.9 for the others.
- Their study is far larger and covers three campuses. Ours covers one course at one university, so their results are the better guide to the wider population.
- Both studies rely on self-reported sleep, so the same measurement caveat applies to both.

## Open questions

- Would the sleep effect survive adjustment for study hours? Our model suggests it does, but the prior study did not include study time.
- Does the 15-hour threshold matter more than total work hours? We have not tested this with enough data.
