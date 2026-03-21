# Notation Reference

Mathematical notation conventions used throughout the design documents.

## Core Symbols

| Symbol | Meaning |
|--------|---------|
| **G** | Full game — the trajectory of states G = S[0], S[1], ..., S[T] |
| **S[t]** | Universal state tensor at tick t. Contains only independent degrees of freedom |
| **t** | Time tick index. t=0 is 1836.1.1, T~5200 is 1936.1.1 (weekly ticks) |
| **Φ(S, Θ_i, Θ_u)** | Time evolution operator: the tick function that maps S[t] to S[t+1] |
| **Θ_i** | Truly invariant structure constants — game rules, loaded once, never written |
| **Θ_u[t]** | User-configurable parameters at tick t — player choices, written only by the player between ticks |
| **Π_x** | Projection onto subspace x (e.g. Π_b for buildings, Π_p for pops). Extracts a slice of S |
| **J** | Jacobian of Φ: ∂S[t+1]/∂S[t]. Piecewise-constant and sparse |
| **χ_c[t]** | Observation mask for country c — filters S[t] into what country c can see |

## Operator Types

| Type | Description | Example |
|------|-------------|---------|
| Projection (Π) | Sparse binary matrix selecting coordinates from S | Π_b extracts building state |
| Invariant (Θ_i) | Read-only tensor loaded from game data | P_io (production I/O coefficients) |
| Configurable (Θ_u) | Player-writable parameter tensor | PM selection, law choice |
| Derived quantity | Computed from S + Θ, never stored | GDP, profit, employment slots |

## Write Authority

| Tensor | Writer | Timing |
|--------|--------|--------|
| Θ_i | Nobody | Loaded at game start, immutable |
| Θ_u[t] | Player only | Between ticks |
| S[t] | Φ only | During tick evaluation |
