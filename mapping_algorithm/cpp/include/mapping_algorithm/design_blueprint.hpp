#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace mapping_algorithm {

struct CityProfile {
    std::string id;
    std::string label;
    std::string street_pattern;
    std::string block_ratio;
    std::vector<std::string> design_tags;
    std::vector<std::string> asset_style_tags;
};

struct RoadRecord {
    int row = 0;
    int col = 0;
    std::string category;
    int bitmask = 0;
    std::string zone;
    bool is_intersection = false;
    std::string asset_slot;
};

struct BlockRecord {
    int id = -1;
    int area = 0;
    int r0 = 0;
    int c0 = 0;
    int r1 = 0;
    int c1 = 0;
    std::string zone;
    bool is_park = false;
};

struct LotRecord {
    int id = -1;
    int block_id = -1;
    int area = 0;
    std::string zone;
    std::string building_type;
    std::string landmark_type;
    std::string asset_slot;
};

struct LandmarkRecord {
    std::string type;
    int row = 0;
    int col = 0;
    std::string asset_slot;
};

struct BuildingAssemblyRecord {
    int id = -1;
    int lot_id = -1;
    int block_id = -1;
    int anchor_row = 0;
    int anchor_col = 0;
    int footprint_r0 = 0;
    int footprint_c0 = 0;
    int footprint_r1 = 0;
    int footprint_c1 = 0;
    int floors = 1;
    std::string zone;
    std::string building_type;
    std::string landmark_type;
    std::string footprint_style;
    std::string facade_family;
    std::string roof_type;
    std::string asset_slot;
    std::vector<std::string> sprite_stack;
};

struct SpriteAssignmentRecord {
    std::string target_kind;
    int target_id = -1;
    int row = 0;
    int col = 0;
    std::string asset_slot;
    std::vector<std::string> sprite_ids;
    std::string reason;
    std::uint32_t decision_hash = 0;
};

struct DesignBlueprint {
    std::string schema = "city_design_blueprint.v1";
    std::uint32_t seed = 0;
    std::string algorithm_version = "mapping_algorithm_cpp.v2";
    std::string resolved_coast_side;
    CityProfile profile;
    int width = 0;
    int height = 0;
    std::vector<RoadRecord> roads;
    std::vector<BlockRecord> blocks;
    std::vector<LotRecord> lots;
    std::vector<LandmarkRecord> landmarks;
    std::vector<BuildingAssemblyRecord> buildings;
    std::vector<SpriteAssignmentRecord> sprite_assignments;
    std::vector<std::string> required_asset_slots;
};

} // namespace mapping_algorithm
