#pragma once

#include "mapping_algorithm/design_blueprint.hpp"
#include "mapping_algorithm/map_types.hpp"

#include <set>
#include <string>
#include <utility>
#include <vector>

namespace mapping_algorithm {

class MapGenerator {
public:
    explicit MapGenerator(MapConfig config);

    void generate();

    const MapConfig& config() const noexcept { return config_; }
    const MapGrid& grid() const noexcept { return grid_; }
    MapGrid& grid() noexcept { return grid_; }
    const MapStats& stats() const noexcept { return stats_; }
    const std::vector<std::set<std::pair<int, int>>>& blocks() const noexcept { return blocks_; }
    const std::vector<std::set<std::pair<int, int>>>& lots() const noexcept { return lots_; }
    const std::vector<BuildingAssemblyRecord>& buildings() const noexcept { return buildings_; }
    CoastSide resolved_coast_side() const noexcept { return resolved_coast_side_; }

    DesignBlueprint to_design_blueprint(const std::string& profile_id = "") const;

private:
    void generate_coastline();
    void generate_elevation();
    void generate_zones();
    void generate_civic_anchor();
    void generate_highways();
    void generate_connectors();
    void generate_sidewalks();
    void generate_blocks();
    void generate_parks();
    void generate_lots();
    void compute_density();
    void generate_buildings();
    void generate_district_names();
    void compute_stats();

    void validate_config() const;
    void set_road(int row, int col, RoadCategory category);
    bool can_place_road(int row, int col) const;

    MapConfig config_;
    MapGrid grid_;
    MapStats stats_;
    std::vector<std::set<std::pair<int, int>>> blocks_;
    std::vector<std::set<std::pair<int, int>>> lots_;
    std::vector<BuildingAssemblyRecord> buildings_;
    std::pair<int, int> civic_anchor_{-1, -1};
    CoastSide resolved_coast_side_ = CoastSide::None;
};

std::string to_string(CoastSide side);
std::string to_string(ZoneId zone);
std::string to_string(RoadCategory category);
CoastSide coast_side_from_string(const std::string& value);

} // namespace mapping_algorithm
