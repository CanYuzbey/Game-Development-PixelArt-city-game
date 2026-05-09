# City Planning Committee Report
## Technical Urban Morphology Reference for Procedural Mid-Rise City Generation

**Prepared by:** Senior City Planning Committee (Architects, Urban Planners, Civil Engineers)
**Date:** 2026-05-09
**Audience:** Game developer building a procedural mid-rise city map generator

---

## 1. Road Hierarchy in Real Mid-Rise Cities

A functioning mid-rise city uses a strict four-to-five tier road hierarchy. Each tier has a distinct width, access role, and sidewalk policy. Treating all streets as identical-width corridors is one of the most common procedural-generation failures.

### Tier 1: Arterial / Urban Highway
- **Right-of-way width:** 30–60 m (Haussmann boulevards: 30 m standard, 50–60 m for Grand Axis routes like Gran Via / Passeig de Gràcia in Barcelona)
- **Carriageway:** 2–4 lanes each direction, separated median common
- **Sidewalks:** Always present; minimum 3.0 m per NACTO urban arterial standard; often 5–8 m in dense cores
- **Function:** City-wide mobility. Through movement, not property access
- **Junction type:** Signalized intersections only; T and X both occur; NO dead ends
- **Real examples:** Haussmann boulevards (Paris, 24–30 m); Broadway (Manhattan); Gran Via (Barcelona, 50 m)

### Tier 2: Collector / Avenue
- **Right-of-way width:** 16–24 m
- **Carriageway:** 1–2 lanes each direction
- **Sidewalks:** Always present; minimum 2.25 m per NACTO collector standard; typically 2–4 m
- **Function:** Distributes traffic from arterials to local streets; also fronts ground-floor retail
- **Junction type:** T and X junctions; dead ends not permitted at this level
- **Lane width:** 3.0–3.35 m per lane (NACTO recommends max 3.35 m / 11 ft on urban collectors to discourage speeding)

### Tier 3: Local Connector Street
- **Right-of-way width:** 9–15 m
- **Carriageway:** One lane each direction or a single shared lane (yield-street pattern)
- **Sidewalks:** Present in grid neighborhoods; may be omitted in low-density residential (yield streets sometimes use a continuous shared surface)
- **Function:** Primary access to residential parcels
- **Junction type:** T and X permitted; dead ends permitted at this level — this is where cul-de-sacs originate

### Tier 4: Private Road / Mews / Court
- **Right-of-way width:** 5–8 m (private neighborhood streets can be 5 ft / 1.5 m narrower than public equivalents)
- **Carriageway:** Single shared lane, typically 4–6 m paved
- **Sidewalks:** Absent. Surface is often continuous flush paving (shared space) or unsealed gravel/pavers
- **Function:** Serves a small cluster of lots (typically 4–20 dwellings)
- **Junction type:** Single-entry only; always terminates in a turning court or cul-de-sac bulb
- **Entrance:** Marked visually as private — gates, bollards, a change of paving material, or posted signage. Gated community entrances require a minimum 22 ft / 6.7 m clear gate width for two-way traffic, and a 60 ft / 18 m setback from the arterial curb line.

### Tier 5: Shared Driveway / Alley
- **Width:** 3–5 m
- **Paving:** Often unpaved or pavers; not maintained by municipality
- **Sidewalks:** None
- **Function:** Rear-lane access to parking/garages; service access; garbage collection
- **Junction:** Connects between two parallel local streets — passes through the interior of a block

**Key rule:** Higher tiers connect only to same or higher tiers at their endpoints. A private road never T-junctions directly onto an arterial. A collector connects to arterials. Local streets connect to collectors or other locals.

---

## 2. Block Size by Zone (Real Measurements)

Block sizes are the single most diagnostic dimension for a city zone. The data below comes from OSM-derived global city analysis and published urban morphology studies.

### Historic Core / CBD

