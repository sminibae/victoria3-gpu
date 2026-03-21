# victoria3-gpu

A clean-room, GPU-accelerated economic simulator that replicates Victoria 3's economic mechanics using only publicly available data.

**Core hypothesis**: Victoria 3's single-threaded economic simulation (Clausewitz engine) can be reimplemented as vectorized tensor operations on the GPU, achieving dramatic speedup without simplifying the model.

## Why This Exists

Victoria 3 simulates a global economy across 100 years of industrialization. Every weekly tick evaluates thousands of population units, hundreds of buildings, and dozens of interconnected markets — all on a single CPU core. By the late game, the simulation slows to a crawl.

But most of this computation is structurally parallel: building output, POP demand, wage updates, and price adjustments are all independent across entities. These are tensor operations trapped in a sequential loop.

This project asks: **what if we ran the same economic model on a GPU?**

Two approaches are explored:

1. **GPU offloading** — Express per-entity calculations as sparse matrix multiplications and element-wise transforms, then execute them on GPU.
2. **Boundary approximation** — Model the economy as flows through a continuous field (finite-volume style), computing only flux at boundaries rather than tracking every agent.

## The Math

The entire game state lives in a single vector **S[t]** (~1.3M floats, ~5MB), updated each tick by a piecewise-linear operator:

```
S[t+1] = Φ(S[t], Θ_i, Θ_u[t])
```

| Symbol | Meaning |
|--------|---------|
| S[t] | Universal state at tick t (buildings, pops, prices, treasury, tech) |
| Θ_i | Invariant game rules (production I/O, consumption baskets, map topology) |
| Θ_u[t] | Player choices (PM selection, laws, construction orders) |
| Φ | The tick function — a composition of sparse sub-operators |

Every subsystem is a **projection** of S through Θ. Nothing derived is ever stored.

The tick decomposes into GPU-friendly sub-operators:

```
output     = P_io @ Θ_u.active_PM @ S.building_levels   # sparse matmul
demand     = C_needs @ S.pop_count                       # sparse matmul
supply     = aggregate(output, by=market)                # reduction
Δprices    = K · (supply - demand)                       # element-wise
Δwages     = clamp(α · profit, -max, +max)               # element-wise
Δpop       = M_adjacency · SoL_diff                      # sparse matvec
S[t+1]     = S[t] + [Δprices, Δwages, ...]              # element-wise add
```

One CPU→GPU transfer per tick, then a chain of GPU kernels, then readback. No mid-tick CPU round-trips.

> Full mathematical framework: [ideas/03_state_space_framework.md](ideas/03_state_space_framework.md)
> GPU pipeline design: [ideas/04_action_and_gpu_design.md](ideas/04_action_and_gpu_design.md)

## Project Phases

| Phase | Goal | Status |
|-------|------|--------|
| 0 | Data collection — parse game scripts, scrape wiki, index dev diaries | In progress |
| 1 | Formalize economic model as math equations | — |
| 2 | Vectorization design — tensor layouts, GPU ops, boundary approximation | — |
| 3a | CPU reference implementation (correctness baseline) | — |
| 3b | GPU-accelerated tick | — |
| 3c | Boundary approximation implementation | — |
| 4 | Validation against known Victoria 3 scenarios | — |
| 5 | Research report | — |

## Data Sources

All knowledge comes from publicly available sources. **The binary is never touched.**

- **Game script files** — `.txt` files under `game/common/` (buildings, goods, production methods, defines)
- **Official wiki** — `vic3.paradoxwikis.com` (price formulas, MAPI, substitution logic)
- **Developer diaries** — 150+ posts explaining system design
- **Modding community** — GitHub tools, forum analysis, empirical measurements

> You need to supply your own copy of the game scripts. This repo does not and will not distribute game files.

## Technology Stack

| Layer | Tool |
|-------|------|
| Language | Python (prototyping) → Rust or C++ (performance) |
| GPU | PyTorch (CUDA); possibly custom CUDA/Vulkan later |
| Data | Polars / NumPy / Arrow |
| Visualization | Matplotlib / Plotly |

## Directory Structure

```
victoria3-gpu/
├── ideas/                # Design documents and research notes
│   ├── 00_notation.md
│   ├── 01_motivation.md
│   ├── 02_project_plan.md
│   ├── 03_state_space_framework.md
│   └── 04_action_and_gpu_design.md
├── data/
│   ├── raw/              # Parsed game scripts (user's own copy)
│   ├── parsed/           # Structured JSON/Parquet output
│   └── wiki/             # Scraped wiki pages and formulas
├── src/
│   ├── parser/           # Paradox .txt script file parser
│   ├── scraper/          # Wiki and dev diary scraper
│   ├── model/            # Economic model (CPU reference)
│   ├── gpu/              # GPU-accelerated kernels
│   └── boundary/         # Boundary approximation layer
├── tests/
├── notebooks/
└── logs/
```

## Success Criteria

1. CPU reference within **10%** of actual Victoria 3 game values for standard scenarios
2. GPU acceleration **≥ 5x** speedup over CPU reference
3. Boundary approximation **≥ 90%** accuracy vs. full agent sim at **3x** speedup
4. Full pipeline reproducible from **public data only**

## Open Research Questions

- **Market solver convergence**: What iterative method converges fastest for 100+ interconnected markets on a GPU?
- **Temporal stability**: Does the boundary approximation stay stable over long time horizons, or does numerical drift accumulate?
- **POP heterogeneity**: How much within-stratum variation is needed for accurate macro behavior?
- **Trade flow modeling**: Can inter-market trade fold into the same GPU pass as domestic markets?
- **Event shocks**: How do discrete, non-differentiable events interact with an otherwise smooth field model?

## Status

Currently in **Phase 0** — building the data collection and parsing pipeline.

## Contributing

This is a research project in early stages. If you are interested in economic simulation, GPU computing, or Paradox game mechanics, feel free to open an issue or discussion.

Please do not submit contributions that involve decompiled binary code or distributed game assets.

## Legal

This is a clean-room re-implementation. No game binaries are analyzed, decompiled, or reverse-engineered. All information comes from publicly exposed script files, official wiki, developer diaries, and community documentation. No game assets are distributed.

## License

[AGPL-3.0](LICENSE)
