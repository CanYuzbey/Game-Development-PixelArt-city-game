#include "mapping_algorithm/map_generator.hpp"

#include <cstdlib>
#include <iostream>
#include <vector>

using namespace mapping_algorithm;

namespace {

bool same_stats(const MapStats& a, const MapStats& b) {
    return a.land == b.land &&
           a.water == b.water &&
           a.roads == b.roads &&
           a.sidewalks == b.sidewalks &&
           a.blocks == b.blocks &&
           a.lots == b.lots &&
           a.parks == b.parks &&
           a.spawns == b.spawns &&
           a.landmarks == b.landmarks;
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
    if (stats.land <= 0 || stats.roads <= 0 || stats.blocks <= 0 || stats.lots <= 0) {
        std::cerr << "empty city structure for seed=" << config.master_seed
                  << " coast=" << to_string(config.coast_side) << "\n";
        return false;
    }
    if (stats.parks <= 0 || stats.landmarks <= 0 || stats.spawns <= 0) {
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
    if (blueprint.schema != "city_design_blueprint.v1" ||
        blueprint.profile.id != config.city_profile ||
        blueprint.roads.empty() ||
        blueprint.blocks.empty() ||
        blueprint.lots.empty() ||
        blueprint.required_asset_slots.empty()) {
        std::cerr << "design blueprint failed for seed=" << config.master_seed
                  << " coast=" << to_string(config.coast_side) << "\n";
        return false;
    }
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

    std::cout << "mapping_algorithm_smoke PASS=" << passed
              << " FAIL=" << failed << "\n";
    if (failed != 0) {
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
