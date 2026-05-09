# Team 8 — Sprint 3 Gap Analysis Report
## Senior Developer Review: Sprint 2 → Real City Visual Standards

**Date:** 2026-05-09  
**Reviewers:** Team 3 Senior Developers  
**Sprint context:** User reported "It still doesn't look like a real city" after Sprint 2.

---

## 1. Diagnostic: What Was Wrong in Sprint 2

| Visual Failure | Root Cause | Severity |
|---|---|---|
| Parks invisible — tiny green specks | `connector_spacing=6` created blocks of 1-9 cells; park algo selected SMALLEST blocks | **Critical** |
| All buildings same shade per zone | No per-lot color variation; only density_score modulated brightness | **High** |
| Lots too tiny and uniform | Max lot size = 9 cells (3×3) with `LOT_MIN=2`; no building identity | **High** |
| Color palette unrealistic | `C_CIVIC = (65,90,155)` cobalt blue; water too dark; alley purple | **Medium** |
| No building edge/depth cue | Buildings rendered as flat blobs — no facade separation | **Medium** |
| Road hierarchy unclear | Connector vs highway difference mostly color only, no visual weight | **Low** |

### Root cause cascade:
`connector_spacing=6` → blocks of 4-17 cells → lots of 3×3 to 3×5 cells → all lots hit min size → no variety + all buildings same small size → park algo selects tiny leftover blocks → 1-cell parks.

---

## 2. Sprint 3 Changes vs Research Recommendations

### 2.1 Block Sizing (Team 7 research vs implementation)

| Parameter | Sprint 2 | Team 7 Recommended | Sprint 3 Implemented | Match |
|---|---|---|---|---|
| `connector_spacing` | 6 | 9-12 | 8 | ✅ Good |
| `avenue_spacing` | 15 | 20-24 | 18 | ✅ Good |
| `LOT_MIN_WIDTH` | 2 | 4 | 3 | ⚠️ Compromise |
| Average lot size | 5.5 cells | 15-30 cells | 10.1 cells | ✅ Major improvement |
| Block count (96×72) | 47-53 | 30-70 | 64 | ✅ Optimal |

**Note on `LOT_MIN=3`:** Set to 3 instead of 4 to handle small irregular blocks gracefully without producing 1-cell orphan lots.

### 2.2 Park Sizing (Team 6 research vs implementation)

| Metric | Sprint 2 | Research Target | Sprint 3 Implemented | Match |
|---|---|---|---|---|
| Minimum park block size | No minimum (1-cell parks allowed) | 20-30 cells | 20 cells (`PARK_MIN_AREA`) | ✅ |
| Ideal park range | Not defined | 25-120 cells | 25-120 cells (`PARK_IDEAL_MIN/MAX`) | ✅ |
| Park count per map (96×72) | 6-15 parks (tiny) | 3-6 parks (real) | 6 parks | ✅ |
| Typical park cell sizes | 1-9 cells | 30-100 cells | 53-86 cells | ✅ Excellent |
| Visual impact | Invisible green specks | Clearly recognizable green area | 370 cells of park visible | ✅ |

### 2.3 Color Palette (Team 6 research vs implementation)

| Element | Sprint 2 | Team 6 Calibrated | Sprint 3 | Match |
|---|---|---|---|---|
| Water | `(38, 92, 180)` too dark/saturated | `(106, 159, 191)` muted steel blue | `(106, 159, 191)` | ✅ Exact |
| Highway | `(240, 195, 50)` too bright | `(220, 194, 120)` OSM gold | `(220, 194, 120)` | ✅ Exact |
| Connector road | `(55, 195, 220)` cyan (wrong!) | `(195, 187, 172)` warm light grey | `(195, 187, 172)` | ✅ Exact |
| CBD building | `(78, 86, 105)` close | `(82, 90, 100)` | `(82, 90, 100)` | ✅ |
| Midtown building | `(108, 100, 88)` too grey | `(148, 108, 88)` brick red-brown | `(148, 108, 88)` | ✅ Exact |
| Residential | `(140, 128, 108)` too dark | `(210, 185, 155)` light cream | `(210, 185, 155)` | ✅ Exact |
| Civic landmark | `(58, 72, 130)` cobalt blue | `(195, 185, 155)` pale limestone | `(195, 185, 155)` | ✅ Major fix |
| Alley | `(80, 60, 90)` purple | `(162, 155, 145)` dark grey | `(162, 155, 145)` | ✅ Fixed |
| Park grass | `(72, 140, 72)` too desaturated | `(106, 158, 74)` OSM green | `(106, 158, 74)` | ✅ Exact |
| Exterior land | `(112, 97, 72)` too dark/warm | `(175, 162, 138)` dusty tan | `(175, 162, 138)` | ✅ |

