# Related Work

This is a working draft of the related-work section for RepoSum. Reading notes for the two closest systems are in papers/notes_retrosum2021.md and papers/notes_codesibling2022.md.

## 2.1 Neural source-code summarization

Encoder-decoder models trained on function-summary pairs are the standard approach to code summarization. A plain Transformer encoder-decoder over BPE tokens of the function body is our first baseline. On the intra-repo split it reaches 20.4 BLEU-4. Such a model has to store project-specific identifiers, helper names, and local idioms in its weights alone. That is hard when test functions come from repositories it has already seen, but from later commits.

## 2.2 Retrieval-augmented summarization

RetroSum (Oh and Baek, 2021) showed that retrieving existing summaries helps generation. It searches a global corpus of about 2.1M functions from many projects. The retriever is frozen and combines BM25 with dense embeddings. The top 5 neighbors are concatenated to the encoder input, and the reported gain on its own data is +2.2 BLEU over its Transformer baseline. Our notes flag a main weakness: many retrieved neighbors come from unrelated projects that use different naming conventions, so their summaries transfer poorly.

RepoSum keeps the retrieve-then-generate idea and changes three things. The index is scoped to the query's own repository. Neighbors are fused by a learned gate instead of concatenation. The retriever is trained jointly with an InfoNCE objective.

## 2.3 Sibling-based context for code models

CodeSibling (Yoon et al., 2022) is the closest competitor. It retrieves functions from the same file or package with BM25, keeps the top 3, truncates the input to 512 tokens, and concatenates the sibling code to the query. Using same-repository context is the right intuition, and CodeSibling is our strongest baseline at 23.7 BLEU-4 on the intra-repo split.

Its design leaves three gaps. First, there is no learned fusion, so the decoder must learn from raw token streams to ignore unhelpful siblings. Second, the ranking is fixed by lexical overlap and is never trained. Third, its notes record a leakage failure: duplicates of the query function can appear among the retrieved siblings, which exposes the reference summary at test time.

## 2.4 How RepoSum differs

We compare the methods along four axes.

1. **Retrieval scope.** RepoSum builds a repository-scoped dense index. Retrieving over all repositories instead costs 2.1 BLEU-4 (24.0 against 26.1), the largest drop in our ablation.
2. **Leakage control.** The query function and every function from a commit later than the query are removed from the index. The rule matches the chronological split, and it is stricter than the handling in CodeSibling.
3. **Fusion.** Sibling states are combined with the query state through a gate, g = sigmoid(W [h_q ; c]), where c is the attention-weighted sibling context. The weights are a softmax over cosine similarities with temperature 0.07. Replacing the gate with plain concatenation costs 1.3 BLEU-4.
4. **Retriever training.** The code encoder used for retrieval is trained with an InfoNCE loss, L_ret, at temperature 0.07. Positives are functions that share a call-graph neighbor with the query, and negatives are other functions from the same repository in the batch. Freezing the retriever costs 1.1 BLEU-4, and replacing call-graph positives with random positives costs 0.8.

| Method | Retrieval scope | Neighbors used | Fusion | Retriever training | intra-repo BLEU-4 |
|---|---|---|---|---|---|
| Transformer | none | none | none | none | 20.4 |
| RetroSum | global | top 5 summaries | concatenation | frozen | 22.6 |
| CodeSibling | same file/package | top 3 code | concatenation | none (BM25) | 23.7 |
| RepoSum | same repository | top 4 code + summary | gated | joint (L_ret) | 26.1 |

## 2.5 Positioning

RepoSum is not a larger model. It uses the same encoder-decoder size as the baselines and differs in what it retrieves, how the neighbors enter the model, and how the retriever is trained. The gain is largest when the test function sits in a repository that has many close siblings.

The cross-repo setting tests whether the gain transfers to unseen repositories. There RepoSum reaches 22.4 BLEU-4, against 20.9 for CodeSibling, 20.1 for RetroSum, and 18.2 for the Transformer. The margin over CodeSibling is smaller than on the intra-repo split (+1.5 against +2.4). This is consistent with the repository-scoped index having less to offer when the test repository is new.

Retrieval size also matters. Performance peaks at k = 4 for RepoSum and degrades slowly for larger k. Both baselines peak at the same k but fall off faster. We read this as evidence that the gate can suppress noisy siblings, while concatenation cannot.

## 2.6 Open limitations

RepoSum assumes that the target repository already contains related functions. Very small or newly created repositories give the index little to retrieve from, and the method then falls back toward the Transformer baseline. Cross-language siblings, call-graph edges in the index, per-layer fusion, and adaptive k are natural extensions. We have not evaluated them yet.
