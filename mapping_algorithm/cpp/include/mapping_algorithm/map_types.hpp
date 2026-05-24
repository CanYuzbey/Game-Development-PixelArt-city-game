#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace mapping_algorithm {

enum class CoastSide {
    None,
    North,
    South,
    East,
    West,
    Random
};

enum class ZoneId {
    Unassigned = -1,
    CBD = 0,
    Midtown = 1,
    Residential = 2
};

enum class RoadCategory {
    None,
    Highway,
    Connector
};

struct MapConfig {
    int width = 96;
    int height = 72;
    std::uint32_t master_seed = 1;
    std::string city_profile = "generic_dense";

    CoastSide coast_side = CoastSide::None;
    double coast_coverage = 0.28;
    double coast_noise_scale = 3.5;
    int coast_smoothing_passes = 2;

    int highway_ns_min = 2;
    int highway_ns_max = 5;
    int highway_ew_min = 0;
    int highway_ew_max = 3;
    double highway_organic = 0.3;

    double connector_density = 0.65;
    int connector_spacing = 8;
    int avenue_spacing = 18;
    int min_block_depth = 2;
    double connector_turn_bias = 0.08;
    int roundabout_count = 8;
    int diagonal_streets = 2;
    int sidewalk_depth = 1;
    double sidewalk_damage_rate = 0.15;
};

struct MapCell {
    bool is_water = false;
    bool is_land = false;
    RoadCategory road_category = RoadCategory::None;
    ZoneId zone_id = ZoneId::Unassigned;
    int block_id = -1;
    int lot_id = -1;
    double density_score = 0.0;
    bool is_park = false;
    bool is_civic_anchor = false;
    bool is_setback = false;
    std::string coast_type;
    std::string tile_role;
    std::string building_type;
    double encounter_chance = 0.0;
    bool is_spawn_point = false;
    std::string landmark_type;
    double elevation = 0.0;
    std::string footprint_style;
    std::string district_name;

    bool is_road() const noexcept {
        return road_category != RoadCategory::None;
    }
};

class MapGrid {
public:
    MapGrid(int width, int height);

    int width() const noexcept { return width_; }
    int height() const noexcept { return height_; }
    bool in_bounds(int row, int col) const noexcept;

    MapCell& at(int row, int col);
    const MapCell& at(int row, int col) const;

    int road_bitmask(int row, int col) const;
    int land_count() const;
    int water_count() const;
    int road_count() const;
    int sidewalk_count() const;

private:
    int width_;
    int height_;
    std::vector<MapCell> cells_;
};

struct MapStats {
    std::uint32_t seed = 0;
    int width = 0;
    int height = 0;
    int land = 0;
    int water = 0;
    int roads = 0;
    int sidewalks = 0;
    int blocks = 0;
    int parks = 0;
    int lots = 0;
    int spawns = 0;
    int landmarks = 0;
};

} // namespace mapping_algorithm
