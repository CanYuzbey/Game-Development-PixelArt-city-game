#include "mapping_algorithm/map_generator.hpp"

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

using namespace mapping_algorithm;
namespace fs = std::filesystem;

namespace {

std::string escape_json(std::string_view value) {
    std::ostringstream out;
    for (const char ch : value) {
        switch (ch) {
            case '\\': out << "\\\\"; break;
            case '"': out << "\\\""; break;
            case '\n': out << "\\n"; break;
            case '\r': out << "\\r"; break;
            case '\t': out << "\\t"; break;
            default: out << ch; break;
        }
    }
    return out.str();
}

void write_string_array(std::ostream& out, const std::vector<std::string>& values) {
    out << "[";
    for (std::size_t i = 0; i < values.size(); ++i) {
        if (i != 0) {
            out << ", ";
        }
        out << "\"" << escape_json(values[i]) << "\"";
    }
    out << "]";
}

std::string default_output_name(std::uint32_t seed) {
    std::ostringstream out;
    out << "city_seed_" << seed << ".json";
    return out.str();
}

void print_usage() {
    std::cerr << "usage: mapping_city_exporter [--seed N] [--width W] [--height H]\n"
              << "                             [--profile ID] [--coast SIDE] [--out FILE]\n";
}

MapConfig parse_args(int argc, char** argv, fs::path& output_path) {
    MapConfig config;
    output_path = default_output_name(config.master_seed);
    bool explicit_output = false;

    for (int i = 1; i < argc; ++i) {
        const std::string key = argv[i];
        auto require_value = [&](const char* flag) -> std::string {
            if (i + 1 >= argc) {
                throw std::invalid_argument(std::string("missing value for ") + flag);
            }
            return argv[++i];
        };

        if (key == "--seed") {
            config.master_seed = static_cast<std::uint32_t>(std::stoul(require_value("--seed")));
            if (!explicit_output) {
                output_path = default_output_name(config.master_seed);
            }
        } else if (key == "--width") {
            config.width = std::stoi(require_value("--width"));
        } else if (key == "--height") {
            config.height = std::stoi(require_value("--height"));
        } else if (key == "--profile") {
            config.city_profile = require_value("--profile");
        } else if (key == "--coast") {
            config.coast_side = coast_side_from_string(require_value("--coast"));
        } else if (key == "--out") {
            output_path = require_value("--out");
            explicit_output = true;
        } else if (key == "--help" || key == "-h") {
            print_usage();
            std::exit(EXIT_SUCCESS);
        } else {
            throw std::invalid_argument("unknown argument: " + key);
        }
    }
    return config;
}

void write_stats(std::ostream& out, const MapStats& stats) {
    out << "  \"stats\": {\n"
        << "    \"seed\": " << stats.seed << ",\n"
        << "    \"width\": " << stats.width << ",\n"
        << "    \"height\": " << stats.height << ",\n"
        << "    \"land\": " << stats.land << ",\n"
        << "    \"water\": " << stats.water << ",\n"
        << "    \"roads\": " << stats.roads << ",\n"
        << "    \"sidewalks\": " << stats.sidewalks << ",\n"
        << "    \"blocks\": " << stats.blocks << ",\n"
        << "    \"parks\": " << stats.parks << ",\n"
        << "    \"lots\": " << stats.lots << ",\n"
        << "    \"spawns\": " << stats.spawns << ",\n"
        << "    \"landmarks\": " << stats.landmarks << ",\n"
        << "    \"buildings\": " << stats.buildings << "\n"
        << "  },\n";
}

void write_profile(std::ostream& out, const CityProfile& profile) {
    out << "  \"profile\": {\n"
        << "    \"id\": \"" << escape_json(profile.id) << "\",\n"
        << "    \"label\": \"" << escape_json(profile.label) << "\",\n"
        << "    \"street_pattern\": \"" << escape_json(profile.street_pattern) << "\",\n"
        << "    \"block_ratio\": \"" << escape_json(profile.block_ratio) << "\",\n"
        << "    \"design_tags\": ";
    write_string_array(out, profile.design_tags);
    out << ",\n    \"asset_style_tags\": ";
    write_string_array(out, profile.asset_style_tags);
    out << "\n  },\n";
}

void write_roads(std::ostream& out, const std::vector<RoadRecord>& roads) {
    out << "  \"roads\": [\n";
    for (std::size_t i = 0; i < roads.size(); ++i) {
        const auto& road = roads[i];
        out << "    {\"row\": " << road.row
            << ", \"col\": " << road.col
            << ", \"category\": \"" << escape_json(road.category)
            << "\", \"bitmask\": " << road.bitmask
            << ", \"zone\": \"" << escape_json(road.zone)
            << "\", \"intersection\": " << (road.is_intersection ? "true" : "false")
            << ", \"asset_slot\": \"" << escape_json(road.asset_slot) << "\"}";
        out << (i + 1 == roads.size() ? "\n" : ",\n");
    }
    out << "  ],\n";
}

void write_blocks(std::ostream& out, const std::vector<BlockRecord>& blocks) {
    out << "  \"blocks\": [\n";
    for (std::size_t i = 0; i < blocks.size(); ++i) {
        const auto& block = blocks[i];
        out << "    {\"id\": " << block.id
            << ", \"area\": " << block.area
            << ", \"bounds\": [" << block.r0 << ", " << block.c0 << ", " << block.r1 << ", " << block.c1 << "]"
            << ", \"zone\": \"" << escape_json(block.zone)
            << "\", \"park\": " << (block.is_park ? "true" : "false") << "}";
        out << (i + 1 == blocks.size() ? "\n" : ",\n");
    }
    out << "  ],\n";
}

void write_lots(std::ostream& out, const std::vector<LotRecord>& lots) {
    out << "  \"lots\": [\n";
    for (std::size_t i = 0; i < lots.size(); ++i) {
        const auto& lot = lots[i];
        out << "    {\"id\": " << lot.id
            << ", \"block_id\": " << lot.block_id
            << ", \"area\": " << lot.area
            << ", \"zone\": \"" << escape_json(lot.zone)
            << "\", \"building_type\": \"" << escape_json(lot.building_type)
            << "\", \"landmark_type\": \"" << escape_json(lot.landmark_type)
            << "\", \"asset_slot\": \"" << escape_json(lot.asset_slot) << "\"}";
        out << (i + 1 == lots.size() ? "\n" : ",\n");
    }
    out << "  ],\n";
}

void write_landmarks(std::ostream& out, const std::vector<LandmarkRecord>& landmarks) {
    out << "  \"landmarks\": [\n";
    for (std::size_t i = 0; i < landmarks.size(); ++i) {
        const auto& landmark = landmarks[i];
        out << "    {\"type\": \"" << escape_json(landmark.type)
            << "\", \"row\": " << landmark.row
            << ", \"col\": " << landmark.col
            << ", \"asset_slot\": \"" << escape_json(landmark.asset_slot) << "\"}";
        out << (i + 1 == landmarks.size() ? "\n" : ",\n");
    }
    out << "  ],\n";
}

void write_buildings(std::ostream& out, const std::vector<BuildingAssemblyRecord>& buildings) {
    out << "  \"buildings\": [\n";
    for (std::size_t i = 0; i < buildings.size(); ++i) {
        const auto& building = buildings[i];
        out << "    {\"id\": " << building.id
            << ", \"lot_id\": " << building.lot_id
            << ", \"block_id\": " << building.block_id
            << ", \"anchor\": [" << building.anchor_row << ", " << building.anchor_col << "]"
            << ", \"footprint\": [" << building.footprint_r0 << ", " << building.footprint_c0
            << ", " << building.footprint_r1 << ", " << building.footprint_c1 << "]"
            << ", \"floors\": " << building.floors
            << ", \"zone\": \"" << escape_json(building.zone)
            << "\", \"building_type\": \"" << escape_json(building.building_type)
            << "\", \"landmark_type\": \"" << escape_json(building.landmark_type)
            << "\", \"footprint_style\": \"" << escape_json(building.footprint_style)
            << "\", \"facade_family\": \"" << escape_json(building.facade_family)
            << "\", \"roof_type\": \"" << escape_json(building.roof_type)
            << "\", \"asset_slot\": \"" << escape_json(building.asset_slot)
            << "\", \"sprite_stack\": ";
        write_string_array(out, building.sprite_stack);
        out << "}";
        out << (i + 1 == buildings.size() ? "\n" : ",\n");
    }
    out << "  ],\n";
}

void write_sprite_assignments(std::ostream& out, const std::vector<SpriteAssignmentRecord>& assignments) {
    out << "  \"sprite_assignments\": [\n";
    for (std::size_t i = 0; i < assignments.size(); ++i) {
        const auto& assignment = assignments[i];
        out << "    {\"target_kind\": \"" << escape_json(assignment.target_kind)
            << "\", \"target_id\": " << assignment.target_id
            << ", \"row\": " << assignment.row
            << ", \"col\": " << assignment.col
            << ", \"asset_slot\": \"" << escape_json(assignment.asset_slot)
            << "\", \"sprite_ids\": ";
        write_string_array(out, assignment.sprite_ids);
        out << ", \"reason\": \"" << escape_json(assignment.reason)
            << "\", \"decision_hash\": " << assignment.decision_hash << "}";
        out << (i + 1 == assignments.size() ? "\n" : ",\n");
    }
    out << "  ],\n";
}

void write_cells(std::ostream& out, const MapGrid& grid) {
    out << "  \"cells\": [\n";
    bool first = true;
    out << std::fixed << std::setprecision(3);
    for (int r = 0; r < grid.height(); ++r) {
        for (int c = 0; c < grid.width(); ++c) {
            if (!first) {
                out << ",\n";
            }
            first = false;
            const auto& cell = grid.at(r, c);
            out << "    {\"row\": " << r
                << ", \"col\": " << c
                << ", \"role\": \"" << escape_json(cell.tile_role)
                << "\", \"zone\": \"" << escape_json(to_string(cell.zone_id))
                << "\", \"road\": \"" << escape_json(to_string(cell.road_category))
                << "\", \"block_id\": " << cell.block_id
                << ", \"lot_id\": " << cell.lot_id
                << ", \"land\": " << (cell.is_land ? "true" : "false")
                << ", \"water\": " << (cell.is_water ? "true" : "false")
                << ", \"park\": " << (cell.is_park ? "true" : "false")
                << ", \"setback\": " << (cell.is_setback ? "true" : "false")
                << ", \"spawn\": " << (cell.is_spawn_point ? "true" : "false")
                << ", \"coast\": \"" << escape_json(cell.coast_type)
                << "\", \"building_type\": \"" << escape_json(cell.building_type)
                << "\", \"landmark_type\": \"" << escape_json(cell.landmark_type)
                << "\", \"footprint_style\": \"" << escape_json(cell.footprint_style)
                << "\", \"district\": \"" << escape_json(cell.district_name)
                << "\", \"density\": " << cell.density_score
                << ", \"elevation\": " << cell.elevation
                << ", \"encounter_chance\": " << cell.encounter_chance
                << "}";
        }
    }
    out << "\n  ]\n";
}

void write_city_json(const fs::path& path, const MapGenerator& generator, const DesignBlueprint& blueprint) {
    if (path.has_parent_path()) {
        fs::create_directories(path.parent_path());
    }
    std::ofstream out(path);
    if (!out) {
        throw std::runtime_error("cannot write output file: " + path.string());
    }

    out << "{\n"
        << "  \"schema\": \"deployable_city_map.v1\",\n"
        << "  \"algorithm_version\": \"" << escape_json(blueprint.algorithm_version) << "\",\n"
        << "  \"resolved_coast_side\": \"" << escape_json(blueprint.resolved_coast_side) << "\",\n";
    write_stats(out, generator.stats());
    write_profile(out, blueprint.profile);
    out << "  \"required_asset_slots\": ";
    write_string_array(out, blueprint.required_asset_slots);
    out << ",\n";
    write_roads(out, blueprint.roads);
    write_blocks(out, blueprint.blocks);
    write_lots(out, blueprint.lots);
    write_landmarks(out, blueprint.landmarks);
    write_buildings(out, blueprint.buildings);
    write_sprite_assignments(out, blueprint.sprite_assignments);
    write_cells(out, generator.grid());
    out << "}\n";
}

} // namespace

int main(int argc, char** argv) {
    try {
        fs::path output_path;
        const MapConfig config = parse_args(argc, argv, output_path);
        MapGenerator generator(config);
        generator.generate();
        const auto blueprint = generator.to_design_blueprint();
        write_city_json(output_path, generator, blueprint);

        const auto& stats = generator.stats();
        std::cout << "exported " << output_path.string()
                  << " seed=" << stats.seed
                  << " size=" << stats.width << "x" << stats.height
                  << " buildings=" << stats.buildings
                  << " roads=" << stats.roads
                  << " landmarks=" << stats.landmarks
                  << " coast=" << blueprint.resolved_coast_side
                  << "\n";
        return EXIT_SUCCESS;
    } catch (const std::exception& ex) {
        std::cerr << "mapping_city_exporter failed: " << ex.what() << "\n";
        print_usage();
        return EXIT_FAILURE;
    }
}