| City | Block Width (short side, m) | Block Depth (long side, m) | Notes |
|---|---|---|---|
| Manhattan Midtown | ~80 | ~229–274 | North–south between avenues: 80 m; East–west between numbered streets: 229–274 m. High variance: 6th–12th Ave blocks reach 280 m. (Source: City Block Wikipedia; Old Urbanist blog) |
| Paris (Haussmannian) | ~80–120 | ~120–200 | Building footprints are 15 m street frontage × 7–13 m depth; blocks assembled from many such parcels. Street widths 18–24 m. (Source: Urban.PubPub Haussmann analysis) |
| Barcelona Eixample | 113 | 113 | Perfect square. Chamfered corners (chaflans) create 45° cuts of ~17 m. Streets are 20 m wide. Passeig de Gràcia is 60 m. (Source: Wikipedia Cerdà Plan; UrbanDesignLab.in) |
| Tokyo (Minato, commercial) | ~60 | ~80 | ~4,800 m² average block area in commercial zones. Extreme variation; inner-city blocks can be 30×50 m. (Source: ResearchGate Tokyo block distribution study) |
| Amsterdam Jordaan | ~40–60 | ~60–100 | Canal structure dictates elongated blocks perpendicular to canal lines. Lots are famously narrow (5–8 m frontage). |

### Mixed-Use Midtown / Transitional

- Typical range: **80–150 m × 80–150 m**
- Blocks become more irregular here. Expect 10–25% of blocks to be non-rectangular due to diagonal streets, historic path routes, or topography.
- London Islington: one of London's densest boroughs; blocks are 60–120 m on a side, often irregular due to organic street growth predating any grid plan.

### Residential Outskirts

- **Typical grid suburb:** 120–180 m × 60–90 m (elongated to maximize lot depth)
- **Post-WWII discontinuous suburb (cul-de-sac pattern):** Block equivalents become irregular cells of 200–500 m across, internally subdivided by cul-de-sacs; blocks in the traditional sense disappear
- Buenos Aires residential: 110 m × 110 m grid (very regular)
- Generic suburban US: 80–120 m (short) × 150–275 m (long), giving rectangular blocks with rear alleys or large rear yards

**Practical generation rule:** Block area in historic cores averages ~10,000–15,000 m²; in planned midtown grids ~12,000–20,000 m²; in residential outskirts ~15,000–40,000 m² for grid zones. Perimeter-to-area ratios are diagnostic — very elongated blocks (aspect ratio > 3:1) belong to dense grid cores (Manhattan) or canal cities.

---

## 3. Private Property Patterns

### Cul-de-Sac Prevalence

Cul-de-sacs are the dominant pattern in post-1950s American and British residential subdivisions. The Institute of Transportation Engineers formally recommended discontinuous hierarchical street systems (favoring cul-de-sacs) following a Los Angeles traffic study from 1951–1956. As a result:

- In American post-war suburbs, **30–50% of residential streets** by count are dead-end streets or cul-de-sacs (estimated from the Reconsidering the Cul-de-sac study, ACCESS Magazine, Spring 2004).
- In grid-dominant European cities (Barcelona Eixample, Paris arrondissements, Amsterdam canal grid), **dead-end residential streets are rare — under 5%**.
- Radburn, NJ (the model superblock suburb) showed that cul-de-sac layouts reduce total street area and utility length by **25%** versus an equivalent grid — hence their economic dominance in North American development.

### Cul-de-Sac Standard Dimensions

These are the values that appear across North American municipal design codes:

- **Maximum length (centerline):** 365 m (1,200 ft) — beyond this, emergency access fails
- **Typical residential cul-de-sac length:** 75–180 m
- **Bulb right-of-way diameter:** 27–30 m (90–100 ft); some jurisdictions require 40 m (130 ft)
- **Pavement diameter at bulb:** 24–30 m (80–100 ft)
- **Back-of-curb radius:** 13.7–18.3 m (45–60 ft); reduced to 9 m (30 ft) allowed in very low-traffic situations
- **Minimum emergency turning radius:** 8.5–9.1 m (28–30 ft) for modern fire apparatus

### Private Court / Mews / Parking Court

London mews: originally stable alleys behind Georgian townhouses, now residential. Typical mews are 4–6 m wide carriageway, no sidewalk, 60–120 m long, entered from a single point on the collector street. The enclosed mews court is 10–20 m wide.

Parking courts (US): a 6–8 m wide drive entering from the local street, serving 4–12 parking spaces in a surface lot behind buildings. Often 20–40 m deep.

### How Private Streets Differ from Public

| Feature | Public Local Street | Private Road / Mews |
|---|---|---|
| Width | 9–15 m ROW | 5–8 m ROW |
| Sidewalk | Both sides typical | None |
| Pavement | Asphalt, maintained by city | Pavers, asphalt, or gravel; owner-maintained |
| Curb | Raised concrete curb | Flush edge, drainage channel, or bare edge |
| Signage | Street signs at each end | "Private Road" / gate / bollards |
| Through connection | Connects to network | Single entry, terminates |

