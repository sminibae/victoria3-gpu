# User Actions & GPU Pipeline Design

> See [03_state_space_framework.md](03_state_space_framework.md) for the state-space formulation this builds on.

## The Problem

The time-state framework defines a clean simulation loop:

```
S[t+1] = Φ(S[t], Θ_i, Θ_u[t])
```

But Victoria 3 is a game — the player builds, legislates, trades, declares war. Where do these actions enter the math?

## Rejected: Direct State Mutation

The naive approach lets the player write directly into S[t]:

```
S[t] → S[t] + Δ(user_action)     # player pokes state
S[t+1] = Φ(S[t], Θ)              # then simulation runs
```

This breaks the invariant that Φ is the sole authority on state transitions. Two writers to S means side effects, ordering dependencies, and lost structural guarantees (linearity, Jacobian analysis, skip-ahead).

## Adopted: Actions as Parameters of Φ

### Core Insight

Every player action can be rewritten as setting a parameter that Φ reads and resolves. The player never touches the economic state directly — they configure the simulation's behavior, and Φ handles consequences.

In the real game, this is already how most things work: you queue construction (flag), select a production method (flag), enact a law (flag), declare war (flag). The simulation processes these over subsequent ticks.

### The Θ_i / Θ_u Split

The original invariant operators Θ split into two:

```
Θ_i  — truly invariant (game engine rules, never change)
Θ_u  — user-configurable parameters (player choices that shape Φ)
```

The clean formulation:

```
S[t+1] = Φ(S[t], Θ_i, Θ_u[t])
```

- **Φ** is a fixed function — its code never changes
- **Θ_i** is loaded once, lives in GPU read-only memory
- **Θ_u[t]** is the player-writable parameter space, updated between ticks
- **S[t]** is the economic state, written only by Φ

### Write Authority — No Overlap

| Tensor | Writer | When |
|--------|--------|------|
| Θ_i | Nobody | Loaded at game start, immutable |
| Θ_u[t] | Player only | Between ticks |
| S[t] | Φ only | During tick evaluation |

Three tensors, three write authorities, zero overlap.

### Persistent vs. Impulse Parameters

Two sub-tensors within Θ_u:

| Type | Behavior | Examples |
|------|----------|----------|
| `Θ_mode` | Persistent — stays set until changed | PM selection, law choice, tariff policy |
| `Θ_impulse` | One-shot — Φ reads, executes, then zeros out | Construction order, war declaration |

### Concrete Split

**Θ_i (truly invariant)**

| Operator | Shape | Description |
|----------|-------|-------------|
| `P_io[pm, good]` | 200 × 49 | I/O coefficients per PM option |
| `P_emp[pm, pop_type]` | 200 × 15 | Employment slots per PM option |
| `C_needs[pop_need, good]` | ~20 × 49 | Consumption baskets |
| `G_base[good]` | 49 | Base prices |
| `State_adjacency[state, state]` | 730 × 730 | Map topology (sparse) |
| `State_resources[state, resource]` | 730 × k | Arable land, coal deposits |
| `Tech_DAG[tech, tech]` | 100 × 100 | Tech prerequisite graph |
| `Sim_constants` | ~100 scalars | PRICE_RANGE, MAX_WAGE_STEP, etc. |

**Θ_u[t] (player-configurable)**

| Parameter | Shape | Type |
|-----------|-------|------|
| `active_PM_selection[state, building, PM_group, PM_option]` | sparse one-hot | Persistent |
| `law_selection[country, law_group, law_option]` | sparse one-hot | Persistent |
| `tariff_policy[country, good]` | continuous | Persistent |
| `tax_policy[country, level]` | one-hot | Persistent |
| `trade_route_active[country, market, good]` | binary | Persistent |
| `research_selection[country, tech]` | binary | Persistent |
| `construction_queue[state, building_type]` | binary | Impulse |

## Rejected Alternative: Action as Global Operator on Φ

Another approach considered: define a user action operator A that transforms Φ itself:

- **Additive**: `Φ' = Φ + A_user` — sparse correction matrix
- **Multiplicative**: `Φ' = A_user · Φ` — near-identity transformation

**Why rejected**: Φ in the linear regime is the matrix A in `S[t+1] = A·S[t] + b`. The global matrix has dimension N×N where N ≈ 1.3M — that's ~10¹² entries, impossible to materialize.

In practice, Φ is a composition of sparse sub-operators:

