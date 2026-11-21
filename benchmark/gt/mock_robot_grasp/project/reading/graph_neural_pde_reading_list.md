# Graph Neural PDE Reading List

A running list for the graph neural PDE reading group. We meet every two weeks for about 90 minutes. Each session has one presenter who gives a short overview, then the group discusses the main claims and open questions. Papers are grouped by theme. Start with the foundations if you are new to the area.

## 1. Foundations

- **Kipf & Welling (2017), "Semi-Supervised Classification with Graph Convolutional Networks."** The standard message-passing baseline. Read it first, since almost every later paper compares against it.
- **Gilmer et al. (2017), "Neural Message Passing for Quantum Chemistry."** Gives the general MPNN framework that the rest of the list builds on.
- **Battaglia et al. (2018), "Relational Inductive Biases, Deep Learning, and Graph Networks."** A long but useful survey of how graph structure enters the model design.

## 2. Continuous-depth view of message passing

- **Chen et al. (2018), "Neural Ordinary Differential Equations."** Introduces continuous-depth models and the adjoint method. We will refer back to it often.
- **Chamberlain et al. (2021), "GRAND: Graph Neural Diffusion."** Treats a graph layer as a discretised heat-type diffusion equation. Good for discussing what the Laplacian actually does to node features.
- **Chamberlain et al. (2021), "Beltrami Flow and Neural Diffusion on Graphs."** Extends the diffusion view with richer geometric structure. Pay attention to the choice of the coupling term.
- **Di Giovanni et al. (2022), "Graph Neural Networks as Gradient Flows."** Argues that many message-passing updates are gradient descent on an energy. Discussion point: does the energy view explain or merely re-describe the behaviour?
- **Eliasof, Haber & Treister (2021), "PDE-GCN: Novel Architectures for Graph Neural Networks Motivated by Partial Differential Equations."** Builds architectures directly from discretised PDE operators, with convection and diffusion terms.

## 3. Over-squashing and long-range dependencies

- **Alon & Yahav (2021), "On the Bottleneck of Graph Neural Networks and Its Practical Implications."** Identifies exponential compression of information through bottleneck nodes. Read this before the curvature papers.
- **Topping et al. (2022), "Understanding Over-Squashing and Bottlenecks on Graphs via Curvature."** Uses Ricci-type curvature to locate bottlenecks and proposes graph rewiring to relieve them.
- **Di Giovanni et al. (2023), "On Over-Squashing in Message Passing Neural Networks."** A more theoretical treatment of when rewiring helps and when it does not.

## 4. Sheaves and cellular structure

- **Bodnar et al. (2022), "Neural Sheaf Diffusion."** Replaces the scalar graph Laplacian with a sheaf Laplacian that carries learned restriction maps. Good for discussing whether the extra expressivity is needed in practice.
- **Bodnar et al. (2022), "Neural Sheaf Diffusion: A Topological Perspective on Heterophily and Oversmoothing in GNNs."** Companion paper with heterophily experiments. Read the two together.

## 5. Learning physical simulation on meshes and particles

- **Sanchez-Gonzalez et al. (2020), "Learning to Simulate Complex Physics with Graph Networks."** Learned particle-based simulators with a graph network encoder-processor-decoder.
- **Pfaff et al. (2021), "Learning Mesh-Based Simulation with Graph Networks."** Moves the same idea onto adaptive meshes. Useful for thinking about how the graph is built from the physical domain.
- **Raissi, Perdikaris & Karniadakis (2019), "Physics-Informed Neural Networks."** The reference for penalising PDE residuals in the loss. Compare the residual-loss idea with the graph-based approaches above.

## 6. Operator learning

- **Lu et al. (2021), "Learning Nonlinear Operators via DeepONet."** Learns maps between function spaces with a branch-trunk architecture.
- **Li et al. (2021), "Fourier Neural Operator for Parametric Partial Differential Equations."** Learns the solution operator in Fourier space. We will discuss how the mesh-free and graph-based operator methods differ in what they assume about the domain.

## Open questions for discussion

1. Does the diffusion or gradient-flow view give useful design rules, or does it mainly give post hoc explanations?
2. When rewiring helps with over-squashing, does it also hurt by adding spurious edges?
3. Are sheaf-based models worth their extra parameters on real benchmarks?
4. How should boundary conditions be encoded when the graph comes from an irregular mesh?
5. What is a fair benchmark for graph PDE solvers, given that many datasets come from simple grids?

## Schedule

| Session | Theme | Presenter |
|---|---|---|
| 1 | Foundations (Section 1) | Rotating, sign-up sheet on the wiki |
| 2 | Continuous-depth view (Section 2) | Rotating |
| 3 | Over-squashing (Section 3) | Rotating |
| 4 | Sheaves (Section 4) | Rotating |
| 5 | Physical simulation (Section 5) | Rotating |
| 6 | Operator learning and open questions (Section 6) | Group discussion |

Presenters should send a one-page summary to the list at least two days before the session. Please bring one question per paper to the discussion.