### Gated Communities

- Internal road width: ~6.7 m minimum (22 ft clear gate width) for two-way traffic
- Gate setback from arterial: minimum 18 m (60 ft)
- Internal roads are entirely private; all maintenance costs fall on the HOA, not the city
- No sidewalks are required internally; shared surface or narrow paths common
- Perimeter: often a wall 1.8–2.4 m high or dense landscaping berm

---

## 4. Park and Open Space Placement

### Park-to-Block Ratio by Zone

The American Planning Association (PAS Report 194, "Standards for Outdoor Recreational Areas") established widely cited benchmark ratios:

- **Overall system minimum:** 6.25–10.5 acres of developed open space per 1,000 residents (~2.5–4.3 ha/1,000 pop)
- **Neighborhood parks:** 0.6 ha per 1,000 residents minimum; service radius 400–800 m
- **Japan's Urban Park Law benchmarks:** Children's park: 0.25 km radius; Community park: 0.5 km radius; Regional park: 1.0 km radius

For procedural generation, a useful working ratio is: **1 park per every 8–15 city blocks** in dense residential/mixed zones; **1 plaza per every 4–6 blocks** in CBD cores (plazas replace park grass with hard paving).

### Park Sizes by Type

| Park Type | Typical Size | Notes |
|---|---|---|
| Pocket park / Tot lot | 400–2,000 m² (0.04–0.2 ha) | Fills a single residual lot; common in dense grids |
| Neighborhood park | 0.5–4 ha (1.2–10 acres) | Serves a ~400 m radius; standard target 2–4 ha |
| District / Community park | 8–10 ha (20–25 acres) | Serves several neighborhoods; sports fields, larger landscape |
| City park | 20–200+ ha | Rare; one per city (Central Park NYC = 341 ha) |
| Plaza / civic square | 0.1–1 ha | Hard-paved; located at intersections or in front of civic buildings |

### Placement Logic by Zone

- **CBD:** Hard-surface plazas (0.1–0.5 ha) at civic buildings, transit hubs, and major intersections. Green parks are scarce — maybe 1 per 15–20 blocks.
- **Mixed-use midtown:** Combination of plazas and small neighborhood parks. Expect 1 park per 8–12 blocks. Parks tend to occupy corner lots or entire small blocks.
- **Residential:** Neighborhood parks every 6–10 blocks. Parks positioned centrally within a walkable catchment.
- **Edge / suburban:** Larger, less frequent parks. Linear greenways along watercourses. Playing fields and sports parks.
- **Roundabout gardens:** 15–30 m diameter planted circles at major intersections in European cities; not a true park but contributes visual greenery.

---

## 5. Landmark and Density Anchors

### What Makes a City Feel Non-Gamey

The most commonly cited problem in academic procedural city surveys (including Parish & Müller 2001, SIGGRAPH; and the CityGen survey) is **global homogeneity** — when every block is the same size and every street is the same width. Real cities are non-homogeneous because they evolved through time, so multiple historical layers coexist.

**Specific non-gamey properties to target:**

1. **Irregular block sizes:** Even in formally planned grids (Manhattan, Barcelona Eixample), variance exists. The Eixample has blocks of exactly 113 m, but the street grid was superimposed over irregular terrain and older paths, producing edge conditions. In Manhattan, avenue-to-avenue spacing varies from ~180 m to ~280 m within the same grid. A purely uniform block grid reads as artificial.

2. **Landmark anchors:** Civic buildings (city hall, cathedral, train station, market) break the block pattern. They occupy 1–4 blocks, are set back from the street with a plaza, and orient adjacent street geometry toward them. They should be placed before the street grid is generated, with the grid bending to accommodate them.

3. **Irregular lot lines inside blocks:** Real parcels are not uniform rectangles. Historic cores have lots that taper, wedge, or abut at odd angles because they predate the street grid. A block interior that shows perfectly uniform lot subdivisions reads as fake.

4. **Street width variety within tier:** Even local streets aren't all 9 m — a historic lane might be 4 m, while a newer local access street is 12 m. Introducing width variation of ±2–4 m within a tier adds authenticity.

