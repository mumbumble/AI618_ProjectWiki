# GraspDR: Method Description

GraspDR is a sim-to-real training recipe for parallel-jaw grasping with a 7-DoF Franka-style arm. It combines structured domain randomization with a contact-aware reward. It builds on the automatic domain randomization of ADR-Grasp (Hallström and Okafor, 2020) and replaces two of its core pieces. Training runs entirely in the PhysBox 2.3 simulator.

## Overview

The training loop runs as follows:

1. Object meshes from tabletop_objs_v2 (640 training meshes) are spawned in simulation.
2. The Structured Randomization Sampler (SRS, class `StructuredRandomizer`) draws physics and visual parameters.
3. The GraspPolicy (class `GraspPolicy`) receives a 96x96 RGB-D wrist image and proprioception, and outputs actions.
4. The Contact-Aware Reward (CAR, class `ContactAwareReward`) scores each step from fingertip normal forces.
5. PPO updates the policy. The Range Curriculum sets the randomization scale s that SRS uses.

GraspDR has two components, SRS and CAR, plus a third training piece, the Range Curriculum.

## 1. Structured Randomization Sampler (SRS)

Physics and visual parameters are split into three groups:

| Group    | Parameters                                              | Range                                     |
|----------|---------------------------------------------------------|-------------------------------------------|
| visual   | light intensity, texture hue, camera pose jitter        | camera jitter +-2 cm                      |
| dynamics | friction, object mass, joint damping                    | friction 0.4-1.2, mass +-30%, damping +-25% |
| geometry | object scale, pad stiffness                             | object scale 0.8-1.2                      |

Each group g has a latent vector z_g ~ N(0, I). Parameters are drawn as

    theta_g = mu_g + s * L_g z_g

where mu_g is the nominal value of the group, s is the randomization range scale, and L_g is the Cholesky factor of a group correlation matrix. Within each group, the off-diagonal correlation is rho = 0.6. Parameters inside a group are therefore sampled jointly and correlated. Groups are sampled independently of each other.

ADR-Grasp instead widens each parameter's range on its own and samples uniformly, which ignores correlations between parameters. SRS keeps the same parameter ranges but samples them as grouped, correlated draws.

## 2. Range Curriculum

The range scale s ramps linearly from 0.5 to 1.0 over the first 2M env steps and then stays at 1.0, which is the training range. The ramp is driven by environment step count, not by success rate. This replaces ADR-Grasp's rule of widening a range whenever success exceeds 80%.

For evaluation, the policy is tested on shifted physics at s in {0.5, 1.0, 1.5, 2.0, 2.5}. Values above 1.0 lie outside the training range and measure robustness to unseen physics.

## 3. Contact-Aware Reward (CAR)

The per-step reward is

    r_t = r_reach + r_lift + lambda_c * r_contact - lambda_f * max(0, F_t - F_max) / F_max

with the following terms:

- r_reach = 0.1 * exp(-5 * d), where d is the gripper-to-object distance in metres.
- r_lift = 1.0 once the object has been lifted above 10 cm for 10 steps.
- r_contact = (fraction of the 2 fingertip pads whose normal force lies between F_min and F_max) * cos(angle between the pad normal axis and the object surface normal).
- F_t is the fingertip normal force at step t, read from the simulated pad sensors.

Hyperparameters: lambda_c = 0.5, lambda_f = 0.1, F_max = 25 N, F_min = 0.8 N.

The contact term rewards pads that press on the object with a moderate force and face the surface. The force penalty discourages crushing. ADR-Grasp used a sparse lift-only reward, and CAR replaces it.

## 4. GraspPolicy Architecture

- Visual encoder: ResNet-18 style network with width 32, applied to the RGB-D input.
- Proprioception: 2-layer MLP with hidden size 128.
- Fusion: a 256-d feature from the visual and proprioceptive branches.
- Actor head: outputs a 6-D delta pose and a gripper command.
- Critic: asymmetric. It sees the fused feature and the privileged physics parameters theta, which are available only in simulation.
- Contact auxiliary head: predicts per-pad contact from the visual and proprioceptive features.

## 5. Training Objective

    L_total = L_clip + 0.5 * L_value - 0.01 * H + 0.2 * L_contact

- L_clip: PPO clipped surrogate objective with clip epsilon = 0.2.
- L_value: value function loss.
- H: policy entropy, used as a bonus.
- L_contact: binary cross-entropy over the per-pad contact labels from the auxiliary head.

## 6. Training Procedure

- Algorithm: PPO with Adam, learning rate 3e-4, gamma 0.99, GAE lambda 0.95, clip 0.2.
- Parallelism: 1024 environments, rollouts of 32 steps, minibatches of 4096.
- Length: 20M env steps in total.
- Seeds: 5 seeds (0-4) for every reported cell.
- Data: 640 training meshes. The 160 held-out meshes are split into 80 validation and 80 test meshes.
- Compute: one GPU. A 20M-step run takes about 11 h 40 min.

## 7. Evaluation

The metric is grasp success rate (%) on held-out meshes, with 2000 episodes per cell and 95% confidence intervals.

Main results (success %, per randomization range):

| Method       | 0.5  | 1.0  | 1.5  | 2.0  | 2.5  |
|--------------|------|------|------|------|------|
| GraspDR      | 91.2 | 90.1 | 87.4 | 83.0 | 76.5 |
| ADR-Grasp    | 88.0 | 85.3 | 80.1 | 72.4 | 63.8 |
| SimBridge    | 89.5 | 86.8 | 82.6 | 76.0 | 67.2 |
| Uniform DR   | 86.1 | 82.7 | 76.9 | 68.5 | 58.3 |
| No DR        | 90.3 | 71.2 | 52.6 | 38.4 | 27.9 |

At range 1.5, GraspDR reaches 87.4 +-1.4%. This is +4.8 points over the best baseline, SimBridge (82.6), and +7.3 points over ADR-Grasp (80.1).

Ablations at range 1.5 (5 seeds, 2000 episodes each):

| Variant                              | Success % | Change |
|--------------------------------------|-----------|--------|
| Full GraspDR                         | 87.4      | -      |
| w/o SRS (independent uniform)        | 81.9      | -5.5   |
| w/o CAR (sparse lift reward)         | 82.7      | -4.7   |
| w/o force penalty (lambda_f = 0)     | 85.1      | -2.3   |
| w/o Range Curriculum                 | 84.6      | -2.8   |
| w/o SRS and w/o CAR                  | 76.9      | -10.5  |

SRS and CAR contribute the largest gains. The effects are roughly additive: removing both gives 76.9, which matches the Uniform DR result.

## 8. Relation to Prior Work

GraspDR builds on ADR-Grasp (Hallström and Okafor, 2020). It keeps the idea of automatically widening the randomization range during training. It changes two things:

1. Independent per-parameter uniform widening becomes grouped, correlated sampling (SRS), with a linear Range Curriculum.
2. The sparse lift-only reward becomes the contact-aware reward (CAR).

SimBridge (Varga and Tanaka, 2022) is a competing approach. It uses adversarial image translation and a sparse lift reward, and it does not randomize physics beyond fixed ranges.

## 9. Limitations

- The method is tested on a single robot arm.
- It handles rigid objects only.
- Tactile sensing is simulated. The fingertip normal-force sensors have not been validated against real hardware.

## 10. Future Work

- Adaptive per-group scale s_g, replacing the single global scale s.
- A learned correlation matrix in SRS, replacing the fixed rho = 0.6.
- Real tactile signals in CAR, once hardware is available.
- A slip penalty added to CAR.
- Extension to deformable objects.
- Extension to multi-arm setups.
