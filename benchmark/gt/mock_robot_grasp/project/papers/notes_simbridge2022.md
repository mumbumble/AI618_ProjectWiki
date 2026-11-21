# Reading notes: SimBridge (Varga and Tanaka, 2022)

Slug: simbridge2022
Role in our project: competing baseline (ref2) for the GraspDR paper
Read by: project team, for the baseline section and related work

## One-line summary

SimBridge closes the sim-to-real gap at the image level. An adversarial, CycleGAN-style adapter translates simulated RGB-D wrist images so they look more like real camera frames, and the policy is trained with a sparse lift reward on top of that. Physics is only randomized inside fixed ranges.

## Method as I understand it

- **Adapter:** unpaired adversarial image translation from sim RGB-D to real-looking RGB-D. Training needs about 4,000 unpaired real images from the target setup.
- **Policy:** same grasping task and action space as ours (6-D delta pose plus gripper). The reward is sparse: 1.0 when the object is lifted, otherwise nothing.
- **Physics:** no physics randomization beyond fixed ranges. Friction, mass, and joint damping are not sampled per episode the way they are in SRS.
- **Tactile:** fingertip normal forces are not used anywhere in the objective or the observation.

## Why it matters for us

SimBridge is the strongest of the existing baselines at the in-range setting, and it is the one a reviewer will compare against most directly. The comparison is about where the gap lives. SimBridge addresses appearance, while the GraspDR argument is that the failures under shift come from dynamics (friction, mass, damping, pad stiffness) that an image adapter cannot fix.

## Our numbers (success rate %, 2000 episodes per cell, 95% CI)

| Method | 0.5 | 1.0 | 1.5 | 2.0 | 2.5 |
|---|---|---|---|---|---|
| GraspDR | 91.2 ±1.3 | 90.1 ±1.3 | 87.4 ±1.4 | 83.0 ±1.6 | 76.5 ±1.9 |
| ADR-Grasp | 88.0 ±1.4 | 85.3 ±1.6 | 80.1 ±1.8 | 72.4 ±2.0 | 63.8 ±2.1 |
| SimBridge | 89.5 ±1.4 | 86.8 ±1.5 | 82.6 ±1.7 | 76.0 ±1.9 | 67.2 ±2.1 |
| Uniform DR | 86.1 ±1.5 | 82.7 ±1.7 | 76.9 ±1.9 | 68.5 ±2.0 | 58.3 ±2.1 |
| No DR | 90.3 ±1.3 | 71.2 ±1.9 | 52.6 ±2.2 | 38.4 ±2.1 | 27.9 ±2.0 |

Observations:

- At range 0.5 SimBridge (89.5) is close to GraspDR (91.2) and No DR (90.3). The image adapter helps when the test physics matches training.
- Over range 0.5 to 2.5, SimBridge drops 22.3 points. GraspDR drops 14.7 points.
- SimBridge beats ADR-Grasp and Uniform DR at every range.
- Gap to GraspDR grows with shift: 1.7, 3.3, 4.8, 7.0, 9.3 points across the five ranges.
- **Headline:** at range 1.5, GraspDR 87.4 versus SimBridge 82.6 is a +4.8 point gain. Versus ADR-Grasp (80.1 at 1.5, using the 85.3 at 1.0 column as a sanity check only) the gain is +7.3 points.

## Strengths

- No need for physics parameters or simulator access beyond the usual training loop.
- Image-level adaptation is cheap at test time (the adapter is dropped after training, the policy runs on raw sim-like input).
- Works well when the real setup looks like the sim after translation.

## Weaknesses and open questions

- **Data cost:** 4,000 unpaired real images is a real collection effort. Our own setup has not been used to collect this yet, so the baseline numbers are from the reimplementation run by 김태민.
- **Appearance only:** the adapter does not model friction, object mass, or joint damping. These are exactly the parameters that break the policy at range 2.0 and above.
- **Sparse reward:** the lift-only reward gives no signal about contact quality, so the policy has no pressure to avoid over-squeezing and no credit for partial contact.
- **Fixed ranges:** the physics ranges are chosen once. We have no evidence about how SimBridge behaves when the real plant lies outside them.
- **Single adapter:** the adapter is trained once and does not adapt during training. It can underfit when the sim is changed by randomization, since the appearance keeps shifting.

## Notes for the paper

- Describe SimBridge as an image-level sim-to-real method, not as a physics method. This is the fairest framing and it is what the table shows.
- In the related work section, group SimBridge with pixel translation methods, and group ADR-Grasp with automatic randomization methods.
- In the limitations or discussion, mention the 4,000-image cost. It is a practical reason someone might pick GraspDR even where the in-range numbers are close.
- In the main table, keep the CI half-widths next to each value, as the other baselines have them.

## Open items

- Confirm with 김태민 that the SimBridge runs used the same 5 seeds (0 to 4) and 2000 episodes per cell as the other rows.
- Check the figure legend colour for SimBridge so it stays distinct from ADR-Grasp in the range plot.
- Ask 이도현 whether the limitations section should mention that the adapter was trained on our rendering pipeline and not on a public real dataset.
