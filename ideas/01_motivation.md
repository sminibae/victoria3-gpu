# Motivation

## The Performance Problem

Victoria 3 simulates a global economy across a century of industrialization (1836–1936). Every weekly tick, the game evaluates thousands of population units, hundreds of buildings, dozens of interconnected markets, trade routes, wages, consumption, and investment decisions. All of this runs on the Clausewitz engine — single-threaded, on one CPU core.

The result is familiar to any player: the early game runs smoothly, but as the world industrializes and the number of economic actors grows, the simulation slows to a crawl. By the 1900s, running at maximum speed can feel like watching paint dry.

This is not a bug. It is an architectural ceiling. The engine processes economic actors sequentially, and the workload grows linearly with game complexity. No amount of hardware improvement changes the fundamental bottleneck.

## The Hypothesis

Most of Victoria 3's per-tick computation is structurally parallel. Building output is independent across buildings. POP demand is independent across population groups. Wage updates are independent across employers. Price adjustments are independent across goods. These are not inherently sequential operations — they are matrix multiplications, element-wise transforms, and sparse reductions. They are tensor operations.

The hypothesis of this project is twofold:

1. **GPU offloading**: The bulk of per-entity calculations (demand, production, wages, wealth updates) can be expressed as vectorized tensor operations and offloaded to the GPU, where thousands of cores process them in parallel.

2. **Boundary approximation**: Instead of tracking every individual POP and building as discrete agents, the economy can be modeled as flows through a continuous field — computing only the flux at boundaries between market regions, wealth strata, and supply-demand equilibria. This is the same idea as finite-volume methods in computational physics, applied to economic simulation.

If both hold, the same economic model that bogs down a single CPU core could run orders of magnitude faster on a GPU — not by simplifying the model, but by executing it in the architecture it was always suited for.

## The Legal Constraint

Victoria 3's binary (`victoria3.exe`) is compiled C++ (Clausewitz/Jomini engine). Paradox's EULA explicitly prohibits disassembly, decompilation, and reverse engineering of the binary.

This project obeys that constraint completely. **The binary is never touched.** All knowledge comes from publicly available sources:

- **Game script files** (`.txt`) — Paradox deliberately exposes these for modding. They contain building definitions, production methods, goods, POP types, consumption baskets, simulation constants, and more. These are effectively the specification of the economic model.
- **Official wiki** (`vic3.paradoxwikis.com`) — Community-maintained documentation of game formulas, including price equilibrium, market access, and substitution logic.
- **Developer diaries** — Over 150 blog posts where Paradox developers explain system design decisions, economic model philosophy, and simulation architecture.
- **Modding community** — Extensive documentation, analysis tools, and empirical measurements from the modding community.

This is a clean-room re-implementation: an independent simulator built from public data, not a derivative of the binary. The goal is not to clone Victoria 3, but to answer a research question: can this class of economic simulation be made dramatically faster through GPU acceleration and mathematical reformulation?

## What This Project Is

A research project. A clean-room, GPU-accelerated economic simulator that replicates Victoria 3's economic mechanics using only publicly available data. It is not a mod, not a clone, and not a derivative of the binary.

The core deliverables are:
- A mathematical formalization of the economic model
- A CPU reference implementation for correctness validation
- A GPU-accelerated implementation for performance comparison
- A boundary approximation layer for accuracy-vs-speed tradeoff analysis
- A research report documenting findings

---

## Appendix: Original Conversation

The following is the original conversation with claude opus4.6 (in Korean) that sparked this project. It covers the initial exploration of whether reverse engineering Victoria 3 is feasible, the legal constraints, and how the idea evolved into a clean-room GPU acceleration project.

---

궁금한게 있는데,
내가 싱글플레이가 되는 게임을 플레이한다고 했을 때
일단 내 컴퓨터에 그 게임에 대한 파일이 거의 다 가지고 있을 것 같은데
그냥 코드를 보거나 리버스 엔지니어링 같은걸로 원래 코드를 복원할 수 있나?

