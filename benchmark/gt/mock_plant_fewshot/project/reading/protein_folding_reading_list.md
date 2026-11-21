# Protein Structure Prediction: Reading Group List

Reading group, autumn term. We meet every other Thursday at 16:00 in Seminar Room 3. Each session has one presenter who gives a 15-minute summary, followed by open discussion. Please read the assigned paper before the session and bring at least one question.

## Schedule

| Session | Date | Presenter | Paper |
|---|---|---|---|
| 1 | 2026-09-03 | Yoon Taeho | FoldNet-lite 2023 |
| 2 | 2026-09-17 | Han Ara | Residue Graph Refinement 2021 |
| 3 | 2026-10-01 | Moon Sujin | DistoGram 2022 |
| 4 | 2026-10-15 | Oh Jinwoo | Torsion-Aware Attention 2024 |
| 5 | 2026-10-29 | Seo Hyejin | MSA Sparsify 2020 |
| 6 | 2026-11-12 | Bae Kyungmin | Recycling for Long Chains 2025 |

## Papers

### 1. FoldNet-lite 2023
A lightweight structure predictor that replaces the full evoformer-style trunk with a stack of pairwise convolution blocks. The authors argue that most of the accuracy comes from the distance-map head, so the trunk can be shrunk by a factor of four. Useful as a starting point for discussing what the trunk actually contributes.

### 2. Residue Graph Refinement 2021
Treats the predicted contact map as a graph and runs message passing over residues to clean up inconsistent contacts. The refinement step improves long-range contact precision but adds noticeable cost for chains above 500 residues. Worth reading for the error analysis in the appendix.

### 3. DistoGram 2022
Predicts a histogram of inter-residue distances per pair instead of a single distance value. The loss is a cross-entropy over bins, and the authors show that the spread of the histogram correlates with local uncertainty. We will compare this with the confidence heads in more recent work.

### 4. Torsion-Aware Attention 2024
Injects backbone torsion angles into the attention bias so that attention heads can respect local geometry. The gain is clearest on loops and disordered regions, where sequence-only models tend to smear their predictions. Discussion point: is the gain from better geometry or from a different inductive bias?

### 5. MSA Sparsify 2020
Studies how many aligned sequences a model really needs. The paper shows that subsampling the multiple sequence alignment to a few hundred rows loses little accuracy on well-conserved families but hurts orphan proteins badly. Good background for any discussion of low-data settings.

### 6. Recycling for Long Chains 2025
Analyses iterative recycling of the structure module for chains longer than 1,000 residues. The authors report that the number of recycling steps has diminishing returns after three cycles and that memory use, not accuracy, sets the practical limit. We will close the term by comparing this with the earlier papers on cost.

## Discussion Questions

1. Which of these papers changes the input representation, and which changes only the output head?
2. How should we judge a predicted structure for a protein with no close homologs in the training set?
3. Do the reported gains survive when the evaluation split is changed to a stricter time cutoff?
4. Which of the cost-saving ideas could be used in a lab with a single consumer GPU?

## Logistics

- Papers are available through the group drive folder. Please do not share the PDFs outside the group.
- If you cannot attend a session, send your questions to the presenter by the Wednesday before.
- The list may change if a new paper appears that fits the autumn theme. Any change will be announced in the group chat.