### Density Transitions Between Zones

Real cities do not have sharp hard-coded zoning boundaries (except where a highway or river creates a hard edge). The transition from CBD to mixed-use to residential is a **gradient of 3–5 blocks** wide. Key observable signals of transition:

- Building height drops by 1–2 stories per block away from CBD peak
- Ground-floor retail (mixed-use) thins out along collector streets, persisting for 2–4 blocks into residential before disappearing
- Block size increases slightly (less subdivision pressure)
- Street tree coverage increases as you move outward

**Mixed-use corridor pattern:** A collector or minor arterial becomes a "high street" / "main street" with ground-floor retail for a linear distance of 400–1,200 m through a residential zone. This is how commercial uses penetrate residential without zone boundaries — they follow the road hierarchy, not a zone polygon.

---

## 6. Quantitative Summary Table

| Zone | Block Width (m) | Block Depth (m) | Dead-End % | Park Ratio | Sidewalk Coverage |
|---|---|---|---|---|---|
| Historic Core / CBD | 60–120 | 80–275 | < 5% | 1 per 15–20 blocks (plazas) | 100% both sides |
| Mixed-Use Midtown | 80–150 | 80–180 | 5–10% | 1 per 8–12 blocks | 100% both sides |
| Residential Grid | 80–180 | 120–275 | 10–20% | 1 per 6–10 blocks | Both sides on locals; may drop on privates |
| Residential Cul-de-Sac Suburb | Irregular (150–400 m cells) | Irregular | 40–55% of internal streets | 1 per 10–20 blocks | Only on collector feeders; absent on culs |
| Gated / Private Court | 100–300 m enclosure | n/a | 100% (by definition) | Shared internal amenity only | None on internal roads |

**Notes on dead-end %:** This is % of residential street segments that terminate without through-connection. In purely European-grid neighborhoods, this approaches 0%. In post-war American subdivisions, it can exceed 50% of all local street segments.

---

## 7. Key Takeaways for Game Developers

### Top 5 Most Impactful Implementations for Realism

**1. Multi-tier road widths with strict hierarchy rules**
Don't give every street the same width. Implement at minimum three distinct visual widths: arterial (~30 m ROW), collector (~18 m), local (~10 m), with private lanes (~6 m) as an optional fourth. Connections must respect hierarchy: privates connect only to locals or collectors, never directly to arterials. This single change has the largest visual impact.

**2. Non-uniform block sizing with zone-based parameters**
Use different block-size distributions per zone. CBD zone: blocks drawn from a 70–130 m distribution. Residential: 100–200 m. Drive the generator with noise rather than a static grid — even Barcelona's famous 113 m grid has perceptible irregularity at its edges. Add ±15–20% jitter to block dimensions.

**3. Cul-de-sac injection in residential zones only**
Residential zones should have 20–40% of their local street network terminate as cul-de-sacs. Use standard bulb dimensions: 27 m diameter bulb, max 180 m length. Never place cul-de-sacs in grid cores or commercial zones.

**4. Landmark-first generation order**
Place 3–7 landmark buildings (train station, city hall, market, cathedral, park) before generating streets. These anchor the street geometry. Roads should bend slightly toward them, creating irregular approach angles — the opposite of the gamey "landmark drops into a perfect grid" problem.

**5. Park distribution with type-by-zone logic**
CBD: hard-surface plazas (0.1–0.5 ha) at civic nodes. Residential: green neighborhood parks (0.5–2 ha) every 6–10 blocks. Do not scatter parks uniformly — cluster 2–3 small parks within a neighborhood catchment, then leave longer gaps. This matches the uneven real-world distribution that comes from land acquisition patterns.

### Common Mistakes Game Generators Make vs. Real Cities

| Generator Mistake | Real City Behavior |
|---|---|
| All streets same width | 4–5 distinct width tiers with strict connection rules |
| Perfect rectangular grid everywhere | Grids exist only in planned expansions; organic cores are irregular; diagonal streets follow topography or old paths |
| Uniform block sizes city-wide | Block size varies 3–4× across zones and shrinks toward historic core |
| Parks evenly distributed every N blocks | Parks cluster near schools/civic buildings; CBD has plazas not grass |
| Sharp zone boundaries (ring 1 = CBD, ring 2 = res) | 3–5 block gradient transitions; commercial uses bleed along collector streets |
| Dead ends absent or universal | Dead ends (cul-de-sacs) are zone-specific — rare in grids, dominant in suburbs |
| Civic buildings in random lots | Civic buildings occupy block-scale footprints with fronting plaza; placed at intersections of at least two collector-level roads |

