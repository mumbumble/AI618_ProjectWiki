# Reading notes: Cho & Baek (2024)

**Paper:** Explanations in AI Code Suggestions: Effects on Reliance
**Authors:** Cho Hyun-woo and Baek Seo-yeon (2024)
**Read by:** Han Ji-woo, for the background section of our study proposal
**Status:** Personal reading notes, not yet discussed with Prof. Seo

---

## Core question

Does the amount of explanation attached to an AI code suggestion change how much developers rely on it, including when the suggestion is wrong?

## Design

- Between-subjects: each developer saw one explanation condition only.
- 36 developers in total. If split evenly, that is about 12 per condition.
- Conditions: no explanation, short explanation, long explanation.
- Tasks: code suggestion review with a mix of correct and incorrect AI suggestions.
- Measures: acceptance of suggestions (correct and incorrect), review time, self-reported trust.

## Main findings

- Long explanations raised acceptance of wrong suggestions by 17%.
- Long explanations also increased review time by 22%.
- The authors read this as developers treating a long justification as evidence of correctness. Length made suggestions look more credible without making them more accurate.
- The short-explanation condition did not show the same pattern. I need to recheck the exact comparison before citing it in the proposal.

## What the paper did not test

- No evidence-linked explanation. Explanations were prose only. Nothing pointed to specific code lines or walked through execution.
- No within-subjects comparison, so differences could partly reflect individual differences in trust.
- Review accuracy was not the main outcome. They focused on acceptance of suggestions.
- Only one code-review setting was used. It is unclear how well the effect carries over to other kinds of defects.

## How this shapes our proposal

- **Main gap:** their explanations were all prose. Our trace condition adds highlighted code lines and a step-by-step execution trace that points to the defect.
- **Calibration concern:** their long-explanation result suggests richer text may inflate acceptance of wrong suggestions. We want to check whether richer evidence raises trust *and* review accuracy, rather than only raising acceptance.
- **Design change:** a within-subjects design lets each developer compare all three styles, which reduces between-person noise. The cost is order effects, so we counterbalance condition order across the six permutations of three conditions.
- **Terminology:** the paper says "reliance." We use "trust" for the survey attitude measure and "review accuracy" for the behavioral measure.
- **Our terse condition** is a one-line verdict with no reasoning. It is not the same as their short-explanation condition, so the two should not be compared directly.

## Hypotheses carried over

- **H1:** Trust rises with explanation richness (trace > rationale > terse), measured by the trust composite (mean of Q1-Q3).
- **H2:** The trace condition yields higher review accuracy than the terse condition, measured as fewer errors per task.
- Review accuracy = 1 - errors/3, since each PR has three seeded defects.

## Open questions

- Do the word counts of their long explanations match our rationale paragraphs? We need this before claiming the conditions are comparable.
- Was their review time measured per task or per session?
- Can we get the explanation materials from the authors so we can reuse the wording?
- Would seeded-defect PRs produce the same effect as real code review? This goes in the limitations section.
