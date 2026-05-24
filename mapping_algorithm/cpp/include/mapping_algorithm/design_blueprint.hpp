#pragma once

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

struct DesignBlueprint {
    std::string schema = "city_design_blueprint.v1";
    CityProfile profile;
    int width = 0;
    int height = 0;
    std::vector<RoadRecord> roads;
    std::vector<BlockRecord> blocks;
    std::vector<LotRecord> lots;
    std::vector<LandmarkRecord> landmarks;
    std::vector<std::string> required_asset_slots;
};

} // namespace mapping_algorithm
