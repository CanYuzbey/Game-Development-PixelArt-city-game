#include "mapping_algorithm/map_generator.hpp"

#include <iostream>

using namespace mapping_algorithm;

int main() {
    MapConfig config;
    config.width = 80;
    config.height = 60;
    config.master_seed = 7;
    config.coast_side = CoastSide::West;
    config.city_profile = "manhattan";

    MapGenerator generator(config);
    generator.generate();
    const auto& stats = generator.stats();
    const auto blueprint = generator.to_design_blueprint();

    std::cout << "seed=" << stats.seed
              << " size=" << stats.width << "x" << stats.height
              << " land=" << stats.land
              << " water=" << stats.water
              << " roads=" << stats.roads
              << " blocks=" << stats.blocks
              << " lots=" << stats.lots
              << " buildings=" << stats.buildings
              << " landmarks=" << stats.landmarks
              << " profile=" << blueprint.profile.id
              << " coast=" << blueprint.resolved_coast_side
              << "\n";

    return 0;
}
