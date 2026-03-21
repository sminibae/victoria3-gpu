# Project Plan

## Vision

Build an independent, GPU-accelerated economic simulator that replicates the core mechanics of Victoria 3's economy — using only publicly available data — and test whether a vectorized, boundary-approximation approach can overcome the single-threaded performance ceiling of the Clausewitz engine.

This is not a clone or a mod. It is a research simulator.

## Legal Scope

| Allowed | Not Allowed |
|---------|-------------|
| Reading game script files (`.txt`) you own | Disassembling / decompiling `victoria3.exe` |
| Using Paradox wiki formulas | Distributing game assets |
| Reading dev diary blog posts | Creating derivative works of the binary |
| Community modding documentation | Bypassing DRM |
| Building an independent simulator | Distributing a Victoria 3 replacement |

The clean-room rule: **never touch the binary.**

## Data Sources

### 1. Game Script Files (Highest Priority)

Located in `Steam/steamapps/common/Victoria 3/game/`.

| Directory | Contents |
|-----------|----------|
| `common/defines/00_defines.txt` | Simulation constants (tick rate, decay, elasticity) |
| `common/goods/` | Tradeable goods, base prices, weight |
| `common/buildings/` | Building types, input/output goods |
| `common/production_methods/` | Per-method ratios, workforce requirements |
| `common/pop_types/` | POP categories, wage structure |
| `common/buy_packages/` | Consumption baskets per wealth level |
| `common/script_values/` | Derived computation formulas |

### 2. Official Wiki

`vic3.paradoxwikis.com` — key pages: Market, Goods, Needs, Buildings, Infrastructure, Trade.

### 3. Developer Diaries

Over 150 dev diaries at `paradoxinteractive.com` and `forum.paradoxplaza.com`. Priority: DD #1–10 (economy philosophy), DD #57 (system overview), DD #78–90 (post-launch balance).

### 4. Modding Community

GitHub repos, Paradox forum User Mods section, Reddit r/victoria3, Steam guides, Victoria 3 modding Discord.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      victoria3-gpu                       │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Data Layer  │  │  Model Layer │  │ Solver Layer  │  │
│  │              │  │              │  │               │  │
│  │ Script Parser│─▶│ Economic     │─▶│ CPU: Main     │  │
│  │ Wiki Scraper │  │ State Graph  │  │  tick loop    │  │
│  │ DD Corpus    │  │              │  │               │  │
│  └──────────────┘  │ POP Tensor   │  │ GPU: Parallel │  │
│                    │ Market Matrix│  │  compute      │  │
│                    │ Flow Grid    │  │               │  │
│                    └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Phases

### Phase 0: Data Collection

Build the ground-truth knowledge base before writing simulation code.

- **0.1 Script Parser** — Parse Paradox `.txt` files into structured JSON. Target: all `common/` files.
- **0.2 Wiki Scraper** — Scrape formula-containing pages. Store as markdown with extracted equations.
- **0.3 Dev Diary Corpus** — Download all dev diaries. Index by topic (economy, POP, market, performance).
- **0.4 Community Knowledge** — Curate external analysis, empirical measurements, and modding tools.

**Deliverable**: `data/` corpus + knowledge base reference.

### Phase 1: Economic Model Formalization

Translate parsed data into precise mathematical equations.

- **1.1 Goods & Market** — Price equilibrium from MAPI. Supply curve (buildings) and demand curve (POP needs).
- **1.2 POP Demand** — Consumption baskets by wealth level. Substitution behavior.
- **1.3 Building Production** — Throughput per production method. Profit margin calculation.
- **1.4 Employment & Wages** — Employment distribution. Wage determination (subsistence floor, market-clearing).
- **1.5 Dependency Graph** — Explicit DAG of one tick's computation. Identify parallel vs. sequential nodes.

**Deliverable**: Full mathematical specification with all equations.

### Phase 2: Vectorization Design

Redesign computation for GPU and batch processing.

- **2.1 State Tensor Design** — Define `POP_state`, `building_state`, `market_state`, `flow_state` layouts.
- **2.2 Tick as Tensor Ops** — Rewrite the tick as: sparse matmul → reduction → element-wise → sparse matvec.
- **2.3 Boundary Approximation** — Divide economic space into grid cells. Track only flux at boundaries.

**Deliverable**: Tensor layouts, operation breakdown, boundary approximation spec.

### Phase 3: Prototype Implementation

- **3a CPU Reference** — Full tick loop in pure Python. Correctness baseline.
- **3b GPU-Accelerated Tick** — Port parallel parts to PyTorch/CUDA. Benchmark ticks/sec.
- **3c Boundary Approximation** — Implement flux-grid model. Measure accuracy vs. speed tradeoff.

**Deliverable**: Working Python prototype with benchmarks.

### Phase 4: Validation

- **4.1 Unit** — Each equation matches wiki formula for known inputs.
- **4.2 Scenario** — Standard scenarios (e.g. 1836 Britain) within 10% of game values.
- **4.3 Stability** — 100 in-game years without divergence, oscillation, or collapse.

**Deliverable**: Validation report with charts and error analysis.

### Phase 5: Research Report

- Does GPU offloading give meaningful speedup?
- How accurate is boundary approximation at various grid coarsening levels?
- What is the minimal sequential computation that must remain on CPU?

**Deliverable**: Final research report.

## Technology Stack

| Layer | Tool |
|-------|------|
| Language | Python (prototyping) → Rust or C++ (performance) |
| GPU | PyTorch (CUDA); possibly custom CUDA/Vulkan later |
| Data | Polars / NumPy / Arrow |
| Visualization | Matplotlib / Plotly |

## Success Criteria

1. CPU reference within **10%** of actual Victoria 3 game values for standard scenarios
2. GPU acceleration **≥ 5x** speedup over CPU reference
3. Boundary approximation **≥ 90%** accuracy vs. full agent sim at **3x** speedup
4. Full pipeline reproducible from **public data only**

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Wiki formulas incomplete or outdated | Cross-reference with script files; note discrepancies |
| Boundary approximation loses too much fidelity | Keep full agent model as fallback; tune grid resolution |
| GPU memory limits at large state tensors | Tile computation; evaluate sparse representations |
| Market solver diverges | Start with known-converging methods; add damping |
| Undocumented engine mechanics | Accept uncertainty; validate empirically against game replays |

## Open Research Questions

1. **Market solver convergence** — What iterative method converges fastest on GPU for 100+ interconnected markets?
2. **Temporal stability** — Is boundary approximation stable over long horizons, or does numerical drift accumulate?
3. **POP heterogeneity** — How much within-stratum heterogeneity is needed for macro accuracy?
4. **Trade flow modeling** — Can inter-market trade fold into the same GPU pass as domestic markets?
5. **Event system** — How to handle discrete shocks in an otherwise smooth field model?
