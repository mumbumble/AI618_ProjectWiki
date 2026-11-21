# CodeSibling (codesibling2022): reading notes

Key: `codesibling2022`
Full cite: Yoon et al., 2022. Competing approach. We use it as a baseline row in the main results table.
Last updated: 2026-11-21

## One-paragraph summary

CodeSibling retrieves sibling functions for a query Java function from the same file or the same package. Retrieval uses BM25 over tokenized code. The top-3 siblings are then concatenated with their raw code to the query body, and the combined input goes to a standard encoder-decoder. There is no learned fusion step, no retrieval loss, and no explicit control for leakage between the query and the index. The core idea is close to ours: nearby functions in the same codebase carry useful naming and idiom information. The difference is how the neighbors are found and how they are used.

## How the method works (as far as the paper describes it)

- Sibling pool: functions in the same file or package as the query. This is narrower than the whole repository.
- Scoring: BM25 on code tokens. Purely lexical, no encoder involved in retrieval.
- Selection: top-3 by BM25 score.
- Input construction: query body first, then sibling code, joined as one sequence. The input is truncated to 512 tokens.
- Model: a plain Transformer encoder-decoder. Siblings are not encoded separately and their summaries are not used.

## What it does not do

- No learned fusion. Sibling information enters only through the raw token sequence, so the model has to learn to ignore noisy siblings on its own.
- No retrieval loss. The retriever is fixed and never sees the summarization objective.
- No summaries of siblings. Only their code is used. This means the decoder never sees what the neighbors were documented as, which is the signal RetroSum and RepoSum rely on.
- No leakage control. The paper notes that duplicates of the query can show up in the retrieved set.

## Failure noted in the paper

The duplicate-leak problem is the one to watch. If the query function (or an exact copy of it in another file of the repo) is in the index, BM25 ranks it first and the decoder sees the answer. This inflates scores on dev without helping on test. We hit the same class of bug ourselves in an early version of our own retriever (the query was in its own index, dev BLEU looked far too high). We fixed it with self-exclusion and commit-time filtering. Any fair comparison with CodeSibling should check that the baseline also excludes the query and later commits. We have not verified this for the number we report, so this is a to-do item before submission.

## Numbers as we report them

Main results (BLEU-4, 0-100, corpus-level, 95% bootstrap CI):

| Method      | intra_repo          | cross_repo          |
|-------------|---------------------|---------------------|
| Transformer | 20.4 [20.0, 20.8]   | 18.2 [17.7, 18.7]   |
| RetroSum    | 22.6 [22.2, 23.0]   | 20.1 [19.6, 20.6]   |
| CodeSibling | 23.7 [23.3, 24.1]   | 20.9 [20.4, 21.4]   |
| RepoSum     | 26.1 [25.7, 26.5]   | 22.4 [21.9, 22.9]   |

CodeSibling is the strongest baseline on intra_repo, so the RepoSum gain of +2.4 is measured against it. On cross_repo the gap is +1.5.

Draft v1 had CodeSibling at 23.5 (intra_repo) and 20.8 (cross_repo). The v2 numbers above are the ones to cite. Make sure the figure and text do not mix the two.

## Sweep over number of retrieved functions (k)

Intra_repo BLEU-4 for CodeSibling, k in {0, 1, 2, 4, 8, 16}:

20.4, 22.5, 23.4, 23.7, 23.2, 22.6

The original paper uses top-3. Our sweep peaks at k=4, and the main table uses k=4 so that the budget matches RepoSum. We should say this explicitly in the experiments section so reviewers do not think we tuned the baseline less than RepoSum. At k=0 it equals the Transformer, as expected.

Shape: CodeSibling peaks at k=4 like RepoSum, but it falls faster after that (23.2 at k=8, 22.6 at k=16). Concatenating many raw sibling bodies fills the 512-token window with code the decoder has to filter out. RepoSum's gated fusion degrades more slowly (26.0 and 25.6 at k=8 and k=16).

## Relation to RetroSum

Both are retrieval-augmented summarizers. The differences that matter for us:

- RetroSum retrieves from a global multi-project corpus. CodeSibling restricts to the local file or package. We restrict to the repository. This is the middle ground we argue for.
- RetroSum concatenates retrieved summaries. CodeSibling concatenates retrieved code. Neither learns how to weight neighbors.
- RetroSum uses a frozen retriever. CodeSibling uses a frozen BM25 retriever. RepoSum trains the retriever jointly with L_ret.

## Points for the paper

- Position CodeSibling as the closest baseline in scope (local, same codebase) but with no learned component on either side of the retrieval.
- The argument for repo scope against RetroSum applies to CodeSibling too, but CodeSibling is already repo-adjacent. Our claim should be about repo-wide candidates plus learned weighting, not about locality alone.
- Mention the 512-token truncation. RepoSum caps the source at 400 tokens, and the siblings are encoded separately, so the comparison is not perfectly matched. Say so in the limitations.
- Do not claim CodeSibling is "broken." It is a reasonable, simple baseline that is hard to beat without learned fusion.

## Open questions

- Did the CodeSibling runs exclude the query and later commits? If not, the baseline number is inflated and the gap may be larger or smaller than reported. Needs a check with the data split owner.
- Is BM25 run on identifiers split by camelCase and snake_case, or on raw tokens? This changes recall a lot in Java code and should be stated.
- Should we add a CodeSibling variant that uses sibling summaries too? That would separate the effect of the summary signal from the effect of learned fusion.
- Cross-repo: CodeSibling's package-local pool is small for many repos. Check how often the pool has fewer than 3 functions, and report it if it matters.

## Quick checklist before the draft goes out

- [ ] Baseline row in the main table uses the numbers above.
- [ ] Leakage check on the CodeSibling index is documented.
- [ ] k=4 choice for the baseline is stated in the experiments section.
- [ ] Figure caption for the k sweep lists CodeSibling values in the same order as the other series.
- [ ] Related work paragraph contrasts scope (file/package vs. repo vs. global) and learned vs. fixed fusion.
- [ ] Limitations mention the 512-token truncation and the BM25 tokenization choice.
