# Reading notes: RetroSum (Oh and Baek, 2021)

Status: read in full, notes for the related work section and the method section of draft v2.
Key takeaway: RetroSum showed that retrieved summaries help a Transformer summarizer. Its retriever is global and frozen, and it fuses neighbors by plain concatenation. RepoSum keeps the retrieve-then-generate idea and changes those three choices.

## Problem setting

- Input: a function body. Output: a one-sentence summary (docstring first sentence).
- Base model: a Transformer encoder-decoder with no retrieval. This is the "Transformer" row in our tables.

## Retrieval setup

- Corpus: about 2.1M functions drawn from many projects (a single global corpus).
- Retriever: frozen hybrid of BM25 and an embedding similarity score. "Frozen" means it is never updated by the summarization loss.
- For each query, the top-5 neighbors are retrieved and their summaries are concatenated to the encoder input as plain text.
- Training and test queries both use the same global index.

## Reported results

- +2.2 BLEU over their Transformer baseline on their own data.
- Their data and split differ from ours, so their absolute numbers should not be compared with ours.
- The gain comes mostly from lexical overlap: many neighbors share identifiers and phrasing with the target summary.

## What works

- Simple. The decoder and the training loss are unchanged, so it drops into any encoder-decoder model.
- Works even with a frozen retriever, so no extra training is needed for retrieval.
- Shows that retrieved summaries carry useful information that the model can copy or paraphrase.

## Weaknesses (my reading)

- Neighbors often come from unrelated projects. Naming conventions, package names and APIs differ, so the retrieved summaries can push the model toward wrong vocabulary.
- Concatenation gives every neighbor the same weight. The model has to learn from raw text which neighbor to trust, and nothing in the architecture helps it with that.
- The retriever is not adapted to the summarization task. Its similarity score is never tuned to decide which neighbors help the decoder.
- Retrieved summaries use up encoder input budget that would otherwise hold the query code. With k = 5 and long neighbors, the query can get crowded out.

## What RepoSum changes

1. Repo-scoped index. Retrieval is limited to the same repository, so neighbors share naming conventions and APIs with the query. This is the biggest change in our ablation table, and it is the main reason RepoSum differs from RetroSum.
2. Learned gated fusion instead of concatenation. Each sibling is encoded from its code plus its summary with the shared encoder. Neighbors are weighted by alpha_i = softmax(cos(e_q, e_i) / 0.07) over k = 4 siblings. The query state is combined with the sibling context c = sum_i alpha_i h_i through a gate g = sigmoid(W [h_q ; c]), giving h = h_q + g * c.
3. Retriever trained jointly. The retrieval encoder is trained with an InfoNCE loss (temperature 0.07). Positives are functions that share a call-graph neighbor with the query; negatives are other functions from the same repo in the batch. The total loss is L = L_ce + 0.3 * L_ret.

RepoSum keeps RetroSum's retrieve-then-generate idea and its use of a Transformer backbone. We used RetroSum as a baseline in the intra_repo setting (22.6 BLEU-4). Its frozen-retriever idea corresponds to our "w/o L_ret" ablation.

## Things to keep in mind

- Leakage. A global index can contain the query function itself, and any later commit of it. Our v0.2 leaked the query into the index and dev BLEU jumped to 29.7. v0.3 fixed this with self-exclusion and commit-time filtering. Any RetroSum-style comparison must apply the same filter.
- Small repos. The repo-scoped index can be very small for some projects. We need to check how many repos have fewer than k eligible siblings and what the model does in that case.
- The k sweep. RetroSum uses k = 5. Our k sweep covers 0, 1, 2, 4, 8 and 16, so the comparison in the paper should state the k used for each baseline.
- Fusion vs. concatenation. Our ablation attributes 1.3 BLEU-4 to the gate. Before the seminar, check that the "plain concatenation" variant uses the same k and the same encoder as the full model.

## Questions for the group

- Should the RetroSum baseline use its original global index, or the same repo-scoped index with its concatenation? The first matches the paper, the second isolates the fusion change. We should say which one we report.
- Is the frozen-retriever variant trained with the same retrieval encoder initialization as the joint model?
- For the related work section, how much detail on the BM25 part do we need? Reviewers may ask why BM25 was dropped in favor of a dense index.