> 좋은 질문이에요. 간단히 말하면, 완전한 원본 소스코드 복원은 사실상 불가능하지만, 어느 정도의 분석은 가능합니다.
>
> **왜 완전 복원이 어려운가?**
>
> 게임을 설치하면 컴퓨터에 있는 건 컴파일된 바이너리(기계어)입니다. 컴파일 과정에서 변수명, 함수명, 주석, 코드 구조 같은 정보가 대부분 사라져요. 마치 케이크를 보고 정확한 레시피를 역추적하려는 것과 비슷합니다. 대략적인 재료는 알 수 있지만, 원래 레시피를 그대로 복원하긴 어렵죠.
>
> **그래도 할 수 있는 것들**
>
> 디컴파일러(Ghidra, IDA Pro 등)를 쓰면 기계어를 C 같은 코드로 대략 변환할 수 있어요. 다만 변수명은 `var_1`, `func_0042` 같은 의미 없는 이름이 되고, 원래의 설계 의도나 구조는 알기 어렵습니다. 그래서 "읽을 수 있는 코드"라기보다는 "분석 가능한 수준"에 가깝습니다.
>
> **언어에 따라 난이도가 크게 다릅니다**
>
> C/C++로 만든 게임은 복원이 가장 어렵고, 반대로 Unity(C#)나 Java 기반 게임은 메타데이터가 많이 남아 있어서 거의 원본에 가까운 코드를 볼 수 있는 경우도 있어요. 그래서 Unity 게임들은 모딩이 활발한 편이기도 하고요.
>
> **실제로 이런 일이 일어나기도 해요**
>
> 유명한 사례로, 팬 커뮤니티가 리버스 엔지니어링으로 오래된 게임의 코드를 재구성해서 비공식 포트나 모드를 만드는 경우가 있습니다. 다만 이건 수많은 사람이 수년간 노력한 결과이지, 혼자 쉽게 할 수 있는 건 아니에요.
>
> 참고로, 대부분의 게임은 이용약관에서 리버스 엔지니어링을 금지하고 있어서 법적인 부분도 고려해야 합니다.

아하 그럼 paradox interactive 의 victoria3에 대해서
1. 법적으로 금지되어있는지,
2. 어떤 언어로 만들었는지
3. 변수명과 주석이 없어지더라고 분석가능한 수준까지 갈 수 있을지
알려줘

> **1. 법적으로 리버스 엔지니어링이 금지되어 있는가?**
>
> 네, Paradox EULA는 소스코드를 역추출하거나, 디스어셈블, 디컴파일, 파생 저작물을 만드는 행위를 명시적으로 금지하고 있습니다. 다만 단서가 하나 있는데, "applicable law에 의해 허용되는 경우는 제외"라는 문구가 붙어 있어요. 예를 들어 EU에서는 호환성 확보를 위한 리버스 엔지니어링이 법적으로 보장되는 경우가 있어서, EULA가 이를 완전히 막지는 못합니다. 하지만 일반적인 호기심이나 학습 목적이라면 EULA 위반에 해당할 수 있어요.
>
> **2. 어떤 언어로 만들었는가?**
>
> Victoria 3는 Paradox의 자체 엔진인 Clausewitz 엔진(정확히는 그 개선판인 Jomini 엔진)으로 제작되었고, 이 엔진은 C++로 작성되었습니다. 다만 게임 로직의 상당 부분은 Paradox 자체 스크립팅 언어로 작성되어 있어서, 모딩 커뮤니티가 텍스트 에디터만으로도 수정할 수 있는 구조입니다.
>
> **3. 분석 가능한 수준까지 갈 수 있을지?**
>
> C++로 컴파일된 바이너리이기 때문에, 복원 난이도가 가장 높은 축에 속합니다. 다만 Victoria 3의 경우 흥미로운 점이 있는데, 게임의 핵심 로직 상당 부분이 C++ 바이너리가 아니라 평문 스크립트 파일로 되어 있다는 거예요. 게임 폴더의 `game/` 디렉토리 안에 있는 `.txt` 파일들을 열어보면 건물 생산성, 법률 효과, AI 전략 같은 것들을 그냥 읽을 수 있습니다.
>
> 정리하면, **엔진 자체의 C++ 코드**는 리버스 엔지니어링이 매우 어렵지만, **게임 로직과 데이터**는 이미 상당 부분 평문으로 노출되어 있어서 별도의 리버스 엔지니어링 없이도 분석이 가능합니다.

내가 하고 싶은건
Clausewitz 엔진이 아마 싱글코어로 돌아가는 걸로 알고있어.
그런데 사실 victoria3를 플레이해보면 알겠지만
정말 많은 데이터를 연산해야하고, 게임 플레이 시간이 오래지속되면 게임 내 진행속도가 너무 느려져.

그런데 아무리 생각해도 대부분 텐서 연산일것 같고, 이런 부분은 최대한 gpu로 떠넘기고, 진짜 병렬화 불가능한 메인 트리 워킹만 cpu가 하고, 나머지는 gpu로 넘기거나,

추상적인 벡터공간으로 모든 연산을 변환한 다음에, 거기서는
모든 입자를 추적하는게 아니라 grid의 boundary에서만 inflow, outflow를 계산하는 그런식으로 우회할 수 있을것 같단 말이지

이런 목적으로 시도해보는건 괜찮을까?

> 기술적으로 아이디어 자체는 상당히 합리적입니다. Victoria 3의 경제 시뮬레이션은 본질적으로 수천 개의 POP과 수백 개의 건물, 상품 시장 간의 대규모 행렬 연산에 가깝죠. GPU로 떠넘길 수 있는 부분이 분명히 있다는 직관은 맞습니다.
>
> 경계면 inflow/outflow만 추적하는 접근도 물리 시뮬레이션에서 실제로 쓰이는 기법(유한체적법 등)이라, 경제 시뮬레이션에 적용해보겠다는 발상이 재미있어요.
>
> 다만 법적 측면에서, EULA가 리버스 엔지니어링을 금지하고 있어요. 엔진 자체를 건드리기보다는, 공개된 스크립트 파일과 위키의 수식 정보를 바탕으로 Victoria 3의 경제 시뮬레이션을 독립적으로 재구현하는 방향이 더 현실적이고 법적으로도 안전합니다.
>
> 요약하면, 바이너리를 뜯는 방식보다는 공개 데이터 기반으로 독립 시뮬레이터를 만들어서 GPU 가속과 근사 기법을 실험해보는 게 기술적으로도 법적으로도 훨씬 나은 경로라고 생각해요.

오호 그럼 바이너리를 뜯어보기도 하고,
이는 참고만하고 더 나은 엔진을 만들어보는건 괜찮다 이거네?

> 음, 그건 좀 주의가 필요한 부분이에요.
>
> "바이너리를 뜯어서 참고하고 새로 만든다"는 것은 클린룸 방식이 아닙니다. 클린룸 리버스 엔지니어링이라는 건, 바이너리를 분석하는 사람과 새로 코드를 작성하는 사람이 완전히 분리되어야 하는 거예요. 한 사람이 바이너리를 보고 그 지식을 가지고 새로 작성하면, 법적으로 "파생 저작물"로 간주될 수 있습니다.
>
> 제가 앞서 제안한 건 조금 다른 방향이었어요. 바이너리는 건드리지 않고, 이미 공개된 정보만으로 독립 시뮬레이터를 만드는 거죠. 공개 스크립트와 위키 수식을 바탕으로 경제 모델을 이해하고, 그 모델을 GPU 가속이 가능한 형태로 재설계해서 독립 시뮬레이터를 만드는 겁니다.
>
> 바이너리 분석은 매력적이지만, 그 경로를 택하는 순간 법적 리스크가 따라오기 때문에 피하는 게 낫다는 거예요.

오호 좋아 그러면 게임폴더의 스크립트 파일, 위키의 수식들, 개발자 일지에서 설명한 시스템 설계, 모딩 커뮤니티의 문서화된 지식 이런거는 어떻게 모을 수 있지?

> **1. 게임 폴더 스크립트 파일 (가장 핵심)**
>
> Victoria 3를 소유하고 있다면 바로 접근 가능합니다. 경로는 보통 `Steam/steamapps/common/Victoria 3/game/`이고, 주요 하위 폴더:
> - `common/buildings/` — 건물 정의, 투입/산출 상품
> - `common/production_methods/` — 생산 방식별 투입/산출 비율
> - `common/goods/` — 상품 기본 가격, 속성
> - `common/pop_types/` — POP 유형별 소비, 임금 구조
> - `common/buy_packages/` — 부유 수준별 소비 패키지
> - `common/defines/00_defines.txt` — 시뮬레이션 핵심 상수값 (매우 중요)
> - `common/script_values/` — 각종 계산 공식
>
> **2. 공식 위키 (vic3.paradoxwikis.com)**
>
> Market 페이지에는 수요-공급에 따른 가격 결정 공식, MAPI 계산법 등이 상세히 나와 있고, Needs 페이지에는 POP의 소비 패턴과 대체재 선택 공식이 정리되어 있습니다.
>
> **3. 개발자 일지 (Dev Diaries)**
>
> Paradox 공식 포럼과 웹사이트에 150편 이상의 개발자 일지가 있어요. 특히 초기 번호(#1~#57)에 경제 시스템 설계 철학이 자세히 나와 있습니다.
>
> **4. 모딩 커뮤니티 자료**
>
> GitHub, Paradox 공식 포럼, Reddit r/victoria3, Steam 커뮤니티 가이드, Victoria 3 모딩 Discord 등에 분산되어 있습니다.
