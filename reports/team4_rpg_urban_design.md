# Team 4 — Senior Urban Game Design Committee Report
## Pixel-Art Open-World Urban RPG: Design Reference for the Coding Team

**Prepared by:** Senior Urban Game Design Committee  
**Date:** 2026-05-09  
**Audience:** Implementation team building a seed-based, tile-grid urban RPG (10 m/cell, 64×48–160×120 grids, turn-based card combat)  
**Companion reports:** Team 1 (Urban Morphology), Team 2 (Procedural Algorithms), Team 3 (Implementation Plan)

---

## Executive Summary

This report translates real urban structure (Teams 1–3) into playable RPG game design. It covers every layer the coding team needs to make a procedural city *feel* like a hand-crafted RPG world: tile roles, encounter zones, building variety, player navigation, pixel-art visual language, NPC/enemy spawning, landmark placement, and scale calibration. All recommendations are concrete, numbered, and directly implementable.

---

## 1. Tile Role Taxonomy for Urban RPGs

### 1.1 The Six Core Tile Categories

Every cell on the tile grid belongs to exactly one of six **gameplay-visible tile categories**. These categories drive collision, encounter logic, rendering, and NPC behavior — they are distinct from the zone system (CBD/Midtown/Residential) which is a spatial overlay.

| Category ID | Name | Walkable? | Encounter-eligible? | Typical % of map |
|---|---|---|---|---|
| `TILE_ROAD` | Road surface | Yes | Yes (random encounter zone) | 20–28% |
| `TILE_SIDEWALK` | Sidewalk / pavement | Yes | Yes (low rate) | 8–12% |
| `TILE_BUILDING` | Building footprint | No (solid obstacle) | No | 25–35% |
| `TILE_DOOR` | Building entrance | Yes (triggers script) | No (scripted only) | 0.5–1% |
| `TILE_PARK` | Park / green space | Yes | Yes (event encounters) | 6–10% |
| `TILE_WATER` | Water / canal / fountain | No | No | 2–5% |
| `TILE_ALLEY` | Back-alley | Yes | Yes (high rate) | 3–6% |
| `TILE_PLAZA` | Open plaza / market square | Yes | Yes (NPC scripted) | 2–4% |
| `TILE_RUIN` | Derelict / abandoned lot | Yes | Yes (high rate) | 1–3% |
| `TILE_TRANSIT` | Train/bus station platform | Yes | No (safe zone) | 0.5–1% |

**Implementation rule:** Store `tile_category` as an enum integer on `MapCell`. The zone system (`zone_id`) and tile category are orthogonal — a `TILE_ROAD` cell can exist in any zone; its encounter *rate* is then a product of both.

### 1.2 What Makes a City Feel Like a GAME City vs. a Simulation

Real cities are optimized for vehicles and logistics. Game cities must be optimized for **player agency and dramatic flow**. The key divergences:

**Game cities compress scale selectively.** Blocks that contain important content (a shop, a quest giver, a dungeon entrance) are made larger and more accessible. Filler blocks between landmarks are made narrow and fast to traverse. This is the opposite of simulation — Pokemon's Castelia City has extremely narrow streets (2–3 tiles) that funnel the player along a single axis toward the Gym, while the "interesting" piers are wide open.

**Game cities use tile category as communication.** The player reads the map through visual tile language, not a minimap. Dark asphalt = danger zone. Bright green = safe exploration. Stone plaza = scripted event incoming. This is covered in detail in Section 5.

**Game cities have curated "empty" space.** Real parks are often empty by design. Game parks contain hidden items, sleeping NPCs, rare encounter Pokémon, or environmental storytelling props. No tile should be placed without asking: "What does the player do here?"

**Specific rules for the coding team:**

