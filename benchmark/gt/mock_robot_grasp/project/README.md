# GraspDR

Structured domain randomization and contact-aware rewards for sim-to-real robotic grasping.

GraspDR trains a visuomotor grasping policy entirely in simulation and deploys it on a real robot. It extends ADR-Grasp (Hallström and Okafor, 2020) in two ways: correlated, grouped randomization instead of independent per-parameter widening, and a contact-aware reward instead of a sparse lift-only reward.

## What the method does

- **SRS (Structured Randomization Sampler)**: `StructuredRandomizer` in `src/data.py`. Physics and visual parameters are split into three groups (visual, dynamics, geometry). Each group draws a latent vector and maps it through the Cholesky factor of a group correlation matrix with within-group correlation rho = 0.6, so parameters within a group move together.
- **CAR (Contact-Aware Reward)**: `ContactAwareReward` in `src/contact_reward.py`. Per step, `r_t = r_reach + r_lift + lambda_c * r_contact - lambda_f * max(0, F_t - F_max) / F_max`. Fingertip pads that press on the object with normal force between F_min = 0.8 N and F_max = 25 N, aligned with the surface normal, earn contact reward. Excess force is penalized.
- **Range Curriculum**: the randomization scale s ramps linearly from 0.5 to 1.0 over the first 2M environment steps, then stays at the training range of 1.0.
- **Policy**: `GraspPolicy` in the policy module under `src/`. A ResNet-18 style encoder (width 32) reads the 96x96 RGB-D wrist camera, a 2-layer MLP (hidden 128) reads proprioception, and a fused 256-d feature feeds a 6-D delta-pose plus gripper actor. The asymmetric critic also sees the privileged physics parameters. An auxiliary head predicts per-pad contact with a BCE loss.

Robot: simulated 7-DoF Franka-style arm with a parallel gripper and fingertip pads that have normal-force sensors. Simulator: PhysBox 2.3.

## Dataset

`tabletop_objs_v2`: 800 object meshes in 12 categories (mug, bottle, box, tool, toy, ...). 640 meshes are used for training, and the 160 held-out meshes are split into 80 validation and 80 test meshes. Mesh files sit in `meshes/`, and split files define the train/val/test lists.

## Installation

Requirements: Python 3.10, PyTorch 2.2, and a CUDA GPU. Training took about 11 h 40 min on one A6000-class GPU.

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Make sure PhysBox 2.3 is available in the environment and that the dataset path in your config points at `tabletop_objs_v2`.

## Training

```
python src/train.py --config configs/<config>.yaml
```

Use the Panda config in `configs/` (robot panda, dataset tabletop_objs_v2, eval ranges 0.5 to 2.5). That config inherits from the base config. If `--config` is omitted, `src/train.py` falls back to the base config.

Main settings (defaults in the base config):

| Key | Value | Key | Value |
|---|---|---|---|
| PPO learning rate | 3e-4 | lambda_c | 0.5 |
| gamma / GAE lambda | 0.99 / 0.95 | lambda_f | 0.1 |
| clip | 0.2 | F_max / F_min | 25 N / 0.8 N |
| parallel envs | 1024 | rho | 0.6 |
| rollout length | 32 steps | curriculum_steps | 2,000,000 |
| minibatch | 4096 | s_start | 0.5 |
| total env steps | 20M | aux_weight | 0.2 |

Paper runs use seeds 0 to 4. Logs are written to `logs/` with one file per day.

## Evaluation

```
python src/evaluate.py --config configs/<config>.yaml --ckpt checkpoints/best.pt
```

Evaluation runs shifted physics at randomization scales 0.5, 1.0, 1.5, 2.0 and 2.5, with 2,000 episodes per cell. It writes a CSV to `results/`. The plotting script in `src/` reads that CSV and saves the success-rate figure to `figures/`.

## Headline results (success rate %, range 1.5)

GraspDR reaches 87.4% (95% CI ±1.4). That is +4.8 over SimBridge (82.6) and +7.3 over ADR-Grasp (80.1).

| Method | 0.5 | 1.0 | 1.5 | 2.0 | 2.5 |
|---|---|---|---|---|---|
| GraspDR | 91.2 | 90.1 | 87.4 | 83.0 | 76.5 |
| SimBridge | 89.5 | 86.8 | 82.6 | 76.0 | 67.2 |
| ADR-Grasp | 88.0 | 85.3 | 80.1 | 72.4 | 63.8 |
| Uniform DR | 86.1 | 82.7 | 76.9 | 68.5 | 58.3 |
| No DR | 90.3 | 71.2 | 52.6 | 38.4 | 27.9 |

Ablations at range 1.5: removing SRS gives 81.9, removing CAR gives 82.7, removing the force penalty gives 85.1, and removing the Range Curriculum gives 84.6. Removing both SRS and CAR gives 76.9.

## Repository layout

- `src/`: training, evaluation, policy, randomizer, reward and plotting code
- `configs/`: base and per-robot YAML configs
- `docs/method.md`: detailed method description
- `paper/graspdr_draft_v2.pdf`: current draft (abstract, method, experiments, limitations)
- `results/`: evaluation CSV and ablation table
- `figures/`: paper figures
- `logs/`: training logs
- `checkpoints/`: saved model checkpoints (not tracked)
- `papers/`: reading notes on related work

## Known limitations

Single robot arm, rigid objects only, and tactile signals come from the simulator, so real tactile sensing is untested.
