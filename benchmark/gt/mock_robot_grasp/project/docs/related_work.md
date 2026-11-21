# Related Work

This is a working draft of the related-work section for the GraspDR paper. It covers the two prior methods we build on or compare against most directly, then states where GraspDR differs. Reading notes for each paper are in papers/notes_adrgrasp2020.md and papers/notes_simbridge2022.md. Check the claims below against those notes before the text is frozen.

## Domain randomization for sim-to-real grasping

Grasping policies trained in simulation and moved to a physical arm usually rely on domain randomization. Physics and visual parameters are sampled from ranges so the policy cannot overfit to one simulator configuration. The design choices are which parameters to randomize, how wide the ranges should be, and how values are sampled. Most practical systems sample each parameter independently from a fixed range. That is simple, but it makes it hard to cover realistic combinations of parameters, and a fixed range is either too narrow to transfer or too wide to learn from.

## Automatic domain randomization (ADR-Grasp)

Hallström and Okafor (2020) make the ranges adaptive. Whenever the grasp success rate on the current ranges exceeds 80%, the method widens the range of each physics and visual parameter. Widening is done one parameter at a time, and new values are drawn uniformly from the widened interval. This gives an automatic difficulty schedule without manual tuning, and it is the starting point for GraspDR.

We see two weaknesses. First, the sampler treats parameters as independent. It cannot express that object mass, friction and joint damping, or pad stiffness and object scale, move together in a real setup, so it spends samples on combinations that are unlikely to occur. Second, the reward is sparse and only checks whether the object was lifted. The policy gets little signal about how the fingers make contact before the object leaves the table.

In our experiments ADR-Grasp reaches 88.0% at range 0.5, 85.3% at 1.0 and 80.1% at 1.5 (±1.8). It falls to 63.8% at range 2.5.

## Adversarial image adaptation (SimBridge)

Varga and Tanaka (2022) attack the sim-to-real gap from the visual side. An adversarial image-translation adapter, similar in spirit to CycleGAN, maps simulated wrist-camera images toward the real image distribution, and the policy is trained on the translated images. The adapter needs about 4,000 unpaired real images. Physics is not randomized beyond fixed ranges, and the reward is the same sparse lift signal as in ADR-Grasp.

SimBridge is the strongest baseline in our table at every range from 1.0 to 2.5. It is a good answer to visual mismatch, but it does not address dynamics. Its success rate drops from 89.5% at range 0.5 to 67.2% at range 2.5, because the physics it was trained on is not varied during training. It also depends on collecting a real image set, which GraspDR does not require.

## Contact-aware rewards

Most grasping work that uses sparse rewards treats a lift as success and ignores the path to it. Contact information, when it is used, is often a binary touch flag. We use the normal forces measured at the two fingertip pads, which tells the policy whether each pad is actually pressing on the object and whether it presses too hard.

## How GraspDR differs

- **Sampling (SRS).** The StructuredRandomizer splits parameters into three groups: visual (light intensity, texture hue, camera pose jitter of ±2 cm), dynamics (friction 0.4–1.2, object mass ±30%, joint damping ±25%) and geometry (object scale 0.8–1.2, pad stiffness). Each group draws a latent vector, and parameters within a group are correlated through the Cholesky factor of a group correlation matrix with ρ = 0.6. A single range scale s applies to all groups. This replaces ADR-Grasp's independent per-parameter widening.
- **Reward (CAR).** ContactAwareReward adds a contact term to the reach and lift terms. The contact term counts the fraction of the two pads whose normal force lies between 0.8 N and 25 N, weighted by the cosine between the pad normal and the object surface normal. A penalty applies to force above 25 N, with weight 0.1. The contact term has weight 0.5. This replaces the sparse lift reward used by ADR-Grasp and SimBridge.
- **Curriculum.** The range scale ramps linearly from 0.5 to 1.0 over the first 2M environment steps and then stays at the training range. ADR-Grasp widens ranges based on a success threshold, whereas GraspDR uses a fixed schedule.
- **Auxiliary contact head.** A binary cross-entropy loss, weighted at 0.2, trains the policy to predict per-pad contact from the visual and proprioceptive features.
- **Privileged critic.** The critic sees the physics parameters that were sampled, while the actor only sees the RGB-D image and proprioception.
- **No image adapter.** Visual variation comes from the visual group of the randomizer, so no real images are needed for the adapter.

## Summary of the comparison

Success rate (%) on held-out evaluation, 2000 episodes per cell, 95% CI in parentheses:

| Method | Range 1.5 | Range 2.5 |
|---|---|---|
| GraspDR | 87.4 (±1.4) | 76.5 (±1.9) |
| SimBridge | 82.6 (±1.7) | 67.2 (±2.1) |
| ADR-Grasp | 80.1 (±1.8) | 63.8 (±2.1) |
| Uniform DR | 76.9 (±1.9) | 58.3 (±2.1) |
| No DR | 52.6 (±2.2) | 27.9 (±2.0) |

At range 1.5, GraspDR is 4.8 points above SimBridge and 7.3 points above ADR-Grasp. At the nominal range 0.5 the margin over the best baseline is small, since No DR reaches 90.3%. Most of the gain appears as the test physics moves away from the training range, which is what the structured sampler and the contact reward are meant to improve.

## Open points for the draft

- Confirm the ADR-Grasp widening threshold and the SimBridge training budget against the reading notes.
- Decide whether the related-work section should mention the Uniform DR and No DR baselines as separate prior practices or only as controls.
- The limitations section should note that the contact signal is simulated and that the comparison covers rigid objects only.
