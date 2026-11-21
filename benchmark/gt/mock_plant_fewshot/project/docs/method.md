# LeafProto: Method Description

LeafProto is a few-shot classifier for plant disease from leaf photos. Training is episodic: each step samples a 5-way episode with a small support set and a query set. The method builds on ProtoClass (Maddox and Tanaka, 2019) and changes three things: (a) cosine similarity with a learnable scale replaces squared Euclidean distance, (b) a frequency-domain augmentation called FreqMix is added, and (c) a consistency loss ties clean and mixed query views together.

## 1. Notation

- Episode: N = 5 classes, K support images per class (K = 5 in the main setting), Q = 15 query images per class.
- Input leaf image x, resized to 84 x 84 pixels with 3 color channels.
- f(x) in R^640: embedding produced by the encoder.

## 2. Encoder

The encoder is a ResNet-12 with channel widths 64, 160, 320, and 640. Global average pooling produces a 640-d embedding per image. The class `LeafProtoNet` wraps the encoder and the cosine prototype head.

## 3. FreqMix (key novel module)

FreqMix is a frequency-domain augmentation applied to the images of an episode during training.

1. For each image and each color channel, compute the 2D FFT and split the spectrum into amplitude A and phase P.
2. For two images a and b from the same episode, mix the low-frequency amplitude band:

   A_mix = (1 - M) * A_a + M * (lam * A_a + (1 - lam) * A_b)

   Inside the mask M the amplitude is interpolated between a and b. Outside M it stays A_a.
3. Keep the phase P_a unchanged and apply the inverse FFT to get the mixed image.
4. The label of the mixed image is the label of image a.

Hyperparameters:

- Band ratio beta = 0.1. M is a centered square covering 10% of the shorter side of the shifted spectrum.
- lam is drawn from Uniform(0.3, 0.7).
- Apply probability p = 0.5 per image.
- FreqMix is applied to support and query images during training only. It is never applied at evaluation.

The low-frequency band carries leaf color and illumination. Disease texture lives in higher frequencies, which FreqMix leaves intact.

## 4. Cosine prototype head

The class `CosineProtoHead` works as follows.

- Each support embedding is L2-normalized.
- The prototype of class c is the mean of the normalized support embeddings of that class:
  p_c = mean over support images of class c of f(x_s) / ||f(x_s)||.
- For a query q and class c, the logit is

  z_{q,c} = s * cos(f_q, p_c)

  where s is a learnable scale initialised to 10.0.
- Class probabilities are the softmax of the logits over the 5 classes.

## 5. Losses

The total loss is

  L = L_ce + lambda_cons * L_cons, with lambda_cons = 0.5.

- L_ce is the cross-entropy over the cosine logits of the query set.
- L_cons is the KL divergence between the softmax predictions of the clean query view and the FreqMix query view. The clean view is detached, so gradients flow only through the mixed branch.

## 6. Training procedure

1. Sample one 5-way episode per step, with K = 5 support and Q = 15 query images per class.
2. Apply FreqMix to support and query images with probability 0.5 each.
3. Encode all images, build prototypes from the support set, and compute cosine logits for the clean and mixed queries.
4. Compute L and update the encoder and scale s with Adam (learning rate 0.001, weight decay 0.0005) under a cosine learning-rate schedule.
5. Run 40,000 episodes with seed 42. Evaluate on the validation split every 500 steps and keep the checkpoint with the best validation accuracy.

The main 5-shot run took 5 h 40 min on one RTX 4090.

## 7. Evaluation

Evaluation uses 600 test episodes drawn from the 12 novel test classes of leafdoc_fs. Each episode is 5-way with 15 queries per class. Accuracy is reported in percent as a mean with a 95% confidence interval (ci95) over episodes. FreqMix is off and seeds are fixed at 42.

## 8. Results summary

Main results (accuracy %, 5-way, mean +- ci95):

| Method    | 1-shot     | 2-shot     | 5-shot     | 10-shot    |
|-----------|------------|------------|------------|------------|
| Finetune  | 52.3 +- 0.9 | 61.8 +- 0.8 | 72.5 +- 0.7 | 79.1 +- 0.6 |
| ProtoClass | 60.4 +- 0.9 | 70.2 +- 0.8 | 80.9 +- 0.6 | 85.0 +- 0.5 |
| FastAdapt | 64.8 +- 0.9 | 73.5 +- 0.8 | 83.6 +- 0.6 | 87.2 +- 0.5 |
| LeafProto | 69.7 +- 0.9 | 78.3 +- 0.7 | 87.4 +- 0.5 | 90.6 +- 0.4 |

At 5 shots LeafProto reaches 87.4%, which is 3.8 points above FastAdapt (83.6) and 6.5 points above ProtoClass (80.9).

Ablation (5-shot accuracy %):

| Variant                                   | Accuracy | Change |
|-------------------------------------------|----------|--------|
| Full LeafProto                            | 87.4     | -      |
| w/o FreqMix                               | 84.0     | -3.4   |
| w/o cosine head (squared Euclidean)       | 85.2     | -2.2   |
| w/o consistency loss (lambda_cons = 0)    | 86.3     | -1.1   |
| FreqMix full spectrum (beta = 1.0)        | 85.6     | -1.8   |

FreqMix is the largest contributor. Mixing the full spectrum hurts because it also alters the high-frequency texture that carries disease signal.

## 9. Relation to prior work

ProtoClass computes prototypes as mean support embeddings and classifies with squared Euclidean distance. LeafProto keeps the prototype idea and changes the similarity to a cosine with a learnable scale, adds FreqMix, and adds the consistency loss. FastAdapt relies on a 5-step ridge-regression adaptation of the last layer per episode, which makes test-time inference about 3.1 times slower per episode than LeafProto. LeafProto has no inner loop.

## 10. Limitations and open choices

- Only one dataset (leafdoc_fs) has been evaluated.
- Images are used at 84 x 84 resolution.
- Transfer across species has not been tested.
- The band ratio beta is fixed at 0.1 rather than learned.

## 11. Future work

- Learn beta per episode (adaptive FreqMix).
- Mix the phase as well as the amplitude.
- Use multi-scale prototypes in the cosine head.
- Learn a separate scale s for each class.
- Test cross-species transfer.
- Deploy the ResNet-12 encoder on mobile devices.
- Add a temperature to the consistency loss.
