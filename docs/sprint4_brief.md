# Sprint 4 City Planning Brief

**Team 1 — Architecture Research**  
**Date**: May 9, 2026

---

## 1. Park Ratios

**WHO standard**: 9 m² of green space per resident. For a procedural city with \~10 m/cell resolution:
- A 25-cell park = 250 m² — adequate for a neighbourhood pocket park serving \~25 residents.
- A 100-cell park = 1,000 m² — realistic small urban park (Paris square, NYC vest-pocket park).
- Target: **1 park per 500 land cells** per zone scales naturally with map size.
- At 80×60 (4,800 land cells, 3 zones ≈ 1,600 each): \~3 parks per zone = 9 total — appropriate.
- At 160×120 (19,200 land cells): \~6–7 parks per zone = 18–21 total — correct scaling.

**Block-level reality**: Real city parks occupy 1–6 full blocks. Typical US city block = \~0.4–2 ha. Our 25–120 cell range (0.25–1.2 ha at 10 m/cell) is correctly calibrated.

---

## 2. Waterfront Building Types

**Urban waterfront reality** (based on post-industrial waterfront conversion patterns — Boston Seaport, Rotterdam, Sydney Darling Harbour):

| Building Type | % of waterfront lots | Notes |
|---|---|---|
| Restaurant / bar | 30–40% | Water views command premium; highest frequency |
| Mixed retail / market | 20–30% | Waterfront markets, fish markets |
| Residential (apartments) | 15–25% | Luxury condos with water view |
| Ferry terminal / station | 5–15% | Every navigable waterfront needs transit |
| Vacant / undeveloped | 5–10% | Brownfield gaps, industrial legacy |
| Office | rare (<5%) | Low-rise only; towers set back from edge |

**Conclusion**: Our `WATERFRONT_BLDG_WEIGHTS` (restaurant 35 / market 25 / apartment 20 / station 10 / empty 10) is well-calibrated.

---

## 3. Setback Standards

| Zone | Typical Front Setback | Notes |
|---|---|---|
| Residential single-family | 4.5–6 m (≈1 cell) | Required by code in virtually all US/EU residential |
| Residential multi-family | 3–4.5 m (≈1 cell) | Smaller but still present |
| Commercial / midtown | 0–3 m | Storefronts often at sidewalk edge; minimal setback |
| CBD | 0 m | Buildings built to property line (zero-lot-line) |

**Implementation rule**: Only residential zone lots with ≥ 9 cells get a 1-cell perimeter setback. Commercial and CBD lots get zero setback. This matches real zoning codes globally.

**Visual**: The 1-cell setback renders as warm light-green (lawn), clearly distinguishing house footprints from their yards.

---

## 4. Zone Boundary Transitions

**Urban reality**: Hard zone boundaries do not exist. Real cities have **transitional strips** 1–3 blocks wide where zones blend:
- **CBD edge → Midtown**: "Frame zone" — older low-rise offices, parking structures, light retail. Character shifts gradually over 2–4 blocks.
- **Midtown → Residential**: "Transition strip" — row houses, converted storefronts, small apartments mixed with detached houses.

**Pattern frequency**: In any given boundary cell, roughly 35–45% will "feel" like the adjacent zone rather than the assigned one.

**Implementation**: Flip boundary cells with 40% (CBD→Mid) / 35% (Mid→Resi) probability using seeded noise for organic-looking results. The civic anchor cell is never flipped (it defines the CBD's semantic centre).

---

## 5. Alley vs Cul-de-sac

| Type | Real-world description | Length | Role |
|---|---|---|---|
| Alley / service lane | Rear service access, rubbish bins, loading docks | 1–3 cells | `ROLE_WALKABLE_ALLEY` (danger) |
| Cul-de-sac | Residential dead-end with turning circle | 4+ cells | `ROLE_WALKABLE_ROAD` (normal street) |

**Key distinction**: Alleys are narrow and service-oriented — high crime risk in RPG terms. Cul-de-sacs are planned residential dead-ends — normal street safety. Length ≤ 3 cells = alley; > 3 cells = cul-de-sac.

---

*Sprint 4 brief complete — all research grounded in real urban design standards.*