### What Players Notice Most When a City Feels "Fake"

1. **Street uniformity** — the single widest avenue looks the same as the back alley
2. **Too-regular blocks** — players pattern-match the repetition within seconds of aerial view
3. **Absent transition zones** — stepping from residential into CBD in one block feels like a map seam, not a city
4. **Missing landmarks** — no building that "couldn't be anywhere else"; the city has no visual hierarchy or orientation points
5. **Parks as decorative squares** — parks that are perfectly rectangular, identically sized, and uniformly distributed read as UI elements, not urban spaces

---

## Sources

- [Parish & Müller, "Procedural Modeling of Cities," SIGGRAPH 2001](https://www.researchgate.net/publication/220720591_Procedural_Modeling_of_Cities) — foundational L-system city generation; local constraint rules for junctions
- [Cerdà Plan — Wikipedia](https://en.wikipedia.org/wiki/The_Cerd%C3%A1_Plan) — Barcelona Eixample 113 m block dimensions, 20 m street widths
- [Eixample — Wikipedia](https://en.wikipedia.org/wiki/Eixample) — Passeig de Gràcia 60 m width, district organization into 20-block units
- [City Block — Wikipedia](https://en.wikipedia.org/wiki/City_block) — Manhattan 80 m × 229–274 m; Buenos Aires 110 m × 110 m
- [Haussmann's Renovation of Paris — Wikipedia](https://en.wikipedia.org/wiki/Haussmann%27s_renovation_of_Paris) — boulevard widths 24–30 m; building frontage 15 m
- [Breaking Down Haussmann's Paris, Urban Notes (PubPub)](https://urban.pubpub.org/pub/haussmann/release/3) — building depth 7–13 m; footprint coefficient 66% Opera district
- [Tokyo Block Size Distribution — ResearchGate](https://www.researchgate.net/publication/320217546_Size_distribution_of_urban_blocks_in_the_Tokyo_Metropolitan_Region_estimation_by_urban_block_density_and_road_width_on_the_basis_of_normative_plane_tessellation) — ~4,800 m² average commercial block; log-normal plot distribution
- [Reconsidering the Cul-de-Sac, ACCESS Magazine, Spring 2004](https://accessmagazine.org/spring-2004/reconsidering-cul-de-sac/) — ITE recommendation of discontinuous street systems; Radburn 25% utility saving; 50+ year dominance in North American suburbs
- [Standards for Outdoor Recreational Areas, APA PAS Report 194](https://www.planning.org/pas/reports/report194.htm) — 6.25–10.5 acres/1,000 pop system minimum; neighborhood park 0.6 ha/1,000 pop
- [NACTO Urban Street Design Guide — Lane Width](https://nacto.org/publication/urban-street-design-guide/street-design-elements/lane-width/) — 10–11 ft (3.0–3.35 m) lane widths; arterial sidewalk minimum 3.0 m
- [Minimum Cul-de-Sac Standards (various municipal codes)](https://content.civicplus.com/api/assets/6b229d8a-dd0c-4c3f-b72e-e1505c41e376) — 100 ft ROW diameter; 80 ft pavement diameter; 1,200 ft max length
- [Multi-level Street-Block Divisions of 985 Cities Worldwide — Scientific Data (Nature)](https://www.nature.com/articles/s41597-025-04704-7) — global OSM-derived block dataset; 24 m typical urban road; 8 m residential road
- [Street Hierarchy — Wikipedia](https://en.wikipedia.org/wiki/Street_hierarchy) — functional classification; Roman city street widths as historic baseline
- [CNU Great Idea: The Rural-to-Urban Transect](https://www.cnu.org/publicsquare/2017/04/13/great-idea-rural-urban-transect) — T1–T6 transect zones for density gradient modeling
- [A Survey of Procedural Techniques for City Generation — CityGen.net](https://www.citygen.net/files/images/Procedural_City_Generation_Survey.pdf) — survey of procedural city generation literature

---

*Report length: ~2,400 words. All measurements are metric unless otherwise noted. All percentages are empirically derived from cited sources or are conservative estimates from aggregate planning literature.*
