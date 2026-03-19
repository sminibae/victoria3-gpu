# victoria3-gpu

A clean-room, GPU-accelerated economic simulator that replicates Victoria 3's economic mechanics using only publicly available data.

Not a mod, clone, or derivative of the binary. This is a **research project**: can a single-threaded grand strategy simulation be reimplemented as vectorized tensor operations on the GPU?

---

## Motivation

Victoria 3 runs its economic simulation on a single CPU core (Clausewitz / Jomini engine). As a game progresses, thousands of POPs, hundreds of buildings, and dozens of interconnected markets interact every tick. The simulation slows noticeably over time because it is fundamentally sequential.

The core hypothesis:

> Most of that simulation is embarrassingly parallel. Market clearing, POP demand, building output, and wage computation are large matrix operations over a structured state space. A GPU can run these orders of magnitude faster. A boundary approximation model can also replace per-agent tracking with bulk inflow/outflow calculations at cell interfaces, borrowing from finite-volume methods in physics.

The tick loop, expressed as tensors:

```text
output = production_matrix @ building_state       # building throughput
demand = consumption_matrix @ POP_state           # POP demand
market_state = solve_equilibrium(output, demand)  # iterative CUDA kernel
POP_state = update_wealth(wages, need_satisfaction)
building_state = update_investment(profit_margins)
```

---

## Legal and Ethical Scope

This project uses **only publicly available data**. The binary is never touched.

| Allowed | Not Allowed |
|---|---|
| Game script files (`.txt`) that Paradox deliberately exposes | Disassembling or decompiling `victoria3.exe` |
| Official wiki formulas (`vic3.paradoxwikis.com`) | Distributing game assets |
| Developer diaries and blog posts | Creating derivative works of the binary |
| Community modding documentation | Bypassing DRM |
| Building an independent research simulator | Distributing a Victoria 3 replacement |

Everything in this repo must be reproducible from public data only, without owning or running the game.

---

## Architecture

Two core ideas drive the design:

**1. GPU offloading** — Per-entity computations (POP demand, building output, wage calculation) are independent across entities and map naturally to GPU parallelism.

**2. Boundary approximation** — Instead of tracking every individual POP and building, model the economy as flows across a grid. Only compute inflow/outflow at the boundaries between market regions, population strata, and supply-demand zones. This is analogous to finite-volume methods in computational fluid dynamics.

```
Data Layer          Model Layer            Solver Layer
Script Parser  -->  Economic State Graph   CPU: Main tick loop
Wiki Scraper        POP Tensor         --> GPU: Parallel compute
Dev Diary Corpus    Market Matrix
                    Flow Grid
```

---

## Project Structure

```
victoria3-gpu/
├── data/
│   ├── raw/                # Raw game scripts (bring your own copy)
│   ├── parsed/             # Structured JSON/Parquet output from parser
│   └── wiki/               # Scraped wiki pages and extracted formulas
├── src/
│   ├── parser/             # Paradox .txt script file parser
│   ├── scraper/            # Wiki and dev diary scraper
│   ├── model/              # Economic model (CPU reference implementation)
│   │   ├── market.py
│   │   ├── pops.py
│   │   ├── buildings.py
│   │   └── tick.py
│   ├── gpu/                # GPU-accelerated kernels
│   │   ├── market_solver.py
│   │   └── pop_demand.py
│   └── boundary/           # Boundary approximation layer
│       ├── grid.py
│       └── flux.py
├── tests/
│   ├── unit/               # Per-equation correctness tests
│   └── scenarios/          # Full scenario validation
└── notebooks/
    ├── 01_data_exploration.ipynb
    ├── 02_model_validation.ipynb
    └── 03_benchmarks.ipynb
```

---

## Development Phases

| Phase | Goal | Deliverable |
|---|---|---|
| **0** | Data collection — parse scripts, scrape wiki, index dev diaries | `data/` corpus |
| **1** | Formalize the economic model as mathematical equations | `docs/economic_model.md` |
| **2** | Vectorization design — tensor layouts, GPU ops, boundary approx spec | `docs/vectorization_design.md` |
| **3a** | CPU reference implementation (correctness baseline) | Working Python simulator |
| **3b** | GPU-accelerated tick | Benchmark: ticks/sec vs. CPU |
| **3c** | Boundary approximation implementation | Accuracy vs. speed tradeoff |
| **4** | Validation against known Victoria 3 scenarios | Validation report |
| **5** | Research report | `docs/research_report.md` |

---

## Data Sources

All simulation parameters come from files Paradox deliberately exposes or publicly documents:

- **`common/defines/00_defines.txt`** — simulation constants (tick rate, market elasticity, decay coefficients)
- **`common/goods/`** — tradeable goods, base prices
- **`common/buildings/`** — building types, input/output goods
- **`common/production_methods/`** — per-method throughput ratios
- **`common/pop_types/`** — POP categories, wage structure
- **`common/buy_packages/`** — consumption baskets per wealth level
- **`common/script_values/`** — derived computation formulas
- **vic3.paradoxwikis.com** — market formulas, MAPI, POP needs
- **Paradox developer diaries** — system design intent, balance passes

> You need to supply your own copy of the game scripts. This repo does not and will not distribute game files.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Prototyping | Python |
| GPU kernels | PyTorch (CUDA); custom CUDA/Vulkan as needed |
| Data processing | Polars, NumPy, Apache Arrow |
| Visualization | Matplotlib, Plotly |
| Performance target | Rust or C++ for the final solver |

---

## Success Criteria

1. CPU reference simulator within **10%** of actual Victoria 3 game values for standard scenarios
2. GPU acceleration achieves **at least 5x speedup** over the CPU reference
3. Boundary approximation retains **at least 90% accuracy** vs. full agent simulation at **3x speedup**
4. Full pipeline reproducible from **public data only**

---

## Open Research Questions

- **Market solver convergence**: What iterative method converges fastest for 100+ interconnected markets on a GPU?
- **Temporal stability**: Does the boundary approximation stay stable over long time horizons, or does numerical drift accumulate?
- **POP heterogeneity**: How much within-stratum variation is needed for accurate macro behavior?
- **Trade flow modeling**: Can inter-market trade fold into the same GPU pass as domestic markets, or must it run sequentially?
- **Event shocks**: How do discrete, non-differentiable events (wars, famines, political upheaval) interact with an otherwise smooth field model?

---

## Status

Currently in **Phase 0** — building the data collection and parsing pipeline.

---

## Contributing

This is a research project in early stages. If you are interested in economic simulation, GPU computing, or Paradox game mechanics, feel free to open an issue or discussion.

Please do not submit contributions that involve decompiled binary code or distributed game assets.

---

## License

TBD. The research code will be open source. Game data is owned by Paradox Interactive and is not included in this repository.
