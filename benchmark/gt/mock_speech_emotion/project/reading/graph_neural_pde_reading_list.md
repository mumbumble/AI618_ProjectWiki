# Reading Group: Graph Neural PDE Solvers

Reading list for the autumn session. We meet every other Thursday, 16:00 to 17:30, in seminar room 4B. Each session has one presenter who gives a 20-minute overview and leads a 30-minute discussion. Please read the assigned paper before the session, even if you only skim the proofs.

## Scope

The group focuses on two linked ideas:

- Graph neural networks viewed as discretized diffusion or reaction-diffusion equations on a graph.
- Continuous-depth models, where the number of layers is replaced by an integration time and an ODE solver.

We are less interested in benchmark tables and more in what the continuous view explains about oversmoothing, stability, and expressivity.

## Reading list

1. **Diffusion as message passing** (presenter: Ruth Ashgrove)
   Shows that a single graph convolution step is one explicit Euler step of a heat-type diffusion. Good starting point for the notation we will use all term.

2. **Oversmoothing as a dynamical property** (presenter: Tomas Veldkamp)
   Argues that node features converge to a low-dimensional subspace as depth grows, and links the rate of convergence to the spectral gap of the normalized Laplacian.

3. **Neural graph ODEs with adaptive solvers** (presenter: Mirela Constantin)
   Treats node embeddings as the state of an ODE and uses an adaptive Dormand-Prince solver during training. Discussion point: does adaptive step selection actually change the learned dynamics, or only the compute cost?

4. **Reaction terms against oversmoothing** (presenter: Jonas Hallqvist)
   Adds a nonlinear reaction term to the diffusion equation so that features can separate instead of collapse. We will compare the stability conditions with the pure diffusion case from entry 2.

5. **Stability of discretized graph flows** (presenter: Ruth Ashgrove)
   Gives step-size bounds under which the Euler discretization of a graph diffusion remains stable. Useful for deciding how many layers a practical model should use.

6. **Boundary conditions on graphs** (presenter: Tomas Veldkamp)
   Asks what a Dirichlet or Neumann condition means when the domain is a graph with irregular degree. Several proposed definitions are compared on a small synthetic lattice.

7. **Expressivity of continuous-depth graph models** (presenter: Mirela Constantin)
   Compares the function classes reachable by a discrete message-passing network and by its continuous limit. The main claim is that the continuous model cannot separate some pairs of non-isomorphic graphs that a higher-order discrete model can.

8. **Learning the PDE from data** (presenter: Jonas Hallqvist)
   Fits the diffusion coefficient and the reaction term to observed trajectories of node states, rather than fixing them by hand. Discussion point: identifiability when the graph is partially observed.

## Session schedule

| Session | Date (tentative) | Entries |
|---|---|---|
| 1 | Week of 2 Oct | 1 |
| 2 | Week of 16 Oct | 2, 3 |
| 3 | Week of 30 Oct | 4 |
| 4 | Week of 13 Nov | 5, 6 |
| 5 | Week of 27 Nov | 7 |
| 6 | Week of 11 Dec | 8 |

Dates may move if a presenter is travelling. Changes will be posted on the group mailing list.

## Discussion prompts

Each presenter should prepare answers to these three questions:

- What is the continuous-time analogue of the layer being studied, and what does it assume about the graph?
- Which result would change if the normalization of the adjacency matrix were switched from symmetric to random-walk?
- What is one experiment on a small graph that could confirm or refute the main claim within a single afternoon?

## Practical notes

- Papers are available through the shared library folder. Ask the group coordinator if you cannot find a copy.
- Please bring a printed copy of the main theorem for your own reference. Handwritten annotations are encouraged.
- If you want to present an alternative paper in place of one above, propose it at least two weeks before the session so the rest of the group can read it.

## Open questions for the term

- Does oversmoothing matter in practice once residual connections are added, or is it mostly a theoretical artifact?
- How should step size be chosen when the graph changes over time?
- Can a reaction-diffusion model be trained stably with the same optimizer settings as a standard message-passing network?
