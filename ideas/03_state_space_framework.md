# State-Space Framework

> See [00_notation.md](00_notation.md) for symbol definitions.

## Core Idea

The entire game is a trajectory through a single state space, governed by time.

```
S[t] ∈ ℝ^N       t ∈ {0, 1, ..., T}
```

- **t** is the absolute time dimension — weekly ticks, t=0 is 1836.1.1, T≈5200 is 1936.1.1
- **S[t]** is the universal state at tick t — everything that can vary
- The full game history is a trajectory: G = S[0], S[1], ..., S[T]

Every subsystem — buildings, pops, prices, production — is a **projection** (Π) of S[t]. The simulation never stores derived quantities. Everything computable is computed on the fly.

## The Universal State Vector

S[t] contains only **independent degrees of freedom** — variables that cannot be derived from other variables plus the invariant operators.

### What's in S[t]

| Subspace | Index | Approx Dimension |
|----------|-------|-------------------|
| `building_levels[state, building_type]` | 730 × 80 | ~58K |
| `building_cash[state, building_type]` | 730 × 80 | ~58K |
| `building_wages[state, building_type]` | 730 × 80 | ~58K |
| `pop_count[state, pop_type, wealth_level]` | 730 × 15 × 99 | ~1.1M |
| `prices[market, good]` | 200 × 49 | ~10K |
| `treasury[country]` | ~100 | ~100 |
| `tech_unlocked[country, tech]` | 100 × 100 | ~10K |

**Total N ≈ 1.3M floats.** About 5MB per state snapshot.

### What's NOT in S[t] — Derived Quantities

These are computable from S[t] + invariant operators Θ:

- **Production output** = `P_io · active_PM(S) · building_levels(S)`
- **Supply / demand** = aggregation of production + pop consumption
- **Profit** = revenue − input_cost − wages
- **Employment slots** = `P_emp · active_PM(S) · building_levels(S)`
- **GDP** = output × prices, summed per country
- **Standard of living** = f(income, buy_package_cost at wealth_level)

**Rule**: if a quantity is fully determined by S[t] and Θ, it is a projection, not a state variable.

## Invariant Operators (Θ_i)

Loaded once from game data files and never mutated. These define the "rules" — the linear maps that transform state into outcomes.

| Operator | Shape | Source |
|----------|-------|--------|
| `P_io[pm, good]` | 200 × 49 | `production_methods/` — I/O coefficients |
| `P_emp[pm, pop_type]` | 200 × 15 | `production_methods/` — employment per PM |
| `C_needs[pop_need, good]` | ~20 × 49 | `pop_needs/` — consumption baskets |
| `G_base[good]` | 49 | `goods/` — base prices |
| `BG_props[building_group, property]` | ~30 × k | `building_groups/` — economy of scale, urbanization |
| `Tech_DAG[tech, tech]` | 100 × 100 | `technology/` — prerequisite graph |
| `Tech_unlocks[tech, pm]` | 100 × 200 | `production_methods/` — tech gates PM |
| `State_resources[state, resource]` | 730 × k | Map data — arable land, coal deposits |
| `State_adjacency[state, state]` | 730 × 730 | Map topology (sparse) |
| `Sim_constants` | ~100 scalars | `defines/00_defines.txt` — PRICE_RANGE, MAX_WAGE_STEP_CHANGE |

These sit in GPU constant/read-only memory.

## Projections

A projection Π extracts a subspace of S[t]. Structurally, each Π is an index selection — a sparse binary matrix that picks coordinates from the flat state vector.

```
Π_b · S[t]    →  building state at time t       ∈ ℝ^(730×80×k)
Π_p · S[t]    →  population state at time t     ∈ ℝ^(730×15×99)
Π_m · S[t]    →  market prices at time t        ∈ ℝ^(200×49)
Π_t · S[t]    →  government money at time t     ∈ ℝ^100
```

Derived quantities chain projections through operators:

```
production[t]     = P_io · Π_pm(S[t]) · Π_bl(S[t])
pop_demand[t]     = C_needs · Π_p(S[t])
GDP[country, t]   = Π_c · (production(t) ⊙ Π_m(S[t]))
```

Production and demand are **not stored** — they are projections of S through Θ.

## The Tick as a Single Operator

```
S[t+1] = Φ(S[t], Θ_i, Θ_u[t])
```

Φ is **piecewise-linear**. Within a regime (no good hitting price cap, no building going bankrupt, no tech researched), it collapses to:

```
S[t+1] = A · S[t] + b
```

where A is a sparse N×N matrix and b is a constant offset.

### Simulation Steps

1. `output = P_io @ active_PM_selection @ building_levels` — matmul (linear)
2. `supply, demand = aggregate(output, pop_demand)` — summation (linear)
3. `prices = price_solver(supply, demand, G_base)` — piecewise-linear (clamp at ±PRICE_RANGE)
4. `profit = revenue - cost - wages` — linear
5. `Δwages = f(profit_margin, thresholds)` — piecewise-linear
6. `Δpop_wealth = f(income vs buy_package_cost)` — piecewise-linear (99 discrete levels)
7. `Δbuilding_levels = construction_decisions` — sparse, discrete

### Jacobian

Since Φ is piecewise-linear, J = ∂S[t+1]/∂S[t] is piecewise-constant:

```
J = J_price × J_supply_demand × J_production
    (diagonal)  (sparse sum)     (constant matrix)
```

All factors are sparse or diagonal. The full J is O(N) to compute, not O(N²).

