# Related Work (draft)

Draft for the v2 internal review. Comments welcome, especially on the FastAdapt paragraph.

## Episodic few-shot classification

Few-shot image classification is usually trained and evaluated in episodes. Each episode samples N classes with K labelled support images and Q query images per class, and the model must classify the queries using only the support set. Our experiments follow this protocol with 5-way episodes, 15 queries per class, and 1, 2, 5 or 10 shots. We report accuracy in percent with a 95% confidence interval over 600 test episodes, using seed 42.

## Prototype-based methods

ProtoClass (Maddox and Tanaka, 2019) represents each class by the mean of its support embeddings and assigns a query to the nearest prototype under squared Euclidean distance. Its original benchmark reports 78.2% for 5-way 5-shot, using a four-layer convolutional encoder trained episodically. Our work starts from ProtoClass. We keep the prototype-as-mean-of-support idea and the episodic training loop, and change three things: the similarity function, the training augmentation, and the training objective. Notes on the paper are in papers/notes_protoclass2019.md.

## Adaptation-based methods

FastAdapt (Voss and Lindqvist, 2022) meta-learns an encoder and then adapts the last layer for each test episode. The adaptation is a five-step ridge-regression inner loop with regularisation 0.1. The paper reports 83.6% for 5-way 5-shot. We reproduced this number on leafdoc_fs, so it is the strongest baseline in our tables. Its main costs are at test time. Each episode needs the inner loop, which makes inference about 3.1 times slower per episode than LeafProto. The method also uses no image-level augmentation, so it does not address the limited variety of field photos. Notes are in papers/notes_fastadapt2022.md.

## Fine-tuning baselines

The Finetune baseline pretrains the encoder on the base classes and then fine-tunes a linear head on the support set for 100 steps. It is a simple and widely used reference. On leafdoc_fs it reaches 52.3% at 1 shot and 72.5% at 5 shots, well below the prototype methods. This gap suggests that a head fitted on one or two images per class overfits quickly, which is the main reason we chose a prototype-based design.

## Frequency-domain and leaf-specific augmentation

Augmentation that changes the frequency content of images has been used for general recognition. SpecShift (2021) perturbs spectral components to improve robustness to appearance shifts. LeafAug (2020) uses colour and geometric transforms designed for leaf photos. Both are general context for our work and neither targets few-shot episodes. FreqMix differs in two ways. It mixes only the low-frequency amplitude band between two images of the same episode, and it keeps the phase of the anchor image. Low-frequency amplitude mainly carries colour and illumination. Disease texture sits at higher frequencies, and FreqMix leaves that band untouched.

## Plant disease classification

Most plant disease classifiers assume many labelled images per class and a fixed label set. Field photos vary in lighting, background and leaf age, and new species and disease combinations appear often. Few-shot formulations fit this setting better, but they are less studied for leaves. Our dataset, leafdoc_fs, has 54 species-by-disease classes split into 30 base, 12 validation and 12 novel test classes.

## How this work differs

LeafProto builds on ProtoClass and changes three parts:

- **Similarity.** Queries are compared to prototypes with cosine similarity scaled by a learnable scale s, initialised to 10.0. The Euclidean head is replaced.
- **Augmentation.** FreqMix works in the 2D FFT domain. For two images in an episode, the amplitude inside a centred square covering 10% of the shorter side is interpolated with lambda drawn from Uniform(0.3, 0.7). The phase is kept and the inverse FFT gives the mixed image. The label is that of the anchor. It is applied with probability 0.5 per image, in training only.
- **Objective.** The total loss is L = L_ce + 0.5 * L_cons. L_ce is cross-entropy over the cosine logits of the queries. L_cons is a KL divergence between the predictions on the clean query view and the FreqMix view, with the clean view detached.

On leafdoc_fs at 5 shots, LeafProto reaches 87.4%. This is 3.8 points above FastAdapt (83.6%) and 6.5 points above ProtoClass (80.9%). Unlike FastAdapt, LeafProto needs no inner loop at test time.

The ablation at 5 shots supports each part. Removing FreqMix costs 3.4 points (84.0%). Replacing the cosine head with squared Euclidean distance costs 2.2 points (85.2%). Setting lambda_cons to 0 costs 1.1 points (86.3%). Mixing the full spectrum with beta = 1.0 costs 1.8 points (85.6%). FreqMix contributes the most, which is why we treat the low-frequency band restriction as the central design choice.

## Open gaps

Related methods are also limited in ways we do not yet address. Our evaluation uses a single dataset, images at 84x84 resolution, and no cross-species transfer. The band ratio beta is fixed at 0.1 rather than adapted per episode. We discuss these limits in the final section of the paper.
