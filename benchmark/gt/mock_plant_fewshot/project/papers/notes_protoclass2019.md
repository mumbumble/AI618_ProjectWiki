# Reading notes: ProtoClass (protoclass2019)

Authors: Maddox and Tanaka. Read for: the prior work LeafProto is built on.
Status: read in full, notes by Choi Jimin, reviewed by Park Hyunwoo.

## One-line summary

ProtoClass is an episodic few-shot method. Each class gets a prototype, the mean of its support embeddings, and queries are classified by squared Euclidean distance to the prototypes.

## Setup as described in the paper

- Episodic training with N-way K-shot episodes and a query set per episode.
- Encoder: a 4-conv backbone, producing a flat embedding vector.
- Prototype p_c = mean of the support embeddings of class c.
- Score for a query: negative squared Euclidean distance to each prototype, softmax over classes, cross-entropy loss.
- Train and test use the same N-way K-shot format.

## Reported results

- 5-way 5-shot accuracy of 78.2 on their own evaluation set.
- Their numbers are not directly comparable to ours. Different data, different resolution, different encoder.
- On leafdoc_fs (our runs, same protocol as the paper tables), ProtoClass reaches 60.4 at 1-shot, 70.2 at 2-shot, 80.9 at 5-shot and 85.0 at 10-shot.

## What is useful for us

- The prototype idea is simple and cheap at test time. No inner loop, so it is much faster per episode than FastAdapt.
- Episodic training matches our test protocol directly (5-way, 15 queries per class).
- The Euclidean head is easy to swap. That is why we could test the cosine head as a single change.

## What we change in LeafProto

(a) Cosine head with a learnable scale.
- Prototypes are now built from L2-normalised support embeddings.
- Logit for query q and class c is s * cos(f_q, p_c), with s initialised to 10.0 and learned.
- The paper's squared Euclidean distance is replaced by this cosine score.

(b) FreqMix augmentation, which is new in our work and not in ProtoClass.
- Each leaf image goes through a 2D FFT per channel. Amplitude and phase are split.
- Low-frequency amplitude is mixed between two images of the same episode. Phase is kept.
- Settings: band ratio beta = 0.1, lam ~ Uniform(0.3, 0.7), apply probability p = 0.5, training only.

(c) Consistency loss.
- Total loss L = L_ce + lambda_cons * L_cons, with lambda_cons = 0.5.
- L_cons is the KL divergence between the softmax of the clean query view and the FreqMix query view. The clean view is detached.

Encoder: we use a ResNet-12 (channels 64-160-320-640, 640-d embedding), not the 4-conv net of the original paper.

## Ablation evidence on the head and the augmentation

From the 5-shot ablation on leafdoc_fs:
- Full LeafProto: 87.4
- Squared Euclidean instead of cosine head: 85.2 (-2.2)
- No FreqMix: 84.0 (-3.4)
- No consistency loss: 86.3 (-1.1)

So the cosine head matters, but FreqMix matters more. This is the main reason the paper is framed around the augmentation and not only the head.

## Concerns to keep in mind

- The original paper used a small encoder and a different benchmark. Some of the gain we see could come from the encoder change, not only from the three modifications. We should say this clearly in the limitations.
- ProtoClass has no augmentation, so the fair comparison for our method is ProtoClass with the same ResNet-12 encoder. We do not have this run yet. Lee Doyun may be able to add it.
- The paper does not study image resolution. Our inputs are 84x84 field photos, and small lesions may be hard to see at that size.
- The paper only reports 5-way results in the main text as far as I can tell. Our 1-shot and 10-shot numbers are our own runs.

## Quick takeaways for the write-up

- Cite ProtoClass as the base method in the method section. Say which parts we keep (prototypes, episodic training) and which we change (distance, augmentation, loss).
- Do not compare the 78.2 number directly with our tables. Use our own ProtoClass runs for the comparison.
- If the seminar slide on ProtoClass recap needs one line: "Prototype = mean support embedding, squared Euclidean distance, episodic training."
