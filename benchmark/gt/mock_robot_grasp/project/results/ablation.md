# GraspDR Ablation Results

Success rate (%) at randomization range scale s = 1.5, the shifted-physics setting used for the headline comparison.

- Each row: 5 seeds (0-4), 2000 evaluation episodes per seed.
- Full model is the GraspDR configuration from the main results table.
- Each ablation removes one component and keeps everything else at the default settings.

## Component removal

| Variant | What changes | Success (%) | Δ vs. full (points) |
|---|---|---:|---:|
| Full GraspDR | SRS + CAR (λ_c = 0.5, λ_f = 0.1) + Range Curriculum | 87.4 | — |
| w/o SRS | Independent uniform sampling per parameter (ADR-Grasp-style) | 81.9 | −5.5 |
| w/o CAR | Sparse lift-only reward (r_lift only) | 82.7 | −4.7 |
| w/o force penalty | λ_f = 0 (contact reward kept, no excess-force term) | 85.1 | −2.3 |
| w/o Range Curriculum | s fixed at 1.0 from step 0 | 84.6 | −2.8 |
| w/o SRS and w/o CAR | Independent uniform sampling + sparse lift reward | 76.9 | −10.5 |

The last row matches the Uniform DR result at range 1.5 in the main table, which is expected because that variant has the same sampler and reward as the Uniform DR baseline.

## Analysis

**Largest contributors.** Removing either the structured sampler (SRS) or the contact-aware reward (CAR) costs the most. SRS removal costs 5.5 points and CAR removal costs 4.7 points. Both are larger than the effect of any single smaller term, so the two main components are carrying most of the gain over the baselines.

**Smaller contributors.** The Range Curriculum is worth 2.8 points. Its main effect is to let the policy learn stable grasping at nominal physics before it sees the full randomization range. The force penalty adds 2.3 points on top of the contact reward. It keeps the policy from squeezing objects with fingertip forces above F_max = 25 N, which the simulated pad sensors can register.

**Roughly additive effects.** Removing both SRS and CAR gives 76.9%, a drop of 10.5 points. The individual drops sum to 10.2 points, so the two components interact very little. The 0.3-point gap is within run-to-run noise. This is why we describe the components as contributing roughly independently: the sampler improves coverage of the parameter space, and the reward improves what the policy learns from each episode.

**Why the sampler matters.** Without SRS, sampled friction, mass, damping, and pad stiffness are drawn independently, so the sampler produces physically implausible combinations (for example, high friction with very low pad stiffness). Grouped sampling with within-group correlation (ρ = 0.6) keeps the sampled physics closer to what a real arm and object can produce. That is consistent with the fact that the gap between SRS-off and full GraspDR grows at larger ranges in the main results.

**Caveats.**
- These ablations are reported at range 1.5 only. Trends at other ranges (0.5 to 2.5) are shown in the main results, not here.
- The ablation runs use the same 20M-step budget as the full model, so differences reflect the final policy, not early-training speed.
- The simulator is PhysBox 2.3 and the robot is a simulated 7-DoF arm with parallel gripper. Results on the real robot are not part of this table.
