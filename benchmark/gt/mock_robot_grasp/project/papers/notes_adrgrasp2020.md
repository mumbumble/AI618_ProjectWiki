# Reading notes: ADR-Grasp (adrgrasp2020)

**Paper:** Hallström and Okafor, "ADR-Grasp", 2020
**Why it matters for us:** GraspDR is built directly on top of this method. Its randomization loop and its reward are the two parts we change.
**Status:** Read in full. Notes below are for the lab group, not for the paper.

## One-paragraph summary

ADR-Grasp trains a grasping policy in simulation and uses automatic domain randomization (ADR) to decide how wide the randomization ranges should be. Every physics and visual parameter gets its own range. When the policy's success rate on the current ranges goes above 80%, the ranges are widened. New parameter values are drawn uniformly and independently for each parameter. The reward is sparse: the policy only gets credit for a successful lift.

## The mechanism, step by step

1. Start with narrow ranges around nominal physics.
2. Roll out the policy and measure grasp success.
3. If success is above 80%, widen the range of each parameter by a fixed increment.
4. Sample each parameter independently and uniformly from its current range.
5. Repeat for the rest of training.

The nice property is that the difficulty grows only when the policy is already competent, so the curriculum is implicit.

## What I like

- It is automatic. Nobody has to hand-tune the ranges for each object or robot.
- It needs no extra data. No real images, no demonstrations.
- The widening-on-success idea gives a natural curriculum without extra machinery.
- The implementation is small, which makes it a good base for changes.

## Weaknesses (our reading)

1. **Independence assumption.** Some parameters are physically linked. Friction, object mass and joint damping, or object scale and pad stiffness, do not vary independently in the real world. Independent uniform sampling produces physically odd combinations and spends samples on them. This is the main gap we want to close with grouped, correlated sampling (SRS).
2. **Sparse lift-only reward.** Early in training there is almost no signal, and contact quality is never rewarded. Nothing discourages squeezing an object too hard, and the fingertip force readings are ignored entirely. This is the motivation for the Contact-Aware Reward (CAR).
3. **One gate, one direction.** The 80% threshold is a single number, and the ranges only grow. There is no separate way to evaluate the policy at shifted physics beyond what training saw.
4. **Scaling is unclear.** The paper does not really discuss what happens when there are many parameters, and independent widening gets harder to reason about as that number grows.

## What we keep

- The idea of starting narrow and growing the randomization over training.
- The goal of learning a policy that works under physics it has not seen exactly.

We do not keep the success-gated widening. The Range Curriculum in GraspDR is a fixed linear ramp of the randomization scale s from 0.5 to 1.0 over the first 2M env steps, and then it stays at 1.0. That makes training runs easier to compare, since every seed sees the same schedule.

## What GraspDR changes relative to ADR-Grasp

- **Sampling (SRS).** Parameters are split into three groups: visual (light intensity, texture hue, camera pose jitter of ±2 cm), dynamics (friction 0.4–1.2, object mass ±30%, joint damping ±25%), and geometry (object scale 0.8–1.2, pad stiffness). Each group has a latent z_g ~ N(0, I). Parameters are theta = mu + s · L_g z_g, where L_g is the Cholesky factor of a group correlation matrix with within-group correlation rho = 0.6.
- **Reward (CAR).** The sparse lift reward is replaced by r_t = r_reach + r_lift + λ_c · r_contact − λ_f · max(0, F_t − F_max) / F_max, with λ_c = 0.5, λ_f = 0.1, F_max = 25 N and a contact threshold F_min = 0.8 N.

## Numbers to remember (success %, 2000 episodes per cell)

| Randomization range | ADR-Grasp | GraspDR |
|---|---|---|
| 0.5 | 88.0 ± 1.4 | 91.2 ± 1.3 |
| 1.0 | 85.3 ± 1.6 | 90.1 ± 1.3 |
| 1.5 | 80.1 ± 1.8 | 87.4 ± 1.4 |
| 2.5 | 63.8 ± 2.1 | 76.5 ± 1.9 |

At range 1.5 the gap is +7.3 points. At range 0.5, No DR (90.3) is still competitive, and ADR-Grasp is actually a bit below it. The gap only really opens up when the physics is shifted further from nominal.

## Open questions for the group

- Does the 80% gate still make sense when sampling is correlated? The threshold was tuned for independent ranges, and we have not checked it.
- How much of the drop at large range scales comes from the independence assumption, and how much from the sparse reward? The ablation without SRS (81.9) and without CAR (82.7) suggests both matter, but we have not separated them at every scale.
- Would the correlation matrix be better learned than fixed at rho = 0.6? This is on the ideas list.
- Can a success-gated schedule be combined with grouped sampling, or does the linear ramp work better in practice?

## Reading tips for the next person

- Read the sampling section before the reward section. The reward changes are easier to understand once you know what the policy is randomized over.
- The appendix experiments use fewer seeds than the main text suggests. Check the seed count before quoting any number.
- Keep the 80% gate in mind whenever you compare ADR-based numbers with ours, because the training schedules are not the same.
