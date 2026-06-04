#include "mapping_algorithm/map_generator.hpp"
#include "mapping_algorithm/world_generator.hpp"

#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <map>
#include <queue>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

using namespace mapping_algorithm;

// Lightweight assertion macro for smoke tests
#define CHECK(condition, message) \
    do { \
        if (!(condition)) { \
            std::cerr << "CHECK FAILED: " << (message) << "\n"; \
            return false; \
        } \
    } while (false)

namespace {

using Point = std::pair<int, int>;

bool same_stats(const MapStats& a, const MapStats& b) {
    return a.land == b.land &&
           a.water == b.water &&
           a.roads == b.roads &&
           a.sidewalks == b.sidewalks &&
           a.blocks == b.blocks &&
           a.lots == b.lots &&
           a.parks == b.parks &&
           a.spawns == b.spawns &&
           a.landmarks == b.landmarks &&
           a.buildings == b.buildings;
}

bool has_slot(const DesignBlueprint& blueprint, const std::string& slot) {
    return std::find(blueprint.required_asset_slots.begin(), blueprint.required_asset_slots.end(), slot) !=
           blueprint.required_asset_slots.end();
}

std::vector<Point> neighbours4(int r, int c) {
    return {{r - 1, c}, {r + 1, c}, {r, c - 1}, {r, c + 1}};
}

bool validate_road_local_connectivity(const MapGrid& grid, const MapConfig& config) {
    for (int r = 0; r < grid.height(); ++r) {
        for (int c = 0; c < grid.width(); ++c) {
            const auto& cell = grid.at(r, c);
            if (!cell.is_road()) {
                continue;
            }
            int neighbours = 0;
            for (const auto [nr, nc] : neighbours4(r, c)) {
                if (grid.in_bounds(nr, nc) && grid.at(nr, nc).is_road()) {
                    ++neighbours;
                }
            }
            if (neighbours == 0) {
                std::cerr << "isolated road cell at r=" << r << " c=" << c
                          << " seed=" << config.master_seed
                          << " profile=" << config.city_profile << "\n";
                return false;
            }
        }
    }
    return true;
}

bool validate_lot_connectivity(const MapGrid& grid, const MapConfig& config) {
    std::map<int, std::set<Point>> lots;
    for (int r = 0; r < grid.height(); ++r) {
        for (int c = 0; c < grid.width(); ++c) {
            const auto& cell = grid.at(r, c);
            if (cell.lot_id >= 0) {
                lots[cell.lot_id].insert({r, c});
            }
        }
    }

    for (const auto& [lot_id, cells] : lots) {
        if (cells.empty()) {
            continue;
        }
        std::set<Point> visited;
        std::queue<Point> q;
        q.push(*cells.begin());
        visited.insert(*cells.begin());
        while (!q.empty()) {
            const auto [r, c] = q.front();
            q.pop();
            for (const auto np : neighbours4(r, c)) {
                if (cells.count(np) && !visited.count(np)) {
                    visited.insert(np);
                    q.push(np);
                }
            }
        }
        if (visited.size() != cells.size()) {
            std::cerr << "non-contiguous lot_id=" << lot_id
                      << " seed=" << config.master_seed
                      << " profile=" << config.city_profile << "\n";
            return false;
        }
    }
    return true;
}

struct ZoneCounts { int cbd = 0; int midtown = 0; int residential = 0; };

ZoneCounts count_zones(const MapGrid& grid) {
    ZoneCounts counts;
    for (int r = 0; r < grid.height(); ++r) {
        for (int c = 0; c < grid.width(); ++c) {
            const auto& cell = grid.at(r, c);
            if (!cell.is_land) continue;
            if (cell.zone_id == ZoneId::CBD) ++counts.cbd;
            else if (cell.zone_id == ZoneId::Midtown) ++counts.midtown;
            else if (cell.zone_id == ZoneId::Residential) ++counts.residential;
        }
    }
    return counts;
}

bool validate_config(const MapConfig& config) {
    MapGenerator a(config);
    a.generate();
    MapGenerator b(config);
    b.generate();

    const auto& stats = a.stats();
    if (!same_stats(stats, b.stats())) {
        std::cerr << "determinism failed for seed=" << config.master_seed
                  << " coast=" << to_string(config.coast_side) << "\n";
        return false;
    }
    MapGenerator reusable(config);
    reusable.generate();
    const auto first = reusable.stats();
    reusable.generate();
    if (!same_stats(first, reusable.stats())) {
        std::cerr << "same-generator rerun failed for seed=" << config.master_seed
                  << " coast=" << to_string(config.coast_side) << "\n";
        return false;
    }

    if (stats.land <= 0 || stats.roads <= 0 || stats.blocks <= 0 || stats.lots <= 0) {
        std::cerr << "empty city structure for seed=" << config.master_seed
                  << " coast=" << to_string(config.coast_side) << "\n";
        return false;
    }
    if (stats.parks <= 0 || stats.landmarks <= 0 || stats.spawns <= 0 || stats.buildings <= 0) {
        std::cerr << "missing gameplay layer for seed=" << config.master_seed
                  << " coast=" << to_string(config.coast_side) << "\n";
        return false;
    }
    const double road_ratio = static_cast<double>(stats.roads) / static_cast<double>(stats.land);
    if (road_ratio < 0.05 || road_ratio > 0.50) {
        std::cerr << "road density outside guard rails for seed=" << config.master_seed
                  << " coast=" << to_string(config.coast_side)
                  << " ratio=" << road_ratio << "\n";
        return false;
    }

    const auto blueprint = a.to_design_blueprint();
    if (blueprint.schema != "city_design_blueprint.v2" ||
        blueprint.profile.id != config.city_profile ||
        blueprint.roads.empty() ||
        blueprint.blocks.empty() ||
        blueprint.lots.empty() ||
        blueprint.buildings.empty() ||
        blueprint.sprite_assignments.empty() ||
        blueprint.required_asset_slots.empty()) {
        std::cerr << "design blueprint failed for seed=" << config.master_seed
                  << " coast=" << to_string(config.coast_side) << "\n";
        return false;
    }
    if (blueprint.seed != config.master_seed ||
        blueprint.resolved_coast_side == "random" ||
        blueprint.buildings.size() != static_cast<std::size_t>(stats.buildings) ||
        blueprint.sprite_assignments.size() != blueprint.buildings.size()) {
        std::cerr << "inspectable blueprint mismatch for seed=" << config.master_seed
                  << " coast=" << to_string(config.coast_side) << "\n";
        return false;
    }
    if (!has_slot(blueprint, "street/road") ||
        !has_slot(blueprint, "building/roof") ||
        !has_slot(blueprint, "overlay/shadow") ||
        has_slot(blueprint, "road/highway") ||
        has_slot(blueprint, "road/connector")) {
        std::cerr << "asset slot contract mismatch for seed=" << config.master_seed
                  << " coast=" << to_string(config.coast_side) << "\n";
        return false;
    }
    for (const auto& building : blueprint.buildings) {
        if (building.lot_id < 0 || building.sprite_stack.empty() || building.asset_slot.empty()) {
            std::cerr << "incomplete building assembly for seed=" << config.master_seed
                      << " coast=" << to_string(config.coast_side) << "\n";
            return false;
        }
    }

    if (!validate_road_local_connectivity(a.grid(), config)) {
        return false;
    }
    if (!validate_lot_connectivity(a.grid(), config)) {
        return false;
    }

    // At least some block cells should have street_facing set (perimeter tagging)
    {
        bool found_facing = false;
        for (int r = 0; r < a.grid().height() && !found_facing; ++r) {
            for (int c = 0; c < a.grid().width() && !found_facing; ++c) {
                if (!a.grid().at(r, c).street_facing.empty()) found_facing = true;
            }
        }
        if (a.stats().blocks > 0) {
            CHECK(found_facing, "Perimeter tagging: at least one cell has street_facing set");
        }
    }

    // Zone ratio sanity: CBD must be 5-60% of land, Residential must be at least 10%.
    const auto zones = count_zones(a.grid());
    const int total_zoned = zones.cbd + zones.midtown + zones.residential;
    if (total_zoned > 0) {
        const double cbd_pct = static_cast<double>(zones.cbd) / total_zoned;
        const double resi_pct = static_cast<double>(zones.residential) / total_zoned;
        if (cbd_pct < 0.05 || cbd_pct > 0.60) {
            std::cerr << "CBD zone ratio out of range (" << cbd_pct << ") for seed="
                      << config.master_seed << " profile=" << config.city_profile << "\n";
            return false;
        }
        if (resi_pct < 0.10) {
            std::cerr << "Residential zone too small (" << resi_pct << ") for seed="
                      << config.master_seed << " profile=" << config.city_profile << "\n";
            return false;
        }
    }

    if (config.city_profile == "barcelona_eixample") {
        if (blueprint.buildings.empty()) {
            std::cerr << "barcelona profile produced no buildings for seed=" << config.master_seed << "\n";
            return false;
        }
    }

    // Lot uniqueness: each lot_id must appear in at most one building.
    {
        std::set<int> seen_lot_ids;
        for (const auto& building : blueprint.buildings) {
            if (seen_lot_ids.count(building.lot_id)) {
                std::cerr << "duplicate lot_id=" << building.lot_id << " in buildings for seed="
                          << config.master_seed << "\n";
                return false;
            }
            seen_lot_ids.insert(building.lot_id);
        }
    }

    // Spawn point check: every map must have at least one spawn point.
    if (stats.spawns <= 0) {
        std::cerr << "no spawn points for seed=" << config.master_seed
                  << " coast=" << to_string(config.coast_side) << "\n";
        return false;
    }

    return true;
}

bool validate_rejections() {
    auto rejects = [](MapConfig invalid, const std::string& label) {
        try {
            MapGenerator generator(invalid);
            generator.generate();
        } catch (const std::invalid_argument&) {
            return true;
        }
        std::cerr << label << " was accepted\n";
        return false;
    };

    bool ok = true;

    MapConfig invalid_spacing;
    invalid_spacing.connector_spacing = 0;
    ok = rejects(invalid_spacing, "invalid connector spacing") && ok;

    MapConfig invalid_profile;
    invalid_profile.city_profile = "unknown_profile";
    ok = rejects(invalid_profile, "unknown city profile") && ok;

    MapConfig invalid_density;
    invalid_density.connector_density = 1.5;
    ok = rejects(invalid_density, "invalid connector density") && ok;

    MapConfig invalid_dimensions;
    invalid_dimensions.width = 513;
    ok = rejects(invalid_dimensions, "oversized map dimensions") && ok;

    MapConfig invalid_sidewalk_damage;
    invalid_sidewalk_damage.sidewalk_damage_rate = -0.1;
    ok = rejects(invalid_sidewalk_damage, "invalid sidewalk damage rate") && ok;

    return ok;
}

bool validate_large_map() {
    // Exercises the O(n) BFS civic anchor path and verifies correctness at 256x256.
    MapConfig config;
    config.width = 256;
    config.height = 256;
    config.master_seed = 42;
    config.coast_side = CoastSide::West;
    config.city_profile = "manhattan";

    MapGenerator gen(config);
    gen.generate();
    const auto& stats = gen.stats();

    if (stats.land <= 0 || stats.roads <= 0 || stats.blocks <= 0 ||
        stats.lots <= 0 || stats.buildings <= 0) {
        std::cerr << "large map (256x256) produced empty city\n";
        return false;
    }
    const double road_ratio = static_cast<double>(stats.roads) / static_cast<double>(stats.land);
    if (road_ratio < 0.05 || road_ratio > 0.50) {
        std::cerr << "large map road density out of range: " << road_ratio << "\n";
        return false;
    }
    // Verify determinism on large map
    MapGenerator gen2(config);
    gen2.generate();
    if (stats.land != gen2.stats().land || stats.buildings != gen2.stats().buildings) {
        std::cerr << "large map determinism failed\n";
        return false;
    }
    return true;
}

bool validate_river_bridges() {
    int river_maps = 0;
    for (std::uint32_t seed = 1; seed <= 64; ++seed) {
        MapConfig config;
        config.master_seed = seed;
        config.coast_side = CoastSide::None;

        MapGenerator gen(config);
        gen.generate();
        int water = 0;
        int bridges = 0;
        for (int r = 0; r < gen.grid().height(); ++r) {
            for (int c = 0; c < gen.grid().width(); ++c) {
                const auto& cell = gen.grid().at(r, c);
                if (cell.is_water) ++water;
                if (cell.is_bridge) {
                    ++bridges;
                    if (cell.is_water || !cell.is_land) {
                        std::cerr << "bridge cell is not land for seed=" << seed << "\n";
                        return false;
                    }
                }
            }
        }
        if (water > 0) {
            ++river_maps;
            if (bridges <= 0) {
                std::cerr << "river map missing bridge crossing for seed=" << seed << "\n";
                return false;
            }
        }
    }
    if (river_maps == 0) {
        std::cerr << "river bridge test found no river maps in seed range\n";
        return false;
    }
    return true;
}

bool validate_world_generator() {
    mapping_algorithm::WorldConfig wc;
    wc.world_seed = 0xDEADBEEFU;
    wc.chunk_cols = 8;
    wc.chunk_rows = 6;
    wc.chunk_width = 64; // small for test speed
    wc.chunk_height = 48;
    mapping_algorithm::WorldGenerator wg(wc);
    wg.plan();
    CHECK(wg.chunk_count() == 48, "WorldGenerator: 8x6 = 48 chunks");
    // Verify CBD chunk profile
    const auto& cbd = wg.chunk_at(2, 1);
    CHECK(cbd.city_profile == "manhattan" || cbd.city_profile == "paris_haussmann",
          "WorldGenerator: CBD chunk profile is manhattan or paris_haussmann");
    // Verify corner chunk coast
    const auto& corner = wg.chunk_at(0, 0);
    CHECK(corner.coast_side == mapping_algorithm::CoastSide::North ||
          corner.coast_side == mapping_algorithm::CoastSide::West,
          "WorldGenerator: corner chunk has coastal side");
    // Verify chunk seeds are distinct
    const auto& c00 = wg.chunk_at(0, 0);
    const auto& c10 = wg.chunk_at(1, 0);
    const auto& c01 = wg.chunk_at(0, 1);
    CHECK(c00.chunk_seed != c10.chunk_seed, "WorldGenerator: chunk seeds are distinct (x)");
    CHECK(c00.chunk_seed != c01.chunk_seed, "WorldGenerator: chunk seeds are distinct (y)");
    // Verify config_for_chunk returns correct seed
    const auto cfg = wg.config_for_chunk(2, 1);
    CHECK(cfg.master_seed == wg.chunk_at(2, 1).chunk_seed, "WorldGenerator: config_for_chunk seed matches plan");
    return true;
}

bool validate_terrain_routing() {
    // Highways should prefer low-elevation terrain (valleys over hilltops)
    MapConfig config;
    config.master_seed = 77;
    config.coast_side = CoastSide::None;
    config.width = 80;
    config.height = 60;
    MapGenerator gen(config);
    gen.generate();
    double hw_elev_sum = 0.0, land_elev_sum = 0.0;
    int hw_count = 0, land_count = 0;
    for (int r = 0; r < gen.grid().height(); ++r) {
        for (int c = 0; c < gen.grid().width(); ++c) {
            const auto& cell = gen.grid().at(r, c);
            if (cell.road_category == RoadCategory::Highway) {
                hw_elev_sum += cell.elevation; ++hw_count;
            } else if (cell.is_land && !cell.is_road()) {
                land_elev_sum += cell.elevation; ++land_count;
            }
        }
    }
    if (hw_count > 0 && land_count > 0) {
        const double hw_avg = hw_elev_sum / hw_count;
        const double land_avg = land_elev_sum / land_count;
        CHECK(hw_avg < land_avg,
              "Terrain routing: highway avg elevation must be below land avg elevation");
    }
    return true;
}

bool validate_map_variation() {
    // Different seeds must produce measurably different road networks
    int min_roads = std::numeric_limits<int>::max();
    int max_roads = 0;
    for (std::uint32_t seed = 1; seed <= 6; ++seed) {
        MapConfig config;
        config.master_seed = seed;
        config.coast_side = CoastSide::None;
        config.width = 80;
        config.height = 60;
        MapGenerator gen(config);
        gen.generate();
        min_roads = std::min(min_roads, gen.stats().roads);
        max_roads = std::max(max_roads, gen.stats().roads);
    }
    CHECK(max_roads - min_roads >= 30,
          "Map variation: road counts must differ by >= 30 cells across seeds 1-6");
    return true;
}

} // namespace