This enables:
- **Stability analysis** — eigenvalues of J: |λ_max| > 1 means divergence
- **Implicit integration** — (I − dt·J)·ΔS = dt·Φ(S) for stiff dynamics
- **Sensitivity analysis** — "add 1 steel mill, what happens?" = one J·v product
- **Skip-ahead** — if eigenvalues are well inside unit circle, extrapolate: S[t+k] ≈ S[t] + k·J·(S[t] − S[t−1])

### Regime Transitions

The piecewise boundaries are discrete events:
- A good hitting its price floor/ceiling (PRICE_RANGE = 0.75)
- A building going bankrupt (cash → 0)
- A pop crossing a wealth level threshold
- Tech researched → new PM unlocked
- War/treaty → state ownership change

Between these events, A is constant and the dynamics are a linear recurrence with a closed-form solution: `S[t] = Aᵗ · S[0] + (I − A)⁻¹ · b`.

## Encoding Strategy — Keeping Everything Linear

All categorical or discrete state variables are stored as **one-hot binary tensors**. This converts selection/branching into multiplication, which is linear and GPU-native.

### Production Method Selection

Instead of a categorical integer per PM group:

```
# Categorical integer — breaks linearity, needs branching
active_PM[state, building, PM_group] ∈ {0, 1, ..., k-1}
```

Store a one-hot binary vector:

```
# One-hot — selection becomes matmul
active_PM[state, building, PM_group, PM_option] ∈ {0, 1}
```

Then effective I/O coefficients are:

```
effective_IO[state, building, good] = P_io[PM_option, good] @ active_PM[state, building, PM_group, PM_option]
```

No branching, no indexing — pure linear algebra. GPU threads never diverge.

### Generalization

| Variable | Encoding | Dimension Added |
|----------|----------|-----------------|
| Active PM per group | one-hot over PM options | PM_option (2–5) |
| Technology unlocked | binary flag per tech | already binary |
| Trade route active | binary flag per route | already binary |
| Law enacted | one-hot over law options | law_option (~3–6) |
| Building subsidy/tax | binary or one-hot | policy_level |

Memory cost: `active_PM` goes from ~58K integers to ~234K booleans — negligible at GPU scale.

## Linearization Policy

Not every subsystem is literally linear, but most can be **approximated as piecewise-linear**, keeping them inside the `S[t+1] = A·S[t] + b` regime framework.

### Migration

```
Δpop[state, pop_type] ≈ M_mig · (SoL[state] - SoL_mean)
```

`M_mig` encodes adjacency + distance decay (sparse, from State_adjacency in Θ). Linear in SoL differentials.

### Construction & Investment

```
Δbuilding_levels[state, type] ≈ α · clamp(profit_margin - threshold, 0, cap)
```

Piecewise-linear: zero below threshold, linear above, capped at max construction rate.

### Inter-Market Trade

```
trade_flow[m1, m2, good] ≈ β · (price[m2, good] - price[m1, good])
```

Linear in price differentials — analogous to heat diffusion on a graph. The trade graph is sparse.

### Subsistence Economy

```
subsistence_level[state] ≈ γ · unemployed_pops[state]
```

Linear in pop count. Regime boundary: if unemployment drops to zero, subsistence clamps to zero.

### Accuracy Tuning

| Approximation | Single-Linear | 3–5 Regimes | 10+ Regimes |
|---------------|:-------------:|:-----------:|:-----------:|
| Migration | ~70% | ~85% | ~95% |
| Construction | ~80% | ~90% | ~95% |
| Trade | ~85% | ~92% | ~97% |
| Subsistence | ~90% | ~95% | ~98% |

These are hypothetical targets — actual numbers come from validation. More regimes means more entries in the regime-transition event list, with no architectural changes.

## Observation Masks — Per-Country Views

The full state S[t] is the "god view." Each country c observes a **masked projection** through χ_c.

```
V_c[t] = χ_c[t] ⊙ (Π · S[t])
```

χ_c is a sparse vector: 1 where visible, 0 where hidden. Changes only on discrete events (war, treaty, diplomacy).

### Mask Hierarchy

```
χ_c^sov[state_region]        — binary, territorial ownership
χ_c^mkt[market, good]        — observable prices (own market + trade partners)
χ_c^int[state_region]        — fog of war, continuous [0, 1]
```

### Use Cases

**Human player UI**: Render only `V_c[t]` — own territory in full detail, foreign territory masked.

**AI agent**: Observation is `V_c[t]` — partial observability. Action space scoped by χ_c^sov. This is the standard multi-agent POMDP setup for RL-based AI.

**Economic simulation**: The tick Φ always runs on the **full unmasked S[t]** — physics doesn't care about fog of war. Markets span country boundaries.

## Summary

```
Θ_i                          — invariant operators, loaded once (GPU constant memory)
Θ_u[t]                       — user-configurable parameters (player choices)
S[t] ∈ ℝ^N                  — universal state, only independent degrees of freedom
Φ(S, Θ_i, Θ_u): S[t] → S[t+1] — the tick, piecewise-linear, sparse Jacobian
Π_x · S[t]                  — structural projections (buildings, pops, prices, ...)
g(Π · S[t], Θ)              — derived quantities (production, GDP, profit, ...)
χ_c[t] ⊙ Π · S[t]          — per-country observable view
J = ∂Φ/∂S                   — Jacobian, piecewise-constant, sparse
```

Simulation runs on S.
Presentation and AI run on masked projections.
Everything that can be derived is derived, never stored.
