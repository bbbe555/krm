# KRM Synthetic Dataset — Internal Tool Launch

Four-layer dataset for testing KRM's framework mechanics. Import each JSON file via the Import button in KRM.

## Layers

| File | Layer | What it tests |
|---|---|---|
| `layer1.json` | Coherent | Clean prerequisite chain, passes contradiction detection |
| `layer2.json` | First Revelation | SSO requirement discovered, new ES and 2 work items inserted |
| `layer3.json` | Contradiction | Migration track now depends on infra track — extended critical path |
| `layer4.json` | Stabilization | W1-W5 closed, W6-W8 active, W9 added for cutover comms |

## Structural primitives exercised

1. **Fan-out** — W1 is a prerequisite for W2, which is a prerequisite for W3
2. **Convergence** — W6 requires both the infra track (W3) and migration track (W5) to complete
3. **Reclassification** — Layer 2 promotes SSO from assumption to explicit engineered state
4. **Hard contradiction** — Layer 3 forces a previously independent track into a dependency
