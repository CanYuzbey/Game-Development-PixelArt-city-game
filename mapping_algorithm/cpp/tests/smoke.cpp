#include "mapping_algorithm/map_generator.hpp"

#include <cstdlib>
#include <iostream>

using namespace mapping_algorithm;

int main() {
    MapConfig config;
    config.width = 64;
    config.height = 48;
    config.master_seed = 42;
    config.coast_side = CoastSide::East;
    config.city_profile = "barcelona_eixample";

    MapGenerator a(config);
    a.generate();
    MapGenerator b(config);
    b.generate();

    const auto& sa = a.stats();
    const auto& sb = b.stats();
    if (sa.land != sb.land || sa.water != sb.water || sa.roads != sb.roads ||
        sa.blocks != sb.blocks || sa.lots != sb.lots || sa.landmarks != sb.landmarks) {
        std::cerr << "determinism smoke failed\n";
        return EXIT_FAILURE;
    }

    const auto blueprint = a.to_design_blueprint();
    if (blueprint.schema != "city_design_blueprint.v1" ||
        blueprint.profile.id != "barcelona_eixample" ||
        blueprint.roads.empty() ||
        blueprint.required_asset_slots.empty()) {
        std::cerr << "design blueprint smoke failed\n";
        return EXIT_FAILURE;
    }

    std::cout << "mapping_algorithm_smoke ok\n";
    return EXIT_SUCCESS;
}