1. **No dead-end roads without reward.** Any road tile that terminates without connecting to another road (from Team 1's cul-de-sac system) must have a `TILE_DOOR`, item chest, or NPC at its terminus. Dead ends with nothing are navigation punishment.

2. **Building footprint perimeter ≥ 3 tiles on at least one face.** Buildings smaller than 3×3 cells feel like props, not places. Minimum habitable building is 3×3 (one entrance side + two solid sides). Exception: corner shops and kiosks can be 2×2.

3. **Sidewalks are mandatory on arterial roads, optional on local streets.** Following Team 1's hierarchy: highway-adjacent cells always generate `TILE_SIDEWALK` on both sides (1-cell wide). Connector roads: sidewalk on one side only, or none in residential.

4. **Water is never walkable but is always adjacent to something interesting.** A `TILE_WATER` cell (canal, fountain basin, decorative pond) must have at least one `TILE_PARK`, `TILE_PLAZA`, or special NPC within 4 cells. Water with nothing near it is visual noise.

5. **Alleys connect to exactly two roads and are never longer than 12 cells.** Longer alleys become confusing. An alley > 12 cells should be broken by a junction or a mid-alley `TILE_PLAZA` node.

---

## 2. Encounter Zone Design

### 2.1 Where Encounters Happen

Urban RPG encounters follow a **three-type taxonomy** that maps directly to tile categories:

**Type A — Random Encounters (tile-triggered)**  
Player steps onto a tile; each step has a probability `P` of triggering a combat card encounter. This is the Pokemon grass-patch model applied to urban tiles.

**Type B — Event Encounters (proximity-triggered)**  
An NPC or enemy entity exists at a fixed or semi-fixed cell. Within 2–3 tiles, the player enters a detection radius and the encounter initiates. Used in markets, alleys, and story zones.

**Type C — Scripted Encounters (door/zone-triggered)**  
Entering a building, interacting with an object, or crossing a zone boundary triggers a predetermined encounter. Always involves named NPCs or boss enemies.

### 2.2 Encounter Probability by Tile and Zone

Base encounter probability per step (Type A). Applied every time the player moves to an eligible tile:

| Tile Category | CBD Zone | Midtown Zone | Residential Zone |
|---|---|---|---|
| `TILE_ROAD` (arterial) | 3% | 5% | 4% |
| `TILE_ROAD` (connector) | 6% | 8% | 6% |
| `TILE_SIDEWALK` | 1% | 2% | 1% |
| `TILE_ALLEY` | 18% | 22% | 15% |
| `TILE_PARK` | 8% | 6% | 4% |
| `TILE_RUIN` | 25% | 20% | 20% |
| `TILE_PLAZA` | 0% | 0% | 0% (Type B/C only) |
| `TILE_TRANSIT` | 0% | 0% | 0% (safe zone) |

**Cooldown rule:** After any encounter (win, lose, or flee), apply a **cooldown of 4 steps** during which `P = 0` on all tiles. This prevents encounter spam and respects player pacing. Store `steps_since_encounter` on the player state.

**Time-of-day modifier (optional but recommended):**  
If the game has a day/night cycle, multiply all `P` values by:
- Day (06:00–18:00): ×1.0
- Evening (18:00–22:00): ×1.5
- Night (22:00–06:00): ×2.5

This makes alleys terrifying at night and CBDs manageable by day — a natural urban RPG rhythm.

### 2.3 Encounter Density Design by District

**CBD / Downtown:**  
- Primary encounter type: Type B (gang territory markers, corporate enforcers, rival traders)  
- Secondary: Type A on connector roads (muggers, street criminals)  
- Parks: Type B events (political rally that turns hostile, shady deal gone wrong)  
- Target: player encounters ~1 Type A encounter every 12–18 road tiles moved

**Midtown:**  
- Primary: Type A on roads and alleys (most varied enemy types)  
- Secondary: Type B in markets (traders demanding toll, black market enforcers)  
- Target: player encounters ~1 Type A encounter every 8–12 road tiles moved (this is the "default" rhythm)

**Residential:**  
- Primary: Type B (territorial neighbor disputes, lost children scripted quests)  
- Type A rate is the lowest; this zone is recovery/exploration territory  
- Target: player encounters ~1 Type A encounter every 20–30 road tiles moved

**Implementation rule:** Compute `effective_encounter_probability` as:
```
P_eff = P_base[tile_category][zone_id] × time_modifier × cooldown_mask
```
Avoid per-cell random seeding — use the player's step counter and map seed combined as the RNG input so the same path walked twice yields different encounters.

---

## 3. Building Variety by Zone

### 3.1 CBD / Downtown Buildings

The CBD has the tallest, most imposing buildings. In pixel-art, "tall" is communicated by multi-row facades, dark windows in grid patterns, and narrow footprints relative to height visual cues.

| Building Type | Footprint (cells) | Door Count | Interior Type | Special Rules |
|---|---|---|---|---|
| Office Tower | 4×6 to 6×8 | 1–2 ground floor | Quest-giver floors, item shops | Always >4 tiles from another tower |
| City Hall / Civic Center | 8×6 to 10×8 | 2–4 grand entrances | Story anchors, permit offices | Unique per map; must be in CBD center block |
| Bank / Financial Institution | 4×4 to 5×5 | 1 (double-door style) | Item storage, loan mechanics | 1–3 per CBD |
| Market Square Building | 6×4 perimeter buildings enclosing 4×3 open plaza | 1 per face | Vendor stalls inside | Treated as building+plaza combo tile |
| Luxury Hotel | 5×7 to 6×9 | 2 | Inn mechanics (save, heal) | 1 per CBD; landmark |
| Police HQ | 5×5 | 2 | Safe zone, bounty board | 1 per map; CBD only |

**CBD building density target:** 55–65% of CBD land cells are building footprint. Roads + sidewalks account for 28–32%. Parks/plazas: 8–12%.

**Architectural pixel-art language for CBD:**
- Roof tiles: Dark grey `(60, 60, 70)` or near-black `(40, 40, 50)` to convey concrete/glass
- Window pattern: 2×1 or 1×2 pixel "dot" windows in `(180, 220, 255)` (blue-tinted glass) or `(255, 240, 180)` (lit interior, nighttime)
- Ground floor: Slightly lighter than upper floors — `(90, 85, 100)` — to show retail/lobby differentiation
- Building accent stripe (top floor or lintel): `(200, 170, 60)` gold trim for civic buildings; `(160, 60, 60)` red trim for commercial

### 3.2 Midtown Buildings

Midtown has the most variety. This is where the player spends the most time because it is the transition zone between the dramatic CBD and the quiet residential.

| Building Type | Footprint (cells) | Door Count | Interior Type | Special Rules |
|---|---|---|---|---|
| Shop / Boutique | 2×3 to 3×4 | 1 | Item purchase | 3–6 per midtown block |
| Restaurant / Diner | 3×3 to 4×4 | 1 | Heal mechanic, rumor NPCs | 2–4 per block |
| Apartment Building | 4×5 to 5×7 | 1–2 | NPC home visits, side quests | Dominant building type |
| Clinic / Hospital Wing | 4×5 | 2 | Heal + status cure | 1–2 per midtown zone |
| School | 7×6 to 8×8 | 2–3 (main + side exits) | Student NPCs, library puzzles | 1 per 3×3 block cluster |
| Parking Structure | 5×4 to 6×5 | 0 (open entrance) | Enemy spawn zone (cars as cover) | Alley-adjacent only |
| Corner Shop / Kiosk | 2×2 | 1 | Basic item resupply | 1 per block corner |
| Library | 5×5 to 6×6 | 1–2 | Lore/codex access, puzzle rooms | 1 per midtown zone |
| Night Club / Bar | 3×4 | 1 (velvet rope NPC) | Scripted event space | Evening/night access only |

**Midtown building density target:** 45–55% building footprint. The lower density vs. CBD creates breathing room and allows more sidewalk vendor interaction.

**Architectural pixel-art language for Midtown:**
- Brick facade: `(180, 100, 60)` base with `(160, 85, 50)` mortar lines every 2 pixels
- Awning over shop doors: `(220, 60, 60)` or `(60, 140, 220)` — vary by building type for color identity
- Window boxes (residential): `(60, 180, 80)` green plant pixels — 2–4 pixels wide, flush with window bottom
- Rooftop AC units: `(150, 150, 160)` grey 2×2 blobs on flat roofs — communicates age and density

### 3.3 Residential Buildings

Residential is quieter, smaller-scaled, and more organic-feeling. Building variety signals neighborhood character.

| Building Type | Footprint (cells) | Door Count | Interior Type | Special Rules |
|---|---|---|---|---|
| Single-Family House | 3×3 to 4×4 | 1 (front door) | NPC family home, side quests | Always has 1-cell garden patch |
| Rowhouse / Terrace | 2×4 per unit, 3–6 units joined | 1 per unit | NPC neighbors, collectibles hidden in gardens | Joins horizontally |
| Small Apartment Block | 4×5 | 1 | 4–8 NPC apartments | 2–3 per residential block |
| School / Community Center | 7×7 | 2 | Civic NPCs, bulletin board | 1 per residential zone |
| Corner Shop / Bodega | 2×2 to 3×2 | 1 | Emergency supplies | 1 per block |
| Church / Temple | 5×5 | 1 (large door) | Save point, story cutscene | 1 per residential zone |
| Derelict House | 3×3 to 4×4 | 1 (broken) | `TILE_RUIN` interior, enemy spawn | 1–3% of all residential buildings |
| Garden / Allotment | 3×3 (not a building) | N/A | Herb/item gathering, gardener NPC | 2–4 per block |

**Residential building density target:** 30–42% building footprint. The remainder is garden, street, and small parks — the lowest density of all zones, creating visual openness.

**Architectural pixel-art language for Residential:**
- House wall: `(220, 200, 160)` warm cream / `(190, 160, 120)` tan / `(200, 180, 180)` pale pink — vary by house to avoid monotony
- Roof (pitched pixel suggestion): 2-pixel "ridge" tiles in `(120, 80, 60)` terracotta or `(80, 100, 80)` mossy slate
- Garden patch: `(80, 160, 80)` grass with `(60, 120, 60)` darker patches for bushes; `(200, 80, 80)` flower pixels
- Derelict house: desaturate base color by 40%, add `(80, 70, 60)` dark dirt patches on walls, broken-window frame in `(40, 40, 40)`

---

## 4. Navigation and Flow

### 4.1 The Three Laws of Urban RPG Navigation

**Law 1 — The Player Must Always See a "Pull."**  
At every position on the map, the player must be able to see at least one visual attractor within 8 tiles: a landmark building, a differently-colored road segment, a park entrance, or an NPC with a visible exclamation mark. If the player stands on a road with only identical tiles in all directions, they are lost.

**Law 2 — Main Arteries Must Be Distinguishable From Side Streets.**  
The highway tier (from Team 1) must render 2 tiles wide in the game view (even if the underlying grid uses 1-cell roads). This is done by rendering highway cells with a "wide road" tile variant and offsetting the sidewalk by one cell. Side streets are always 1-tile wide. This single visual difference is the most powerful navigation cue in Pokemon-style maps.

**Law 3 — Bottlenecks Are Features, Not Bugs.**  
A bottleneck — a 1–2 tile wide passage between buildings — is where the player slows down and reads the environment. Every bottleneck should be intentionally placed near a shop entrance, an NPC, or a visible alley branch. Never create bottlenecks that lead to dead-end filler space.

### 4.2 Key Corridors and Landmark Orientation

**Primary corridor:** The main arterial road running through the CBD. This should be the widest road (visually 2 tiles), contain the highest NPC density, and connect the two most important landmarks (e.g., Train Station → City Hall). The player's mental model of the city anchors on this corridor.

**Secondary corridors:** Collector roads branching left/right from the primary corridor at regular intervals (every 8–12 tiles along the primary axis). Each secondary corridor leads into a distinct neighborhood (midtown block cluster or residential area).

**Landmark triangulation:** Place three large landmarks so they form an irregular triangle covering the map. The player can orient themselves by which landmark is visible relative to their position. Example placement for a 96×72 map:
- Landmark A (Train Station): top-left quadrant, cells (12, 8) to (18, 14)
- Landmark B (City Hall): center-top, cells (44, 6) to (52, 14)  
- Landmark C (Harbor/Park): bottom-right quadrant, cells (78, 58) to (86, 66)

**Legibility rules:**
- No two roads should run parallel and less than 3 tiles apart without a visual distinction (different surfacing, a building row between them, or a sidewalk variant)
- Alley entrances must be visually darker than the road they branch from — use `(60, 60, 60)` vs road `(100, 95, 90)` for instant readability
- Intersections with 4+ roads connecting should have a small plaza tile or crosswalk marker tile at their center to signal "this is a decision point"

### 4.3 Preventing Maze-Like Feel

The maze-like failure mode in procedural city maps occurs when the road graph has high connectivity but no visual hierarchy. Specific fixes:

1. **Zone color banding.** Each zone must have a distinct ground color (see Section 5). The player instantly knows which district they are in by looking at the floor.

2. **Maximum interior block path length: 8 tiles.** If the player enters an alley or back-street that dead-ends, the maximum distance from any main road must be 8 tiles. Beyond this, the player loses their bearings. Enforce this in the generator by running a BFS from every non-road cell to the nearest road tile and rejecting layouts where any cell exceeds distance 8.

3. **Forced visual breaks every 16 tiles.** On any straight road segment longer than 16 tiles, insert at least one of: a park, a plaza, a landmark corner building, or a road intersection. Straight uniform corridors past 16 tiles feel like hallways, not streets.

4. **No fully enclosed building clusters without a through-path.** If a cluster of buildings creates a region of road that is only accessible from one direction (a U-shaped enclosure), there must be an alley exit on the far side providing a second connection to the road network.

---

## 5. Visual Hierarchy in Pixel-Art Urban Tiles

### 5.1 Zone Ground Colors

The most important visual decision: every zone has a distinct ground color family. Based on analysis of Pokemon B/W, Pokemon RSE, and Fire Emblem urban maps:

| Zone | Ground Base Color (RGB) | Sidewalk Accent (RGB) | Road Color (RGB) |
|---|---|---|---|
| CBD | `(90, 90, 100)` cool grey | `(130, 125, 140)` pale slate | `(70, 70, 80)` dark asphalt |
| Midtown | `(110, 100, 85)` warm grey-tan | `(150, 140, 120)` beige stone | `(90, 85, 75)` warm asphalt |
| Residential | `(100, 120, 80)` green-grey | `(170, 160, 130)` sandy path | `(110, 105, 95)` lighter asphalt |
| Park (any zone) | `(80, 155, 75)` grass green | `(120, 180, 110)` light grass | `(90, 130, 80)` dirt path |
| Water | `(50, 110, 180)` deep blue | `(80, 150, 210)` shallow edge | N/A |
| Alley | `(55, 55, 60)` dark grey | N/A | `(50, 50, 55)` near-black |

**Critical rule:** Never use the same ground color family in adjacent zones. The zone boundary must be visible as a color shift within 1–2 tiles of crossing the boundary. Implement a 2-tile gradient blend at zone edges.

### 5.2 Reference Analysis: Pokemon B/W Castelia City

Castelia City (Pokemon Black/White, 2010) is the gold standard for urban pixel-art readability:

- **Road:** Consistent medium-dark grey `~(95, 90, 88)` with white dashed centerline markers every 4 tiles — the centerlines are the fastest "this is a road" signal
- **Sidewalk:** Lighter `~(170, 165, 155)` beige stone slabs, with a 1px dark grey gutter line separating road from sidewalk — the gutter line is 1 pixel wide but does enormous navigational work
- **Buildings:** Varied heights suggested by shadow pixels on right and bottom faces — a consistent 45° drop shadow in `(60, 55, 60)` 1–2 pixels wide
- **Doors:** Always marked with a distinct color break — typically `(180, 90, 60)` warm brown for wooden doors, `(120, 140, 160)` blue-grey for metal/glass — never the same color as the building wall

**Key Castelia lesson:** The city feels dense and urban not because of building complexity but because of **tight corridors** (2-tile-wide streets) combined with **tall building facades** that dominate the visual frame. The player feels small and in a city. Replicate this by ensuring that in CBD zones, at least 60% of road cells have an adjacent building tile that is at least 4 cells "tall" in the sprite (even if the cell grid depth is only 1 tile).

### 5.3 Reference Analysis: Pokemon RSE Lilycove City

Lilycove (Ruby/Sapphire/Emerald) demonstrates **zone mixing at small scale** — it combines a market area, a residential cliff area, a harbor, and a contest hall all within a compact map:

- **Market area:** Warm `(180, 150, 110)` sandy ground; building awnings in primary colors (red, blue, yellow) functioning as neighborhood identifiers
- **Harbor/Water edge:** Hard pixel-art wave animation using just 3 frames cycling between `(50, 110, 180)`, `(70, 130, 200)`, and `(90, 150, 220)` — very cheap to implement, high visual impact
- **Cliff residential:** Dark `(120, 100, 80)` stone ground shifting to `(160, 140, 100)` as it rises — height is implied by color darkening, not actual elevation geometry

**Key Lilycove lesson:** **Strong visual anchors at zone transitions.** The border between market and harbor is a dock line — a horizontal strip of `(100, 80, 60)` wood-plank tiles 1 tile wide. Every zone transition should have a 1-tile-wide "border material" that is visually distinct from both zones.

### 5.4 Reference Analysis: Fire Emblem Urban Maps

Fire Emblem: Three Houses monastery town and Three Hopes urban stages use a different approach — the top-down isometric suggestion in pure orthographic tiles:

- **Road surface:** Cobblestone texture — 3×3 tile micro-pattern in alternating `(140, 130, 120)` and `(120, 110, 105)` grey-browns. Implementable as a 2-frame subtle animation or static checker
- **Building rooftop visibility:** FE shows rooftops in oblique view — in pure top-down pixel art, simulate this with a 2-pixel "eave" shadow at the bottom edge of every building tile in `(50, 40, 35)` near-black
- **Impassable decorative tiles:** Barrels, crates, fences, hedges — all use a consistent 1-tile-wide "prop" category in warm brown `(140, 90, 50)` — the player reads "can't walk here" instantly
- **Interior zone indicator:** Fire Emblem uses a subtle floor glow around interactive NPCs — implement as a 2×2 pixel halo in `(255, 240, 100)` at 50% opacity pulsing on a 30-frame cycle

### 5.5 The 5-Color Rule for Immediate Readability

Successful pixel-art urban maps limit each zone to **5 dominant colors** visible at any time:

1. Ground/road base (1 color per zone)
2. Sidewalk/border material (1 color)
3. Building wall dominant (1 color, varied by building type ±20% brightness)
4. Building accent/trim (1 highlight color)
5. Nature/water element (grass green or water blue)

Everything else (NPC sprites, item pickups, UI elements) is layered on top of this 5-color ground. If the ground itself uses more than 5 dominant hues, the map reads as visual chaos.

---

## 6. Spawn Point Placement

### 6.1 NPC Spawn Rules

NPCs are the "life" of the city. They must follow density rules by zone to feel realistic rather than procedurally scattered.

**CBD NPC Types and Densities:**
- Business NPCs (office workers, traders, bankers): 1 per 8–10 road/sidewalk tiles in arterial areas
- Quest-giver NPCs: 1 per large building (City Hall, Police HQ, major hotel)
- Ambient crowd NPCs (non-interactable, decorative): 1 per 4–5 road tiles on primary arterials — these never trigger encounters
- Guard/Enforcer NPCs (Type B encounter sources): 1 per block entrance, clustered near banks and corporate buildings

**Midtown NPC Types and Densities:**
- Shop clerk NPCs: 1 per shop building, placed inside at 1 tile from the `TILE_DOOR`
- Market vendor NPCs: 2–4 per plaza, placed in the interior cells of `TILE_PLAZA`
- Pedestrian NPCs: 1 per 6–8 road tiles, randomized patrol routes of 4–8 tiles
- Alley NPC (enemy or secretive): 1 per alley, placed at the midpoint of the alley length

**Residential NPC Types and Densities:**
- Resident NPCs: 1 per 3–4 houses, placed within 2 tiles of `TILE_DOOR`
- Child NPCs (ambient, no combat): 1–2 per block, in garden/park tiles only
- Gardener/Elder NPC (quest): 1 per block, near garden patches
- Stray cat/dog (ambient): 1 per 2–3 blocks, random patrol

**Global NPC spawn rules:**
- Never spawn NPCs on `TILE_ROAD` within 1 tile of an intersection — this causes pathfinding conflicts
- Minimum 2-tile separation between any two named NPCs
- Ambient NPCs must have a defined patrol polygon (4–8 tiles) before spawning; NPCs without patrol routes look frozen and dead

### 6.2 Enemy Spawn Rules

Enemies use a **zone density table** seeded at map generation time. Enemy spawns are fixed at map creation (seed-based), not random per session.

| Zone | Spawn density (enemies per 100 eligible tiles) | Eligible tile types |
|---|---|---|
| CBD | 8–12 | `TILE_ALLEY`, `TILE_RUIN`, `TILE_ROAD` (connector only) |
| Midtown | 14–18 | `TILE_ALLEY`, `TILE_RUIN`, `TILE_ROAD` (all) |
| Residential | 6–10 | `TILE_ALLEY`, `TILE_RUIN` |
| Park (any zone) | 5–8 | `TILE_PARK` only |

**Enemy placement algorithm:**
1. For each zone, collect all eligible tiles
2. Shuffle the list using the map seed
3. Place enemies at the first N tiles, where N = floor(tile_count × density / 100)
4. Enforce minimum separation: no two enemies within 4 tiles of each other
5. If an enemy placement fails the separation check, skip and try the next tile in the shuffled list

**Enemy respawn policy:** Do not respawn enemies in cells within 8 tiles of the player's current position. Respawn timer: 5 in-game minutes (or equivalent step count ~120 steps). This prevents the frustrating loop of clearing a room and immediately facing a respawn.

### 6.3 Item Spawn Rules

Items (chests, pickups, hidden collectibles) follow a **rarity-by-location** model:

| Location Type | Item Rarity | Spawn Rate |
|---|---|---|
| `TILE_RUIN` | Uncommon–Rare | 1 per ruin tile cluster (BFS-connected group) |
| `TILE_ALLEY` terminus | Common–Uncommon | 1 per dead-end alley |
| Park hidden corner (≥4 tiles from any road) | Rare | 1 per qualifying park region |
| Inside buildings (post-door) | Common (consumables) | 1–3 per building interior |
| Behind locked doors | Rare–Unique | 1 per locked building |

**Item visibility rule:** Items placed outdoors must have a 2-tile "clear" radius — no other items within 2 tiles. Items inside buildings may be placed adjacent to walls.

**Hidden item seeding:** 5% of park and alley tiles contain invisible collectibles (triggered by player pressing Interact on an empty tile). Use the cell coordinate + map seed to determine which tiles are "hidden item" tiles — no runtime randomness needed.

---

## 7. Key Landmarks for Open-World Feel

### 7.1 The Landmark System

Procedural cities feel hand-crafted when they contain **8–12 unique named landmarks** that the player discovers, references on the map screen, and returns to. These landmarks cannot be procedurally placed identically on every map — each must use a unique placement algorithm tied to the seed.

**Landmark placement algorithm:**
1. Divide the map into a 3×3 "superblock" grid (for a 96×72 map: nine 32×24 regions)
2. Assign one Primary Landmark to the center superblock (CBD center)
3. Assign Secondary Landmarks to 4–6 of the remaining 8 superblocks (skip 2–4 to create asymmetry)
4. Place each landmark at a procedurally selected position within its superblock, biased toward the superblock center (Gaussian with σ=6 tiles)
5. Enforce minimum 14-tile separation between any two landmark origins

### 7.2 Mandatory Landmarks (Every Map)

These landmarks are required on every generated map. They serve as gameplay anchors:

**1. Central Train/Transit Station**
- Footprint: 10×8 cells minimum
- Features: `TILE_TRANSIT` platform (4–6 tiles wide), ticket booth NPC, map board
- Gameplay role: Fast travel hub, story start point, new NPC arrival mechanism
- Visual signature: Large roof overhang (4-tile-wide eave), distinctive clock tower sprite (3×5 tiles above normal building height)
- Placement: Top-center to center of map; always adjacent to primary arterial road
- Pixel color signature: Dark steel `(60, 65, 80)` structure with `(200, 190, 150)` sandstone base walls

**2. City Hall / Civic Center**
- Footprint: 10×8 to 12×10 cells
- Features: Grand entrance with 3-tile-wide door cluster, front plaza (`TILE_PLAZA`, 6×4), fountain
- Gameplay role: Main quest hub, law/order NPCs, political story branch
- Visual signature: Columned facade — alternating light `(210, 200, 185)` and shadow `(160, 150, 135)` column tiles; dome suggestion (3×3 curved top tiles in `(180, 160, 80)` gold)
- Placement: CBD zone; must face the primary arterial road

**3. Main Market / Bazaar**
- Footprint: The market is a `TILE_PLAZA` of 8×6 surrounded by 2×3 stall buildings on 3 sides
- Features: 6–10 vendor NPCs, rare item shops, information broker NPC
- Gameplay role: Primary shopping, rumor/quest gathering, fencing stolen goods
- Visual signature: Colorful awning tiles (mix of `(220, 60, 60)`, `(60, 120, 220)`, `(60, 180, 60)`) — 2-tile-wide awning strip above each stall
- Placement: Midtown zone, at the intersection of two collector roads

**4. Central Park**
- Footprint: 12×8 to 16×10 cells of `TILE_PARK`
- Features: Fountain (3×3 water tile cluster at center), 4 bench positions (NPC slots), winding dirt path through center
- Gameplay role: Rare item gathering, day/night scripted events, hidden underground entrance
- Visual signature: Wrought iron fence border tiles (1-tile-wide perimeter in `(40, 40, 50)`) with 4 gate openings aligned to road connections
- Placement: One per map; prefer Midtown/CBD border zone

**5. Hospital / Clinic**
- Footprint: 8×8 cells
- Features: Large cross symbol on roof (5×5 red cross pixels in `(220, 40, 40)`), emergency entrance (2-tile-wide door), ambulance vehicle prop
- Gameplay role: Full heal, status cure, story rescue events
- Visual signature: White `(235, 235, 235)` or pale `(220, 225, 230)` facade — must be the lightest building on the map; unmistakable
- Placement: Midtown zone; never in CBD or deep Residential

**6. Police Station**
- Footprint: 6×6 cells
- Features: Lockup (interior), bulletin board (wanted NPCs, bounty quests), 2 guard NPCs at door
- Gameplay role: Bounty submission, criminal faction hostility management, jail mechanic
- Visual signature: Blue flag/sign tile (`(40, 60, 180)`) prominently above entrance; 2-tile-wide stripe at building base in `(40, 60, 180)`
- Placement: CBD; never more than 8 tiles from City Hall

### 7.3 Optional Landmarks (4–6 per Map, Seed-Selected)

Select 4–6 from this list per map generation, using the seed:

| Landmark | Footprint | Gameplay Role | Visual Signature |
|---|---|---|---|
| Library / Archive | 8×6 | Lore/codex, research quests | Stone grey `(150, 145, 140)`, arched window tiles |
| Underground Entrance / Subway | 3×3 staircase | Zone transition, dungeon access | Dark shaft tiles with yellow safety stripe `(220, 190, 40)` |
| Factory / Industrial | 12×8 | Enemy stronghold, crafting | Smokestack sprite, corrugated iron `(100, 95, 90)` roof |
| Luxury Hotel | 6×10 | Inn/save, high-cost services | Neon sign tiles `(255, 80, 180)`, golden revolving door |
| Harbor / Dock | 14×4 linear | Water-world access, smuggler NPCs | Wooden plank floor `(130, 100, 65)`, boat sprites |
| Stadium / Arena | 14×12 | Tournament combat event | Oval structure, ticket booth, crowd NPC cluster |
| University / Academy | 12×10 | Skill learning, faction quests | Gothic archway entrance, campus green |
| Black Market | 4×4 (hidden, alley-adjacent) | Illegal items, fence NPCs | No sign; entrance is `TILE_ALLEY` door in `(40, 40, 40)` |
| Rooftop Garden | 4×4 (atop a 6×6 building) | Rare herbs, secret NPC meeting | Only accessible via interior staircase |
| Abandoned Mall | 16×10 | Multi-room dungeon | Cracked glass `(150, 160, 170)` facade, barricaded entrance |

**Landmark discovery mechanic:** Landmarks should not appear on the player's map until they come within 6 tiles of the landmark boundary. This preserves the exploration-discovery feel of open-world maps even in a procedural system.

---

## 8. Scale Calibration

### 8.1 Reference Map: 96×72 Tile Grid at 10 m/cell

At 10 m per cell, a 96×72 grid represents **960 m × 720 m = 0.69 km²**. This is comparable to:
- Monaco's entire land area (2.02 km²) — our map is one-third of Monaco
- A medium US downtown district (e.g., downtown Savannah, GA historic district: ~1 km²)
- Roughly 6×4.5 standard NYC city blocks (each block ~80m × 270m)

This is the right scale for a 4–8 hour RPG exploration campaign.

### 8.2 Recommended Block and Building Counts

For a **96×72 tile map** as the reference standard:

**Road network:**
- Primary arterial roads: 2–3 (each spanning the full map width or height)
- Secondary collector roads: 6–10 (branching from arterials)
- Local connector roads: 18–28 (filling residential grid)
- Total road cells: ~1,900–2,400 (≈28% of map)

**Blocks (enclosed land areas between roads):**
- CBD blocks: 4–6 blocks, each 8×6 to 14×10 cells
- Midtown blocks: 12–18 blocks, each 6×5 to 10×8 cells
- Residential blocks: 20–30 blocks, each 4×4 to 8×6 cells
- Total distinct blocks: **36–54**

**Buildings:**
- CBD: 15–25 buildings across 4–6 blocks (2–5 buildings per block)
- Midtown: 40–65 buildings across 12–18 blocks (3–5 per block)
- Residential: 60–100 buildings across 20–30 blocks (3–4 per block)
- **Total buildings: 115–190**

**Parks and plazas:**
- Large parks (>8×6 cells): 2–4 total
- Small parks / pocket greens (3×3 to 6×4): 6–10 total
- Plazas (paved open space): 4–8 total

**Named landmarks:**
- Mandatory: 6 (always present)
- Optional: 4–6 (seed-selected)
- **Total landmarks: 10–12**

**NPCs:**
- Named NPCs (quest/vendor): 30–50
- Patrol NPCs (ambient): 60–90
- Enemy spawns: 50–80 (seed-fixed)
- **Total entities: 140–220**

### 8.3 Player Experience Arc Across the Map

The 96×72 map should deliver the following paced experience:

**Phase 1 — Entry and Orientation (First 10–15 minutes):**
Player starts at the Transit Station (top-center). The primary arterial road runs south from the station directly toward City Hall. This corridor is the "tutorial spine" — wide, high NPC density, no alley branches in the first 8 tiles south of the station. Players learn road navigation, sidewalk NPC interaction, and the first shop.

**Phase 2 — CBD Exploration (15–45 minutes):**
City Hall and Police Station become known. The player crosses into midtown via a secondary corridor. First `TILE_ALLEY` encounter is designed here — a forced narrative event that introduces card combat in a controlled way (not a random encounter). The Market is discovered.

**Phase 3 — Midtown Density (45–120 minutes):**
The widest zone of engagement. The player has free movement. The Hospital and 2–3 optional landmarks are in this zone. Random encounters are most frequent here. The map feels alive because of shop NPCs, patrol patterns, and alley danger.

**Phase 4 — Residential Discovery (120–180 minutes):**
The residential zone rewards exploration — hidden items, unique side-quest NPCs, the church save point. Encounter rate drops, providing emotional pacing relief after midtown. The player discovers the optional Black Market (alley-hidden) and the Underground Entrance.

**Phase 5 — Full Map Control (180+ minutes):**
All landmarks discovered. Player uses fast travel (Transit Station) to optimize NPC revisits. Secret areas (Rooftop Garden, Abandoned Mall) become accessible with acquired keys/cards. The procedural map has been made legible through landmark anchors; it now feels like a "real place."

### 8.4 Scaling Rules for Other Map Sizes

| Map Size | Blocks | Buildings | Named Landmarks | NPCs (total) | Playtime estimate |
|---|---|---|---|---|---|
| 64×48 (small) | 20–30 | 70–110 | 6–8 | 80–130 | 2–4 hours |
| 96×72 (medium, reference) | 36–54 | 115–190 | 10–12 | 140–220 | 4–8 hours |
| 128×96 (large) | 60–85 | 180–280 | 14–18 | 200–320 | 8–14 hours |
| 160×120 (maximum) | 90–130 | 260–400 | 20–26 | 280–450 | 14–24 hours |

**Density scaling rule:** Do not scale NPCs or buildings linearly with area. Use a square-root scaling factor — doubling the map area should produce ×1.4 (not ×2.0) NPCs and buildings. Larger maps need more open/empty space per unit area to remain navigable.

---

## 9. Implementation-Ready Quick Reference

### 9.1 Tile Category Enum Values

```python
class TileCategory(IntEnum):
    ROAD       = 1   # walkable, encounter-eligible
    SIDEWALK   = 2   # walkable, low encounter rate
    BUILDING   = 3   # impassable obstacle
    DOOR       = 4   # walkable, triggers script
    PARK       = 5   # walkable, event encounters
    WATER      = 6   # impassable, decorative
    ALLEY      = 7   # walkable, high encounter rate
    PLAZA      = 8   # walkable, NPC scripted zone
    RUIN       = 9   # walkable, high encounter + loot
    TRANSIT    = 10  # walkable, safe zone (no encounters)
```

### 9.2 Encounter Probability Lookup Table

```python
# Base probability per step (0.0–1.0)
ENCOUNTER_P = {
    (TileCategory.ROAD,     ZoneID.CBD):         0.03,
    (TileCategory.ROAD,     ZoneID.MIDTOWN):      0.08,
    (TileCategory.ROAD,     ZoneID.RESIDENTIAL):  0.06,
    (TileCategory.SIDEWALK, ZoneID.CBD):          0.01,
    (TileCategory.SIDEWALK, ZoneID.MIDTOWN):      0.02,
    (TileCategory.SIDEWALK, ZoneID.RESIDENTIAL):  0.01,
    (TileCategory.ALLEY,    ZoneID.CBD):          0.18,
    (TileCategory.ALLEY,    ZoneID.MIDTOWN):      0.22,
    (TileCategory.ALLEY,    ZoneID.RESIDENTIAL):  0.15,
    (TileCategory.PARK,     ZoneID.CBD):          0.08,
    (TileCategory.PARK,     ZoneID.MIDTOWN):      0.06,
    (TileCategory.PARK,     ZoneID.RESIDENTIAL):  0.04,
    (TileCategory.RUIN,     ZoneID.CBD):          0.25,
    (TileCategory.RUIN,     ZoneID.MIDTOWN):      0.20,
    (TileCategory.RUIN,     ZoneID.RESIDENTIAL):  0.20,
    # All other categories: 0.0 (no random encounters)
}
ENCOUNTER_COOLDOWN_STEPS = 4
```

### 9.3 Zone Color Palette (RGB Tuples)

```python
ZONE_COLORS = {
    "CBD": {
        "ground":    (90,  90,  100),
        "sidewalk":  (130, 125, 140),
        "road":      (70,  70,  80),
        "building":  (80,  75,  90),
        "accent":    (200, 170, 60),
    },
    "MIDTOWN": {
        "ground":    (110, 100, 85),
        "sidewalk":  (150, 140, 120),
        "road":      (90,  85,  75),
        "building":  (180, 100, 60),
        "accent":    (220, 60,  60),
    },
    "RESIDENTIAL": {
        "ground":    (100, 120, 80),
        "sidewalk":  (170, 160, 130),
        "road":      (110, 105, 95),
        "building":  (220, 200, 160),
        "accent":    (80,  160, 80),
    },
    "PARK": {
        "ground":    (80,  155, 75),
        "path":      (90,  130, 80),
        "border":    (40,  40,  50),
        "water":     (50,  110, 180),
    },
}
```

### 9.4 Landmark Placement Superblock Assignment

```python
# For a W×H tile map, divide into 3×3 superblocks
# Superblock indices: 0=top-left, 1=top-center, ..., 8=bottom-right
MANDATORY_LANDMARK_SUPERBLOCKS = {
    "transit_station":  1,   # top-center
    "city_hall":        4,   # center (CBD)
    "police_station":   4,   # center (near city hall)
    "market":           3,   # center-left (midtown)
    "central_park":     5,   # center-right (midtown border)
    "hospital":         7,   # bottom-center (midtown)
}

# Optional landmarks: seed-select 4-6 from remaining superblocks
OPTIONAL_LANDMARK_POOL = [
    "library", "subway_entrance", "factory", "luxury_hotel",
    "harbor", "stadium", "university", "black_market",
    "rooftop_garden", "abandoned_mall"
]
```

---

## 10. Summary of Key Design Numbers

| Parameter | Value |
|---|---|
| Max distance from any cell to nearest road | 8 tiles |
| Min building footprint | 3×3 cells |
| Max alley length | 12 cells |
| Forced visual break on straight roads | Every 16 tiles |
| NPC encounter cooldown | 4 steps |
| Landmark discovery radius | 6 tiles |
| Min landmark separation | 14 tiles |
| Enemy respawn exclusion radius | 8 tiles |
| Zone color gradient transition width | 2 tiles |
| Dominant colors per zone (ground layer) | 5 maximum |
| Reference map size | 96×72 tiles |
| Reference building count (96×72) | 115–190 |
| Reference landmark count (96×72) | 10–12 |
| Reference NPC count (96×72) | 140–220 |
| Estimated playtime (96×72) | 4–8 hours |

---

*End of Team 4 Report — Senior Urban Game Design Committee*  
*Companion documents: `team1_city_planning.md`, `team2_game_algorithms.md`, `team3_implementation_plan.md`*