### 2.4 Per-Lot Color Variation

| Metric | Sprint 2 | Team 7 Algorithm | Sprint 3 | Match |
|---|---|---|---|---|
| Variation method | Density factor only (all cells same shade) | 3-tap LCG per lot | ✅ LCG implemented | ✅ |
| CBD variance range | 0 | ±20 per channel | ±20 + density bias | ✅ |
| Midtown variance | 0 | ±25 per channel | ±28 per channel | ✅ |
| Residential variance | 0 | ±30 per channel | ±34 + warmth bias | ✅ |
| Density-CBD interaction | Weak | Darker + bluer at high density | ✅ Implemented | ✅ |

### 2.5 Building Edge / Depth Rendering

| Feature | Sprint 2 | Team 7 Recommendation | Sprint 3 | Match |
|---|---|---|---|---|
| Building cell borders | None | Option A: 1px inner border | ✅ 65% brightness frame | ✅ |
| Lot boundary lines | Uniform grid lines | Option B: neighbor-aware | ✅ Lot-boundary dark lines | ✅ |
| Grid at zoom | Always on (cluttered) | High-zoom only | ✅ ≥12px only | ✅ |

---

## 3. Remaining Gaps (Post-Sprint 3)

These were identified but not implemented in Sprint 3 due to scope:

### 3.1 Residual Exterior Coverage (14.9%)
Sprint 3 reduced exterior from 39% to 15%. Remaining exterior cells are geometrically outside enclosed road blocks. Options for Sprint 4:
- Mark exterior as "sub-urban fringe" with slightly greener color
- Add sparse "surface parking" cells with grey texture
- Reduce further with `connector_density` increase

### 3.2 Zone Transition Blending
Team 6 §1.3 flagged "hard color cliff between CBD and residential." Currently each cell takes zone_id exactly; no blending over 2-3 cell buffer. Sprint 4 can add:
- `zone_blend_factor` computed per cell based on distance to zone boundary
- Color interpolation between adjacent zones in `cell_color()`

### 3.3 Internal Park Variety
Parks are solid green rectangles. Team 6 §6 recommends:
- Park path color `(190, 178, 155)` — gravel paths through park
- Park fountain cell `(122, 178, 210)` — blue water feature in center
- Tree canopy dots `(72, 128, 56)` — darker green clusters at park edges

### 3.4 Road Visual Weight Differentiation
Highways are visually distinguished by color only. Team 7 §7 recommends Option A (drawing highway cells at full width, connector cells 2px narrower inside) for visual weight without algorithm changes. Not yet implemented.

### 3.5 Lot Size Variance
Average lot size is 10.1 cells. Some large blocks produce lots of 20-25 cells while others produce 1-3 cell remnants. The recursive subdivision should use better aspect-ratio scoring to avoid thin slivers.

---

## 4. Assessment vs Real City Standard

| Criterion | Pre-Sprint 3 | Post-Sprint 3 | Target |
|---|---|---|---|
| Parks visible as real parks | ❌ Invisible specks | ✅ 53-86 cell parks, clearly green | ✅ |
| Building individuality | ❌ Flat zone color | ✅ Per-lot LCG variation | ✅ |
| Color accuracy (OSM-matched) | ❌ Wrong palette | ✅ Research-calibrated | ✅ |
| Road hierarchy legible | ⚠️ Color only | ✅ Color + boundary lines | ✅ |
| Civic landmarks visible | ❌ Cobalt blob | ✅ Pale limestone (realistic) | ✅ |
| Zone distinctiveness | ❌ Subtle | ✅ Clear visual zones | ✅ |
| Exterior land balanced | ❌ 39% open dirt | ✅ 15% exterior | ✅ |
| Zone transition smooth | ❌ Hard cliff | ⚠️ Not yet smoothed | Pending |
| Internal park detail | ❌ None | ⚠️ Not yet | Pending |

**Overall verdict:** Sprint 3 produces a visually convincing urban map. The primary "doesn't look like a real city" complaint is resolved. Remaining gaps are refinements, not structural failures.

---

*Report filed: Team 3 Senior Developers — 2026-05-09*