int main() {
    const std::vector<CoastSide> coasts = {
        CoastSide::None,
        CoastSide::North,
        CoastSide::South,
        CoastSide::East,
        CoastSide::West,
        CoastSide::Random,
    };
    const std::vector<std::string> profiles = {
        "generic_dense",
        "manhattan",
        "barcelona_eixample",
        "paris_haussmann",
        "london_organic",
    };

    int passed = 0;
    int failed = 0;
    for (std::uint32_t seed = 1; seed <= 12; ++seed) {
        for (std::size_t i = 0; i < coasts.size(); ++i) {
            MapConfig config;
            config.width = 80;
            config.height = 60;
            config.master_seed = seed;
            config.coast_side = coasts[i];
            config.city_profile = profiles[i % profiles.size()];
            if (validate_config(config)) {
                ++passed;
            } else {
                ++failed;
            }
        }
    }
    if (validate_rejections()) {
        ++passed;
    } else {
        ++failed;
    }
    if (validate_large_map()) {
        ++passed;
    } else {
        ++failed;
    }
    if (validate_river_bridges()) {
        ++passed;
    } else {
        ++failed;
    }
    if (validate_world_generator()) {
        ++passed;
    } else {
        ++failed;
    }
    if (validate_terrain_routing()) { ++passed; } else { ++failed; }
    if (validate_map_variation())   { ++passed; } else { ++failed; }

    std::cout << "mapping_algorithm_smoke PASS=" << passed
              << " FAIL=" << failed << "\n";
    if (failed != 0) {
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