```
Φ = Φ_wages ∘ Φ_wealth ∘ Φ_prices ∘ Φ_demand ∘ Φ_production
```

User actions don't modify the global Φ — they modify the *input parameters* of specific sub-operators. The Θ_u parameterization achieves the same effect without ever constructing a global matrix.

## GPU Pipeline

### Sub-operator Breakdown

| Sub-operator | Operation | GPU-friendly? |
|-------------|-----------|:---:|
| `Φ_production` | `P_io @ Θ_u.active_PM @ S.building_levels` | Yes — sparse matmul, parallel per state |
| `Φ_demand` | `C_needs @ S.pop_count`, aggregate by market | Yes — matmul + reduction |
| `Φ_prices` | Equilibrium solver | Needs approximation (see below) |
| `Φ_wages` | `clamp(α · profit_margin, -max, +max)` | Yes — element-wise |
| `Φ_wealth` | `f(income - buy_package_cost)` | Yes — element-wise per POP group |
| `Φ_construction` | `process(Θ_u.construction_queue, S.treasury)` | Yes — sparse updates |
| `Φ_migration` | `M_adjacency · SoL_diff` | Yes — sparse matvec on state graph |

Everything except price solving is standard GPU linear algebra.

### The Price Solver Problem

Price equilibrium is the one iterative, potentially sequential bottleneck:

```
find prices such that: supply(prices) ≈ demand(prices)
```

Supply depends on prices (through profitability), demand depends on prices (through substitution). This cannot be solved in one matmul.

### Price Solver Options (Ranked by GPU Friendliness)

**Option 1 — Linearized single-step** (most GPU-friendly, least accurate)

```
Δprices ≈ K · (supply - demand)
```

K is a diagonal sensitivity matrix from Sim_constants. One element-wise multiply. The entire tick becomes one GPU kernel chain with zero CPU round-trips.

**Option 2 — Fixed-iteration Jacobi solver** (good balance)

Run k iterations (k = 5–10) of parallel price adjustment where each good adjusts independently based on its own excess supply/demand. Each iteration is element-wise parallel. Victoria 3 likely uses something similar.

**Option 3 — Batched Newton's method** (most accurate, most complex)

Compute Jacobian of excess demand w.r.t. prices. Since markets are mostly independent (coupled only through trade routes), J is block-sparse. Each block is small (49 goods per market). Batch-solve ~200 small linear systems in parallel on GPU.

### Recommended Strategy

Start with Option 1 for prototyping (Phase 3a/3b). If validation shows it isn't accurate enough, swap in Option 2 or 3. The architecture doesn't change — only one sub-operator gets more internal iterations.

### Full Tick Pipeline

```
Θ_u[t] ← player input                          # CPU: small tensor write
                                                  #
output     = P_io @ Θ_u.active_PM @ S.bld_levels # GPU: sparse matmul
demand     = C_needs @ S.pop_count                # GPU: sparse matmul
supply     = aggregate(output, by=market)         # GPU: reduction
Δprices    = K · (supply - demand)                # GPU: element-wise
profit     = revenue - input_cost - wages         # GPU: element-wise
Δwages     = clamp(α · profit, -max, +max)        # GPU: element-wise
Δwealth    = f(income - buy_cost)                 # GPU: element-wise
Δbuilding  = process(Θ_u.queue, S.treasury)       # GPU: sparse update
Δpop       = M_adj · SoL_diff                     # GPU: sparse matvec
                                                  #
S[t+1]     = S[t] + [Δprices, Δwages, ...]       # GPU: element-wise add
```

One CPU→GPU transfer (Θ_u update), then a chain of GPU kernels, then one GPU→CPU readback (if needed for display). No mid-tick CPU round-trips.

## Open Questions

1. **Impulse clearing**: Should Φ zero out impulse flags, or does the game loop handle it between ticks? If Φ does it, the write-authority invariant gets muddied. If the game loop does it, there's a tiny CPU step between ticks.

2. **Multi-player**: With multiple players, Θ_u gains a player dimension. Do conflicting writes get resolved before Φ runs, or does Φ handle conflict resolution?

3. **AI as player**: AI countries should write to Θ_u through the same interface as human players: `AI(V_country[t]) → Θ_u_update`, reading only the masked observation χ_c.

4. **Price solver accuracy**: How many Jacobi iterations are needed before GDP and SoL converge to within 5% of the game's values? This is the key empirical question for Phase 4.
