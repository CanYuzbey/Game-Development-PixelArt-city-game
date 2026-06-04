# Development Method

## Production Goal

Build a Unity-ready deterministic open-world city generator that supports
streaming chunks, believable road hierarchy, bridge/turn metadata, lot-level
building assembly, sprite assignment, and gameplay hooks.

The generator must keep this placement order:

```text
land/sea -> highways -> roads -> bridges/turns -> buildings
```

## Scrum Structure

### Scrum A: Architecture And Runtime

Owns C# structure, Unity compatibility, allocation control, determinism, and
public contracts.

Current priorities:

- keep `MapGenerationPhase` as the source of truth for phase order,
- continue splitting `MapGenerator` into phase-owned partials or services,
- replace allocation-heavy traversal helpers with non-alloc grid utilities,
- keep runtime code independent from Unity main-thread APIs.

### Scrum B: World And City Planning

Owns world chunk planning, cross-chunk highways, future world-river splines, and
city believability.

Current priorities:

- maintain canonical chunk seed derivation,
- enforce highway edge constraints across adjacent chunks,
- keep random local rivers disabled for streamed world chunks until world-level
  river constraints are implemented,
- reserve curated profiles such as `barcelona_eixample` for authored districts.

### Scrum C: Rendering And Assets

Owns sprite registry consumption, road bitmask rendering, bridge/turn/intersection
visual contracts, building stack rendering, and atlas import.

Current priorities:

- consume `RoadRecord.bitmask` plus cell `road_turn`, `intersection`, and
  `bridge` metadata,
- map `spriteStack` records to Unity sprites/prefabs,
- build draw-order rules for isometric building footprints.

### Scrum D: QA And Tools

Owns smoke gates, seed regression tests, cache export validation, and performance
budgets.

Current priorities:

- extend full-grid deterministic hashing beyond stats checks,
- add allocation/time budgets for 256x256 chunks,
- add cross-chunk highway and future river-continuity regression seeds,
- validate JSON cache metadata: `world_seed`, `chunk_x`, `chunk_y`, `chunk_size`,
  and `algorithm_version`.

## Agile Cadence

Use one-week technical sprints until the Unity renderer is live.

Each sprint should include:

- one playable vertical slice task,
- one determinism or tooling task,
- one performance/structure cleanup task,
- one seed-regression review.

Definition of done:

- C# smoke gate passes,
- generated maps preserve phase order,
- no Unity main-thread dependency in pure generation,
- new output has either a regression test or a documented manual validation path.

## Current Implementation Decisions

- Single-map `MapGenerator` may still use local random rivers.
- `WorldGenerator.ConfigForChunk()` disables local rivers until world-level river
  spline constraints exist.
- Bridges are now finalized after highways and connector roads.
- Road turns and intersections are explicit cell metadata.
- World highway boundary constraints are applied during the highway phase and
  verified by smoke tests across adjacent chunks.
