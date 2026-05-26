#include "mapping_algorithm/map_generator.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <map>
#include <numeric>
#include <queue>
#include <sstream>
#include <stdexcept>

namespace mapping_algorithm {
namespace {

constexpr std::uint32_t SALT_COAST = 0xAB1234;
constexpr std::uint32_t SALT_ELEVATION = 0xE1E2E3E4;
constexpr std::uint32_t SALT_HIGHWAY = 0xCD5678;
constexpr std::uint32_t SALT_CONNECTOR = 0xEF9ABC;
constexpr std::uint32_t SALT_PARKS = 0xA1B2C3;
constexpr std::uint32_t SALT_BUILDINGS = 0xB1C2D3;

using Point = std::pair<int, int>;

struct ProfileRules {
    int avenue_spacing = 18;
    int connector_spacing = 8;
    double connector_density = 0.65;
    int diagonal_streets = 2;
    double highway_organic = 0.3;
    int park_min_area = 18;
    int park_max_area = 140;
};

struct Bounds {
    int r0 = 0;
    int c0 = 0;
    int r1 = 0;
    int c1 = 0;
};

std::uint32_t mix_u32(std::uint32_t x) {
    x ^= x >> 16;
    x *= 0x7feb352dU;
    x ^= x >> 15;
    x *= 0x846ca68bU;
    x ^= x >> 16;
    return x;
}

std::uint32_t decision_hash(std::uint32_t seed, int a, int b, std::uint32_t salt) {
    std::uint32_t h = seed ^ salt;
    h ^= mix_u32(static_cast<std::uint32_t>(a) + 0x9e3779b9U);
    h ^= mix_u32(static_cast<std::uint32_t>(b) + 0x85ebca6bU);
    return mix_u32(h);
}

double decision01(std::uint32_t seed, int a, int b, std::uint32_t salt) {
    return static_cast<double>(decision_hash(seed, a, b, salt)) /
           static_cast<double>(std::numeric_limits<std::uint32_t>::max());
}

int decision_range(std::uint32_t seed, int a, int b, std::uint32_t salt, int min_value, int max_value) {
    if (max_value <= min_value) {
        return min_value;
    }
    const auto span = static_cast<std::uint32_t>(max_value - min_value + 1);
    return min_value + static_cast<int>(decision_hash(seed, a, b, salt) % span);
}

ProfileRules rules_for_profile(const std::string& id, const MapConfig& config) {
    ProfileRules rules;
    rules.avenue_spacing = config.avenue_spacing;
    rules.connector_spacing = config.connector_spacing;
    rules.connector_density = config.connector_density;
    rules.diagonal_streets = config.diagonal_streets;
    rules.highway_organic = config.highway_organic;

    if (id == "manhattan") {
        rules.avenue_spacing = std::max(8, config.avenue_spacing - 5);
        rules.connector_spacing = std::max(5, config.connector_spacing - 2);
        rules.connector_density = std::max(config.connector_density, 0.78);
        rules.diagonal_streets = std::max(config.diagonal_streets, 2);
        rules.highway_organic = std::min(config.highway_organic, 0.22);
    } else if (id == "barcelona_eixample") {
        rules.avenue_spacing = std::max(8, config.avenue_spacing - 6);
        rules.connector_spacing = std::max(8, config.connector_spacing + 1);
        rules.connector_density = std::max(config.connector_density, 0.86);
        rules.diagonal_streets = 0;
        rules.highway_organic = std::min(config.highway_organic, 0.12);
    } else if (id == "paris_haussmann") {
        rules.avenue_spacing = std::max(10, config.avenue_spacing - 3);
        rules.connector_spacing = std::max(7, config.connector_spacing);
        rules.connector_density = std::max(config.connector_density, 0.72);
        rules.diagonal_streets = std::max(config.diagonal_streets, 4);
        rules.highway_organic = std::max(config.highway_organic, 0.24);
    } else if (id == "london_organic") {
        rules.avenue_spacing = std::max(9, config.avenue_spacing - 4);
        rules.connector_spacing = std::max(7, config.connector_spacing + 1);
        rules.connector_density = std::min(config.connector_density, 0.62);
        rules.diagonal_streets = std::max(1, config.diagonal_streets);
        rules.highway_organic = std::max(config.highway_organic, 0.52);
        rules.park_min_area = 10;
        rules.park_max_area = 110;
    }

    return rules;
}

double clamp01(double value) {
    return std::max(0.0, std::min(1.0, value));
}

double smoothstep(double edge0, double edge1, double x) {
    const double t = clamp01((x - edge0) / (edge1 - edge0));
    return t * t * (3.0 - 2.0 * t);
}

double value_noise(int x, int y, std::uint32_t seed) {
    std::uint32_t h = seed;
    h ^= static_cast<std::uint32_t>(x) * 0x27d4eb2dU;
    h ^= static_cast<std::uint32_t>(y) * 0x85ebca6bU;
    h ^= h >> 15;
    h *= 0x2c1b3c6dU;
    h ^= h >> 12;
    return static_cast<double>(h & 0xFFFFU) / 65535.0;
}

double interpolated_noise(double x, double y, std::uint32_t seed) {
    const int x0 = static_cast<int>(std::floor(x));
    const int y0 = static_cast<int>(std::floor(y));
    const int x1 = x0 + 1;
    const int y1 = y0 + 1;
    const double sx = smoothstep(0.0, 1.0, x - x0);
    const double sy = smoothstep(0.0, 1.0, y - y0);
    const double n00 = value_noise(x0, y0, seed);
    const double n10 = value_noise(x1, y0, seed);
    const double n01 = value_noise(x0, y1, seed);
    const double n11 = value_noise(x1, y1, seed);
    const double ix0 = n00 + (n10 - n00) * sx;
    const double ix1 = n01 + (n11 - n01) * sx;
    return ix0 + (ix1 - ix0) * sy;
}

double fbm(double x, double y, std::uint32_t seed, int octaves = 4) {
    double total = 0.0;
    double amp = 1.0;
    double freq = 1.0;
    double norm = 0.0;
    for (int i = 0; i < octaves; ++i) {
        total += interpolated_noise(x * freq, y * freq, seed + i * 1013U) * amp;
        norm += amp;
        amp *= 0.5;
        freq *= 2.0;
    }
    return total / std::max(norm, 0.0001);
}

double directional_gradient(int r, int c, int rows, int cols, CoastSide side) {
    double t = 1.0;
    switch (side) {
        case CoastSide::West: t = static_cast<double>(c) / std::max(cols - 1, 1); break;
        case CoastSide::East: t = 1.0 - static_cast<double>(c) / std::max(cols - 1, 1); break;
        case CoastSide::North: t = static_cast<double>(r) / std::max(rows - 1, 1); break;
        case CoastSide::South: t = 1.0 - static_cast<double>(r) / std::max(rows - 1, 1); break;
        default: break;
    }
    return std::pow(clamp01(t), 2.2);
}

std::vector<std::vector<bool>> smooth_land(std::vector<std::vector<bool>> land, int passes) {
    const int rows = static_cast<int>(land.size());
    const int cols = rows ? static_cast<int>(land[0].size()) : 0;
    for (int pass = 0; pass < passes; ++pass) {
        auto next = land;
        for (int r = 0; r < rows; ++r) {
            for (int c = 0; c < cols; ++c) {
                int total = 0;
                int count = 0;
                for (int dr = -1; dr <= 1; ++dr) {
                    for (int dc = -1; dc <= 1; ++dc) {
                        const int nr = r + dr;
                        const int nc = c + dc;
                        if (nr >= 0 && nr < rows && nc >= 0 && nc < cols) {
                            ++total;
                            if (land[nr][nc]) {
                                ++count;
                            }
                        }
                    }
                }
                next[r][c] = count * 2 > total;
            }
        }
        land = std::move(next);
    }
    return land;
}

std::vector<Point> neighbours4(int r, int c) {
    return {{r - 1, c}, {r + 1, c}, {r, c - 1}, {r, c + 1}};
}

int cheb(Point a, Point b) {
    return std::max(std::abs(a.first - b.first), std::abs(a.second - b.second));
}

CityProfile profile_for(const std::string& id) {
    const std::string key = id.empty() ? "generic_dense" : id;
    if (key == "manhattan") {
        return {"manhattan", "Manhattan / Harlem", "long_avenues_short_cross_streets_diagonal", "3.4:1",
                {"avenue_grid", "waterfront_edges", "brownstone_midrise"},
                {"brick_facade", "brownstone", "glass_cbd"}};
    }
    if (key == "barcelona_eixample") {
        return {"barcelona_eixample", "Barcelona Eixample", "regular_square_grid_chamfered_blocks", "1.1:1",
                {"square_grid", "chamfered_corners", "courtyard_blocks"},
                {"stucco_facade", "balcony_rows", "courtyard_midrise"}};
    }
    if (key == "paris_haussmann") {
        return {"paris_haussmann", "Paris Haussmann", "boulevard_grid_with_diagonals", "1.5:1",
                {"boulevard", "monument_axis", "courtyard_blocks"},
                {"stone_facade", "mansard_roof", "civic_limestone"}};
    }
    if (key == "london_organic") {
        return {"london_organic", "London Organic", "irregular_grid_low_drift", "1.6:1",
                {"irregular_blocks", "mixed_scale", "park_squares"},
                {"brick_facade", "terrace_house", "stone_civic"}};
    }
    return {"generic_dense", "Generic Dense City", "orthogonal_grid_with_soft_drift", "2.0:1",
            {"balanced", "mixed_density", "gameplay_ready"},
            {"neutral_facade", "mixed_urban", "generic_props"}};
}

Point representative_point(const std::set<Point>& points) {
    double avg_r = 0.0;
    double avg_c = 0.0;
    for (const auto [r, c] : points) {
        avg_r += r;
        avg_c += c;
    }
    avg_r /= std::max<std::size_t>(points.size(), 1);
    avg_c /= std::max<std::size_t>(points.size(), 1);

    Point best = *points.begin();
    double best_dist = std::numeric_limits<double>::max();
    for (const auto p : points) {
        const double d = std::hypot(p.first - avg_r, p.second - avg_c);
        if (d < best_dist) {
            best_dist = d;
            best = p;
        }
    }
    return best;
}

ZoneId dominant_zone(const std::set<Point>& points, const MapGrid& grid) {
    std::map<ZoneId, int> counts;
    for (const auto [r, c] : points) {
        ++counts[grid.at(r, c).zone_id];
    }
    return std::max_element(counts.begin(), counts.end(), [](const auto& a, const auto& b) {
        return a.second < b.second;
    })->first;
}

Bounds bounds_for(const std::set<Point>& points) {
    Bounds bounds{
        std::numeric_limits<int>::max(),
        std::numeric_limits<int>::max(),
        std::numeric_limits<int>::min(),
        std::numeric_limits<int>::min()
    };
    for (const auto [r, c] : points) {
        bounds.r0 = std::min(bounds.r0, r);
        bounds.c0 = std::min(bounds.c0, c);
        bounds.r1 = std::max(bounds.r1, r);
        bounds.c1 = std::max(bounds.c1, c);
    }
    return bounds;
}

bool touches_waterfront(const std::set<Point>& points, const MapGrid& grid) {
    for (const auto [r, c] : points) {
        if (!grid.at(r, c).coast_type.empty()) {
            return true;
        }
        for (const auto [nr, nc] : neighbours4(r, c)) {
            if (grid.in_bounds(nr, nc) && grid.at(nr, nc).is_water) {
                return true;
            }
        }
    }
    return false;
}

std::string pick_building_type(ZoneId zone, double roll, bool waterfront) {
    if (waterfront) {
        if (roll < 0.35) return "restaurant";
        if (roll < 0.60) return "market";
        if (roll < 0.90) return "apartment";
        return "empty";
    }
    if (zone == ZoneId::CBD) {
        if (roll < 0.64) return "office";
        if (roll < 0.82) return "bank";
        return "civic";
    }
    if (zone == ZoneId::Midtown) {
        if (roll < 0.46) return "apartment";
        if (roll < 0.76) return "shop";
        return "restaurant";
    }
    if (roll < 0.78) return "house";
    if (roll < 0.92) return "apartment";
    return "shop";
}

std::string asset_slot_for_building(const std::string& type) {
    if (type == "office") return "building/office";
    if (type == "apartment") return "building/apartment";
    if (type == "house") return "building/house";
    if (type == "shop") return "building/shop";
    if (type == "restaurant") return "building/restaurant";
    if (type == "market") return "building/market";
    if (type == "bank") return "building/bank";
    if (type == "civic") return "building/civic";
    if (type == "station") return "landmark/station";
    if (type == "school") return "landmark/school";
    return "terrain/exterior";
}

std::string asset_slot_for_building_record(const std::string& type, const std::string& landmark_type) {
    if (!landmark_type.empty()) {
        return "landmark/" + landmark_type;
    }
    return asset_slot_for_building(type);
}

int floor_count_for(ZoneId zone, const std::string& type, std::uint32_t seed, int lot_id) {
    if (type == "office") return decision_range(seed, lot_id, 10, SALT_BUILDINGS, 7, 16);
    if (type == "bank" || type == "civic") return decision_range(seed, lot_id, 11, SALT_BUILDINGS, 3, 5);
    if (type == "hospital" || type == "police" || type == "station") return decision_range(seed, lot_id, 16, SALT_BUILDINGS, 2, 4);
    if (type == "apartment") return zone == ZoneId::CBD
        ? decision_range(seed, lot_id, 12, SALT_BUILDINGS, 5, 9)
        : decision_range(seed, lot_id, 13, SALT_BUILDINGS, 3, 6);
    if (type == "shop" || type == "restaurant" || type == "market") return decision_range(seed, lot_id, 14, SALT_BUILDINGS, 1, 3);
    if (type == "house" || type == "school") return decision_range(seed, lot_id, 15, SALT_BUILDINGS, 1, 3);
    return 1;
}

std::string roof_for(const std::string& profile_id, const std::string& type, int floors) {
    if (type == "office") return floors >= 8 ? "roof_glass_tower" : "roof_flat_a";
    if (profile_id == "paris_haussmann") return "roof_mansard_a";
    if (profile_id == "barcelona_eixample") return "roof_terracotta_a";
    if (type == "house") return "roof_peaked_a";
    if (profile_id == "manhattan") return "roof_rowhouse_parapet";
    return "roof_flat_b";
}

std::string facade_family_for(const std::string& profile_id, const std::string& type) {
    if (type == "office") return "glass_cbd";
    if (profile_id == "manhattan") return "brick_brownstone";
    if (profile_id == "barcelona_eixample") return "stucco_balcony";
    if (profile_id == "paris_haussmann") return "limestone_mansard";
    if (profile_id == "london_organic") return "brick_terrace";
    return "mixed_urban";
}

std::string footprint_style_for(const std::string& profile_id,
                                ZoneId zone,
                                const std::string& type,
                                const Bounds& bounds) {
    const int w = bounds.c1 - bounds.c0 + 1;
    const int h = bounds.r1 - bounds.r0 + 1;
    if (type == "civic" || type == "hospital" || type == "police" || type == "station" || type == "school") {
        return "institutional_courtyard";
    }
    if (profile_id == "barcelona_eixample") {
        return std::abs(w - h) <= 1 ? "chamfered_courtyard" : "linear_courtyard";
    }
    if (profile_id == "paris_haussmann") {
        return "perimeter_courtyard";
    }
    if (zone == ZoneId::Residential) {
        return w > h ? "rowhouse_strip" : "setback_pair";
    }
    if (zone == ZoneId::CBD) {
        return "tower_podium";
    }
    return w >= h ? "mixed_frontage_wide" : "mixed_frontage_deep";
}

std::string tile_role_for_building(ZoneId zone, const std::string& type, const std::string& landmark_type) {
    if (!landmark_type.empty() || type == "civic" || type == "hospital" || type == "police" || type == "station") {
        return "bldg_civic";
    }
    if (zone == ZoneId::CBD) {
        return "bldg_cbd";
    }
    if (zone == ZoneId::Midtown) {
        return "bldg_mid";
    }
    return "bldg_resi";
}

std::string variant_suffix(std::uint32_t seed, int lot_id, int salt_shift) {
    static const char suffixes[] = {'a', 'b', 'c', 'd'};
    const auto index = decision_hash(seed, lot_id, salt_shift, SALT_BUILDINGS) % 4U;
    return std::string(1, suffixes[index]);
}

std::vector<std::string> sprite_stack_for(const std::string& profile_id,
                                          const std::string& type,
                                          const std::string& landmark_type,
                                          int floors,
                                          std::uint32_t seed,
                                          int lot_id) {
    std::vector<std::string> sprites;
    sprites.push_back("shadow_bldg_2x2");
    if (landmark_type == "town_hall") {
        sprites.push_back("landmark_town_hall_" + variant_suffix(seed, lot_id, 101));
        sprites.push_back("bldg_civic_columns_a");
    } else if (landmark_type == "station") {
        sprites.push_back("landmark_station_" + variant_suffix(seed, lot_id, 102));
    } else if (landmark_type == "hospital") {
        sprites.push_back("landmark_hospital_" + variant_suffix(seed, lot_id, 103));
    } else if (landmark_type == "police") {
        sprites.push_back("landmark_police_" + variant_suffix(seed, lot_id, 104));
    } else if (landmark_type == "school") {
        sprites.push_back("landmark_school_" + variant_suffix(seed, lot_id, 105));
    } else if (type == "office") {
        sprites.push_back(decision_hash(seed, lot_id, 1, SALT_BUILDINGS) % 2 ? "bldg_cbd_glass_a" : "bldg_cbd_glass_b");
    } else if (type == "apartment") {
        sprites.push_back(decision_hash(seed, lot_id, 2, SALT_BUILDINGS) % 2 ? "bldg_mid_brownstone_a" : "bldg_mid_brick_a");
    } else if (type == "house") {
        sprites.push_back(decision_hash(seed, lot_id, 3, SALT_BUILDINGS) % 2 ? "bldg_resi_detached_a" : "bldg_resi_rowhouse_a");
    } else if (type == "shop") {
        sprites.push_back(decision_hash(seed, lot_id, 4, SALT_BUILDINGS) % 2 ? "bldg_shop_storefront_a" : "bldg_shop_storefront_b");
    } else if (type == "restaurant") {
        sprites.push_back("bldg_restaurant_a");
    } else if (type == "market") {
        sprites.push_back("bldg_market_a");
    } else if (type == "bank") {
        sprites.push_back("bldg_bank_a");
    } else if (type == "civic") {
        sprites.push_back("bldg_civic_a");
    }

    if (landmark_type.empty()) {
        sprites.push_back(roof_for(profile_id, type, floors));
    }
    if (landmark_type.empty() && profile_id == "manhattan" && floors >= 4) {
        sprites.push_back("kit_mhtn_fire_escape_a");
    } else if (landmark_type.empty() && profile_id == "barcelona_eixample") {
        sprites.push_back("kit_bcn_balcony_a");
    } else if (landmark_type.empty() && profile_id == "paris_haussmann") {
        sprites.push_back("kit_paris_balcony_ironwork");
    } else if (landmark_type.empty() && profile_id == "london_organic" && type == "house") {
        sprites.push_back("kit_ldn_bay_window_a");
    }
    return sprites;
}

} // namespace

MapGrid::MapGrid(int width, int height)
    : width_(width), height_(height) {
    if (width <= 0 || height <= 0) {
        throw std::invalid_argument("MapGrid dimensions must be positive");
    }
    cells_.resize(static_cast<std::size_t>(width) * static_cast<std::size_t>(height));
}

bool MapGrid::in_bounds(int row, int col) const noexcept {
    return row >= 0 && row < height_ && col >= 0 && col < width_;
}

MapCell& MapGrid::at(int row, int col) {
    if (!in_bounds(row, col)) {
        throw std::out_of_range("MapGrid::at");
    }
    return cells_[static_cast<std::size_t>(row * width_ + col)];
}

const MapCell& MapGrid::at(int row, int col) const {
    if (!in_bounds(row, col)) {
        throw std::out_of_range("MapGrid::at");
    }
    return cells_[static_cast<std::size_t>(row * width_ + col)];
}

int MapGrid::road_bitmask(int row, int col) const {
    int mask = 0;
    const int bits[4] = {8, 2, 1, 4};
    const int dr[4] = {-1, 1, 0, 0};
    const int dc[4] = {0, 0, -1, 1};
    for (int i = 0; i < 4; ++i) {
        const int nr = row + dr[i];
        const int nc = col + dc[i];
        if (in_bounds(nr, nc) && at(nr, nc).is_road()) {
            mask |= bits[i];
        }
    }
    return mask;
}

int MapGrid::land_count() const {
    return static_cast<int>(std::count_if(cells_.begin(), cells_.end(), [](const MapCell& c) { return c.is_land; }));
}

int MapGrid::water_count() const {
    return static_cast<int>(std::count_if(cells_.begin(), cells_.end(), [](const MapCell& c) { return c.is_water; }));
}

int MapGrid::road_count() const {
    return static_cast<int>(std::count_if(cells_.begin(), cells_.end(), [](const MapCell& c) { return c.is_road(); }));
}

int MapGrid::sidewalk_count() const {
    return static_cast<int>(std::count_if(cells_.begin(), cells_.end(), [](const MapCell& c) { return c.tile_role == "sidewalk"; }));
}

MapGenerator::MapGenerator(MapConfig config)
    : config_(std::move(config)), grid_(config_.width, config_.height) {}

void MapGenerator::generate() {
    validate_config();
    grid_ = MapGrid(config_.width, config_.height);
    stats_ = MapStats{};
    blocks_.clear();
    lots_.clear();
    buildings_.clear();
    civic_anchor_ = {-1, -1};
    resolved_coast_side_ = CoastSide::None;

    generate_coastline();
    generate_elevation();
    generate_zones();
    generate_highways();
    generate_connectors();
    generate_sidewalks();
    generate_blocks();
    generate_civic_anchor();
    generate_parks();
    generate_lots();
    compute_density();
    generate_buildings();
    generate_district_names();
    compute_stats();
}

void MapGenerator::validate_config() const {
    if (config_.width <= 0 || config_.height <= 0) {
        throw std::invalid_argument("MapConfig dimensions must be positive");
    }
    if (config_.width > 512 || config_.height > 512) {
        throw std::invalid_argument("MapConfig dimensions exceed supported 512x512 guard rail");
    }
    if (config_.connector_spacing <= 0 || config_.avenue_spacing <= 0) {
        throw std::invalid_argument("MapConfig road spacing must be positive");
    }
    if (config_.highway_ns_min < 0 || config_.highway_ew_min < 0 ||
        config_.highway_ns_max < config_.highway_ns_min ||
        config_.highway_ew_max < config_.highway_ew_min) {
        throw std::invalid_argument("MapConfig highway ranges are invalid");
    }
    if (config_.coast_coverage < 0.0 || config_.coast_coverage > 0.75) {
        throw std::invalid_argument("MapConfig coast_coverage must be in [0.0, 0.75]");
    }
    if (config_.coast_noise_scale <= 0.0) {
        throw std::invalid_argument("MapConfig coast_noise_scale must be positive");
    }
}

void MapGenerator::generate_coastline() {
    CoastSide side = config_.coast_side;
    if (side == CoastSide::Random) {
        if (decision01(config_.master_seed, 11, 7, SALT_COAST) < 0.50) {
            const int dir = decision_range(config_.master_seed, 19, 3, SALT_COAST, 0, 3);
            side = static_cast<CoastSide>(static_cast<int>(CoastSide::North) + dir);
        } else {
            side = CoastSide::None;
        }
    }
    resolved_coast_side_ = side;

    const int rows = grid_.height();
    const int cols = grid_.width();
    if (side == CoastSide::None) {
        for (int r = 0; r < rows; ++r) {
            for (int c = 0; c < cols; ++c) {
                auto& cell = grid_.at(r, c);
                cell.is_land = true;
                cell.is_water = false;
            }
        }
        return;
    }

    std::vector<double> flat;
    std::vector<std::vector<double>> raw(rows, std::vector<double>(cols, 0.0));
    flat.reserve(static_cast<std::size_t>(rows * cols));
    for (int r = 0; r < rows; ++r) {
        for (int c = 0; c < cols; ++c) {
            const double nx = static_cast<double>(c) / cols * config_.coast_noise_scale;
            const double ny = static_cast<double>(r) / rows * config_.coast_noise_scale;
            const double noise = fbm(nx, ny, config_.master_seed ^ SALT_COAST, 4);
            const double bias = directional_gradient(r, c, rows, cols, side);
            raw[r][c] = noise * 0.55 + bias * 0.45;
            flat.push_back(raw[r][c]);
        }
    }
    std::sort(flat.begin(), flat.end());
    const auto cutoff = std::min<std::size_t>(
        flat.size() - 1,
        static_cast<std::size_t>(config_.coast_coverage * flat.size())
    );
    const double threshold = flat[cutoff];
    std::vector<std::vector<bool>> land(rows, std::vector<bool>(cols, false));
    for (int r = 0; r < rows; ++r) {
        for (int c = 0; c < cols; ++c) {
            land[r][c] = raw[r][c] >= threshold;
        }
    }
    land = smooth_land(std::move(land), config_.coast_smoothing_passes);

    for (int r = 0; r < rows; ++r) {
        for (int c = 0; c < cols; ++c) {
            auto& cell = grid_.at(r, c);
            cell.is_land = land[r][c];
            cell.is_water = !land[r][c];
        }
    }

    for (int r = 0; r < rows; ++r) {
        for (int c = 0; c < cols; ++c) {
            auto& cell = grid_.at(r, c);
            if (!cell.is_land) {
                continue;
            }
            bool shoreline = false;
            for (const auto [nr, nc] : neighbours4(r, c)) {
                if (grid_.in_bounds(nr, nc) && grid_.at(nr, nc).is_water) {
                    shoreline = true;
                    break;
                }
            }
            if (shoreline) {
                const double roll = decision01(config_.master_seed, r, c, SALT_COAST);
                cell.coast_type = roll < 0.35 ? "cliff" : (roll < 0.80 ? "beach" : "dock");
            }
        }
    }
}

void MapGenerator::generate_elevation() {
    for (int r = 0; r < grid_.height(); ++r) {
        for (int c = 0; c < grid_.width(); ++c) {
            auto& cell = grid_.at(r, c);
            if (cell.is_water) {
                cell.elevation = 0.0;
            } else {
                cell.elevation = clamp01(fbm(c / 50.0, r / 50.0, config_.master_seed ^ SALT_ELEVATION, 3));
            }
        }
    }
}

void MapGenerator::generate_zones() {
    const int rows = grid_.height();
    const int cols = grid_.width();
    double center_r = rows / 2.0;
    double center_c = cols / 2.0;
    if (resolved_coast_side_ == CoastSide::West) center_c = cols * 0.60;
    if (resolved_coast_side_ == CoastSide::East) center_c = cols * 0.40;
    if (resolved_coast_side_ == CoastSide::North) center_r = rows * 0.60;
    if (resolved_coast_side_ == CoastSide::South) center_r = rows * 0.40;

    for (int r = 0; r < rows; ++r) {
        for (int c = 0; c < cols; ++c) {
            auto& cell = grid_.at(r, c);
            if (!cell.is_land) {
                continue;
            }
            const double dr = std::abs(r - center_r) / (rows / 2.0);
            const double dc = std::abs(c - center_c) / (cols / 2.0);
            const double dist = std::max(dr, dc);
            cell.zone_id = dist < 0.45 ? ZoneId::CBD : (dist < 0.72 ? ZoneId::Midtown : ZoneId::Residential);

            const double transition = decision01(config_.master_seed, r, c, SALT_ELEVATION);
            if (dist >= 0.42 && dist < 0.50 && transition < 0.40) {
                cell.zone_id = ZoneId::Midtown;
            } else if (dist >= 0.69 && dist < 0.77 && transition < 0.35) {
                cell.zone_id = ZoneId::Residential;
            }
        }
    }
}

void MapGenerator::generate_civic_anchor() {
    double best_score = -1.0;
    Point best{-1, -1};
    for (int r = 0; r < grid_.height(); ++r) {
        for (int c = 0; c < grid_.width(); ++c) {
            const auto& cell = grid_.at(r, c);
            if (!cell.is_land || cell.is_water || cell.is_road() || cell.zone_id != ZoneId::CBD || cell.block_id < 0) {
                continue;
            }
            int water_dist = 999;
            for (int rr = 0; rr < grid_.height(); ++rr) {
                for (int cc = 0; cc < grid_.width(); ++cc) {
                    if (grid_.at(rr, cc).is_water) {
                        water_dist = std::min(water_dist, cheb({r, c}, {rr, cc}));
                    }
                }
            }
            const double center_score = -std::hypot(r - grid_.height() / 2.0, c - grid_.width() / 2.0);
            const double score = water_dist * 4.0 + center_score;
            if (score > best_score) {
                best_score = score;
                best = {r, c};
            }
        }
    }
    if (best.first >= 0) {
        civic_anchor_ = best;
        auto& cell = grid_.at(best.first, best.second);
        cell.is_civic_anchor = true;
        cell.tile_role = "civic_anchor";
    }
}

bool MapGenerator::can_place_road(int row, int col) const {
    return grid_.in_bounds(row, col) && grid_.at(row, col).is_land && !grid_.at(row, col).is_water;
}

void MapGenerator::set_road(int row, int col, RoadCategory category) {
    if (can_place_road(row, col)) {
        grid_.at(row, col).road_category = category;
    }
}

void MapGenerator::generate_highways() {
    const auto rules = rules_for_profile(config_.city_profile, config_);
    const int ns_count = decision_range(config_.master_seed, 3, 5, SALT_HIGHWAY, config_.highway_ns_min, config_.highway_ns_max);
    const int ew_count = decision_range(config_.master_seed, 7, 11, SALT_HIGHWAY, config_.highway_ew_min, config_.highway_ew_max);
    for (int i = 0; i < ns_count; ++i) {
        const int c = (i + 1) * grid_.width() / (ns_count + 1);
        for (int r = 0; r < grid_.height(); ++r) {
            const int drift = static_cast<int>(std::round((fbm(r / 20.0, i, config_.master_seed ^ SALT_HIGHWAY) - 0.5) * 2.0 * rules.highway_organic * 3.0));
            set_road(r, std::clamp(c + drift, 0, grid_.width() - 1), RoadCategory::Highway);
        }
    }
    for (int i = 0; i < ew_count; ++i) {
        const int r = (i + 1) * grid_.height() / (ew_count + 1);
        for (int c = 0; c < grid_.width(); ++c) {
            const int drift = static_cast<int>(std::round((fbm(c / 20.0, i + 99, config_.master_seed ^ SALT_HIGHWAY) - 0.5) * 2.0 * rules.highway_organic * 3.0));
            set_road(std::clamp(r + drift, 0, grid_.height() - 1), c, RoadCategory::Highway);
        }
    }
}

void MapGenerator::generate_connectors() {
    const auto rules = rules_for_profile(config_.city_profile, config_);
    for (int c = rules.avenue_spacing; c < grid_.width(); c += rules.avenue_spacing) {
        if (decision01(config_.master_seed, c, 17, SALT_CONNECTOR) > rules.connector_density) {
            continue;
        }
        for (int r = 0; r < grid_.height(); ++r) {
            if (!grid_.at(r, c).is_road()) {
                set_road(r, c, RoadCategory::Connector);
            }
        }
    }
    for (int r = rules.connector_spacing; r < grid_.height(); r += rules.connector_spacing) {
        if (decision01(config_.master_seed, 23, r, SALT_CONNECTOR) > rules.connector_density) {
            continue;
        }
        for (int c = 0; c < grid_.width(); ++c) {
            if (!grid_.at(r, c).is_road()) {
                set_road(r, c, RoadCategory::Connector);
            }
        }
    }
    for (int d = 0; d < rules.diagonal_streets; ++d) {
        int r = std::max(1, grid_.height() / 8 + d * 5);
        int c = std::max(1, grid_.width() / 8 + d * 7);
        while (r < grid_.height() - 1 && c < grid_.width() - 1) {
            if (!grid_.at(r, c).is_road()) {
                set_road(r, c, RoadCategory::Connector);
            }
            if ((r + c + d) % 2 == 0) {
                ++r;
            } else {
                ++c;
            }
        }
    }
}

void MapGenerator::generate_sidewalks() {
    std::vector<Point> sidewalks;
    for (int r = 0; r < grid_.height(); ++r) {
        for (int c = 0; c < grid_.width(); ++c) {
            const auto& cell = grid_.at(r, c);
            if (!cell.is_land || cell.is_road()) {
                continue;
            }
            for (const auto [nr, nc] : neighbours4(r, c)) {
                if (grid_.in_bounds(nr, nc) && grid_.at(nr, nc).road_category == RoadCategory::Connector) {
                    sidewalks.push_back({r, c});
                    break;
                }
            }
        }
    }
    for (const auto [r, c] : sidewalks) {
        grid_.at(r, c).tile_role = "sidewalk";
    }
}

void MapGenerator::generate_blocks() {
    const int rows = grid_.height();
    const int cols = grid_.width();
    std::vector<std::vector<bool>> visited(rows, std::vector<bool>(cols, false));
    int block_id = 0;
    for (int sr = 0; sr < rows; ++sr) {
        for (int sc = 0; sc < cols; ++sc) {
            if (visited[sr][sc] || grid_.at(sr, sc).is_road() || grid_.at(sr, sc).is_water) {
                visited[sr][sc] = true;
                continue;
            }
            std::queue<Point> q;
            std::set<Point> region;
            bool edge = false;
            q.push({sr, sc});
            visited[sr][sc] = true;
            while (!q.empty()) {
                const auto [r, c] = q.front();
                q.pop();
                region.insert({r, c});
                if (r == 0 || c == 0 || r == rows - 1 || c == cols - 1) {
                    edge = true;
                }
                for (const auto [nr, nc] : neighbours4(r, c)) {
                    if (grid_.in_bounds(nr, nc) && !visited[nr][nc] && !grid_.at(nr, nc).is_road() && !grid_.at(nr, nc).is_water) {
                        visited[nr][nc] = true;
                        q.push({nr, nc});
                    }
                }
            }
            int r0 = rows, c0 = cols, r1 = 0, c1 = 0;
            for (const auto [r, c] : region) {
                r0 = std::min(r0, r);
                r1 = std::max(r1, r);
                c0 = std::min(c0, c);
                c1 = std::max(c1, c);
            }
            const int depth = std::min(r1 - r0 + 1, c1 - c0 + 1);
            const bool too_small = static_cast<int>(region.size()) < std::max(4, config_.min_block_depth * 2) ||
                                   depth < std::max(1, config_.min_block_depth);
            if (edge || too_small) {
                for (const auto [r, c] : region) {
                    grid_.at(r, c).block_id = -1;
                }
            } else {
                for (const auto [r, c] : region) {
                    grid_.at(r, c).block_id = block_id;
                }
                blocks_.push_back(region);
                ++block_id;
            }
        }
    }
}

void MapGenerator::generate_parks() {
    const auto rules = rules_for_profile(config_.city_profile, config_);
    std::vector<int> candidates;
    candidates.reserve(blocks_.size());
    for (std::size_t i = 0; i < blocks_.size(); ++i) {
        const auto& block = blocks_[i];
        const bool contains_civic = std::any_of(block.begin(), block.end(), [&](Point p) {
            return grid_.at(p.first, p.second).is_civic_anchor;
        });
        if (!contains_civic &&
            static_cast<int>(block.size()) >= rules.park_min_area &&
            static_cast<int>(block.size()) <= rules.park_max_area) {
            candidates.push_back(static_cast<int>(i));
        }
    }
    std::sort(candidates.begin(), candidates.end(), [&](int a, int b) {
        const auto ha = decision_hash(config_.master_seed, a, static_cast<int>(blocks_[a].size()), SALT_PARKS);
        const auto hb = decision_hash(config_.master_seed, b, static_cast<int>(blocks_[b].size()), SALT_PARKS);
        return ha < hb;
    });

    const int land_cells = grid_.land_count();
    const int target = std::max(1, land_cells / 500);
    for (int i = 0; i < target && i < static_cast<int>(candidates.size()); ++i) {
        for (const auto [r, c] : blocks_[static_cast<std::size_t>(candidates[i])]) {
            auto& cell = grid_.at(r, c);
            cell.is_park = true;
            cell.tile_role = "park";
        }
    }
}

void MapGenerator::generate_lots() {
    int lot_id = 0;
    for (const auto& block : blocks_) {
        if (block.empty()) {
            continue;
        }
        const bool is_park = std::any_of(block.begin(), block.end(), [&](Point p) { return grid_.at(p.first, p.second).is_park; });
        if (is_park) {
            continue;
        }
        int r0 = grid_.height(), c0 = grid_.width(), r1 = 0, c1 = 0;
        for (const auto [r, c] : block) {
            r0 = std::min(r0, r); r1 = std::max(r1, r);
            c0 = std::min(c0, c); c1 = std::max(c1, c);
        }
        const bool split_by_col = (c1 - c0) >= (r1 - r0);
        const int midpoint = split_by_col ? (c0 + c1) / 2 : (r0 + r1) / 2;
        std::set<Point> left;
        std::set<Point> right;
        for (const auto [r, c] : block) {
            ((split_by_col ? c : r) <= midpoint ? left : right).insert({r, c});
        }
        for (const auto& lot : {left, right}) {
            if (lot.size() < 4) {
                continue;
            }
            for (const auto [r, c] : lot) {
                grid_.at(r, c).lot_id = lot_id;
            }
            lots_.push_back(lot);
            ++lot_id;
        }
    }
}

void MapGenerator::compute_density() {
    for (int r = 0; r < grid_.height(); ++r) {
        for (int c = 0; c < grid_.width(); ++c) {
            auto& cell = grid_.at(r, c);
            if (!cell.is_land) {
                continue;
            }
            const double base = cell.zone_id == ZoneId::CBD ? 0.85 : (cell.zone_id == ZoneId::Midtown ? 0.55 : 0.25);
            cell.density_score = base;
        }
    }
}

void MapGenerator::generate_buildings() {
    for (int r = 0; r < grid_.height(); ++r) {
        for (int c = 0; c < grid_.width(); ++c) {
            auto& cell = grid_.at(r, c);
            if (cell.is_water) {
                cell.tile_role = "water";
            } else if (cell.is_road()) {
                cell.tile_role = cell.road_category == RoadCategory::Highway ? "highway" : "road";
                cell.encounter_chance = cell.road_category == RoadCategory::Highway ? 0.08 : 0.12;
            } else if (cell.is_park) {
                cell.tile_role = "park";
                cell.is_spawn_point = true;
                cell.encounter_chance = 0.25;
            } else if (cell.tile_role == "sidewalk") {
                cell.encounter_chance = 0.05;
            } else if (cell.lot_id >= 0) {
                cell.tile_role = "lot";
            } else {
                cell.tile_role = "exterior";
            }
        }
    }

    std::map<int, std::string> landmark_by_lot;
    if (civic_anchor_.first >= 0 && grid_.in_bounds(civic_anchor_.first, civic_anchor_.second)) {
        const int civic_lot = grid_.at(civic_anchor_.first, civic_anchor_.second).lot_id;
        if (civic_lot >= 0) {
            landmark_by_lot[civic_lot] = "town_hall";
        }
    }

    std::vector<int> candidate_lots;
    candidate_lots.reserve(lots_.size());
    for (std::size_t i = 0; i < lots_.size(); ++i) {
        std::set<Point> buildable;
        for (const auto [r, c] : lots_[i]) {
            const auto& cell = grid_.at(r, c);
            if (cell.tile_role != "sidewalk" && !cell.is_road() && !cell.is_water && !cell.is_park) {
                buildable.insert({r, c});
            }
        }
        if (buildable.size() < 6) {
            continue;
        }
        const auto anchor = representative_point(buildable);
        const int lot_id = grid_.at(anchor.first, anchor.second).lot_id;
        if (landmark_by_lot.find(lot_id) == landmark_by_lot.end()) {
            candidate_lots.push_back(static_cast<int>(i));
        }
    }
    std::sort(candidate_lots.begin(), candidate_lots.end(), [&](int a, int b) {
        const auto& lot_a = lots_[static_cast<std::size_t>(a)];
        const auto& lot_b = lots_[static_cast<std::size_t>(b)];
        const auto pa = representative_point(lot_a);
        const auto pb = representative_point(lot_b);
        const auto ha = decision_hash(config_.master_seed, grid_.at(pa.first, pa.second).lot_id,
                                      static_cast<int>(lot_a.size()), SALT_BUILDINGS);
        const auto hb = decision_hash(config_.master_seed, grid_.at(pb.first, pb.second).lot_id,
                                      static_cast<int>(lot_b.size()), SALT_BUILDINGS);
        return ha < hb;
    });

    const std::vector<std::string> civic_landmarks = {"station", "hospital", "police", "school"};
    for (std::size_t i = 0; i < civic_landmarks.size() && i < candidate_lots.size(); ++i) {
        const auto anchor = representative_point(lots_[static_cast<std::size_t>(candidate_lots[i])]);
        landmark_by_lot[grid_.at(anchor.first, anchor.second).lot_id] = civic_landmarks[i];
    }

    int building_id = 0;
    for (const auto& lot : lots_) {
        if (lot.empty()) {
            continue;
        }
        std::set<Point> buildable;
        for (const auto [r, c] : lot) {
            const auto& cell = grid_.at(r, c);
            if (cell.tile_role != "sidewalk" && !cell.is_road() && !cell.is_water && !cell.is_park) {
                buildable.insert({r, c});
            }
        }
        if (buildable.empty()) {
            continue;
        }
        const auto lot_anchor = representative_point(buildable);
        const int lot_id = grid_.at(lot_anchor.first, lot_anchor.second).lot_id;
        if (lot_id < 0) {
            continue;
        }
        const auto bounds = bounds_for(buildable);
        const ZoneId zone = dominant_zone(buildable, grid_);
        const bool waterfront = touches_waterfront(buildable, grid_);
        const auto landmark_it = landmark_by_lot.find(lot_id);
        const std::string landmark_type = landmark_it == landmark_by_lot.end() ? "" : landmark_it->second;
        const double roll = decision01(config_.master_seed, lot_id, static_cast<int>(buildable.size()), SALT_BUILDINGS);

        std::string building_type;
        if (landmark_type == "town_hall") {
            building_type = "civic";
        } else if (!landmark_type.empty()) {
            building_type = landmark_type;
        } else {
            building_type = pick_building_type(zone, roll, waterfront);
        }
        if (building_type == "empty") {
            for (const auto [r, c] : buildable) {
                auto& cell = grid_.at(r, c);
                cell.tile_role = "exterior";
                cell.building_type.clear();
                cell.landmark_type.clear();
            }
            continue;
        }

        const bool uses_setback = zone == ZoneId::Residential &&
                                  buildable.size() >= 9 &&
                                  landmark_type.empty() &&
                                  building_type != "apartment";
        std::set<Point> footprint;
        for (const auto [r, c] : buildable) {
            const bool perimeter = r == bounds.r0 || r == bounds.r1 || c == bounds.c0 || c == bounds.c1;
            auto& cell = grid_.at(r, c);
            if (uses_setback && perimeter) {
                cell.is_setback = true;
                cell.tile_role = "setback";
                cell.encounter_chance = 0.03;
                continue;
            }
            footprint.insert({r, c});
        }
        if (footprint.empty()) {
            footprint.insert(lot_anchor);
            grid_.at(lot_anchor.first, lot_anchor.second).is_setback = false;
        }

        const auto footprint_bounds = bounds_for(footprint);
        const auto anchor = representative_point(footprint);
        const int floors = floor_count_for(zone, building_type, config_.master_seed, lot_id);
        const std::string profile_id = profile_for(config_.city_profile).id;
        const std::string footprint_style = footprint_style_for(profile_id, zone, building_type, footprint_bounds);
        const std::string roof_type = landmark_type.empty() ? roof_for(profile_id, building_type, floors) : "";
        const std::string facade = facade_family_for(profile_id, building_type);
        const std::string tile_role = tile_role_for_building(zone, building_type, landmark_type);
        const std::string asset_slot = asset_slot_for_building_record(building_type, landmark_type);

        for (const auto [r, c] : footprint) {
            auto& cell = grid_.at(r, c);
            cell.tile_role = tile_role;
            cell.building_type = building_type;
            cell.landmark_type = landmark_type;
            cell.footprint_style = footprint_style;
            cell.encounter_chance = tile_role == "bldg_civic" ? 0.16 : (zone == ZoneId::CBD ? 0.10 : 0.06);
        }

        BuildingAssemblyRecord record;
        record.id = building_id++;
        record.lot_id = lot_id;
        record.block_id = grid_.at(anchor.first, anchor.second).block_id;
        record.anchor_row = anchor.first;
        record.anchor_col = anchor.second;
        record.footprint_r0 = footprint_bounds.r0;
        record.footprint_c0 = footprint_bounds.c0;
        record.footprint_r1 = footprint_bounds.r1;
        record.footprint_c1 = footprint_bounds.c1;
        record.floors = floors;
        record.zone = to_string(zone);
        record.building_type = building_type;
        record.landmark_type = landmark_type;
        record.footprint_style = footprint_style;
        record.facade_family = facade;
        record.roof_type = roof_type;
        record.asset_slot = asset_slot;
        record.sprite_stack = sprite_stack_for(profile_id, building_type, landmark_type, floors, config_.master_seed, lot_id);
        buildings_.push_back(std::move(record));
    }
}

void MapGenerator::generate_district_names() {
    for (int r = 0; r < grid_.height(); ++r) {
        for (int c = 0; c < grid_.width(); ++c) {
            auto& cell = grid_.at(r, c);
            if (!cell.is_land) {
                continue;
            }
            cell.district_name = cell.zone_id == ZoneId::CBD ? "Civic Core" :
                (cell.zone_id == ZoneId::Midtown ? "Midtown" : "Residential Quarter");
        }
    }
}

void MapGenerator::compute_stats() {
    stats_ = MapStats{};
    stats_.seed = config_.master_seed;
    stats_.width = grid_.width();
    stats_.height = grid_.height();
    stats_.land = grid_.land_count();
    stats_.water = grid_.water_count();
    stats_.roads = grid_.road_count();
    stats_.sidewalks = grid_.sidewalk_count();
    stats_.blocks = static_cast<int>(blocks_.size());
    stats_.lots = static_cast<int>(lots_.size());
    stats_.buildings = static_cast<int>(buildings_.size());
    stats_.parks = 0;
    for (const auto& block : blocks_) {
        const bool is_park_block = std::any_of(block.begin(), block.end(), [&](Point p) {
            return grid_.at(p.first, p.second).is_park;
        });
        if (is_park_block) {
            ++stats_.parks;
        }
    }
    std::set<std::string> landmarks;
    for (int r = 0; r < grid_.height(); ++r) {
        for (int c = 0; c < grid_.width(); ++c) {
            const auto& cell = grid_.at(r, c);
            if (cell.is_spawn_point) ++stats_.spawns;
            if (!cell.landmark_type.empty()) landmarks.insert(cell.landmark_type);
        }
    }
    stats_.landmarks = static_cast<int>(landmarks.size());
}

DesignBlueprint MapGenerator::to_design_blueprint(const std::string& profile_id) const {
    DesignBlueprint out;
    out.profile = profile_for(profile_id.empty() ? config_.city_profile : profile_id);
    out.seed = config_.master_seed;
    out.resolved_coast_side = to_string(resolved_coast_side_);
    out.width = grid_.width();
    out.height = grid_.height();
    out.required_asset_slots = {
        "terrain/water", "terrain/exterior", "street/road", "street/sidewalk",
        "landscape/park", "building/office", "building/shop", "building/apartment",
        "building/house", "building/restaurant", "building/market", "building/bank",
        "building/civic", "building/roof", "overlay/shadow", "prop/facade_kit",
        "landmark/town_hall", "landmark/station", "landmark/hospital",
        "landmark/police", "landmark/school"
    };
    for (int r = 0; r < grid_.height(); ++r) {
        for (int c = 0; c < grid_.width(); ++c) {
            const auto& cell = grid_.at(r, c);
            if (cell.is_road()) {
                out.roads.push_back({r, c, to_string(cell.road_category), grid_.road_bitmask(r, c),
                                     to_string(cell.zone_id), grid_.road_bitmask(r, c) == 15,
                                     "street/road"});
            }
        }
    }
    for (const auto& block : blocks_) {
        if (block.empty()) continue;
        int r0 = grid_.height(), c0 = grid_.width(), r1 = 0, c1 = 0;
        ZoneId zone = ZoneId::Unassigned;
        bool park = false;
        int id = -1;
        for (const auto [r, c] : block) {
            const auto& cell = grid_.at(r, c);
            id = cell.block_id;
            zone = cell.zone_id;
            park = park || cell.is_park;
            r0 = std::min(r0, r); r1 = std::max(r1, r);
            c0 = std::min(c0, c); c1 = std::max(c1, c);
        }
        out.blocks.push_back({id, static_cast<int>(block.size()), r0, c0, r1, c1, to_string(zone), park});
    }
    std::map<int, const BuildingAssemblyRecord*> building_by_lot;
    for (const auto& building : buildings_) {
        building_by_lot[building.lot_id] = &building;
        if (!building.landmark_type.empty()) {
            out.landmarks.push_back({building.landmark_type, building.anchor_row, building.anchor_col, building.asset_slot});
        }
        std::ostringstream reason;
        reason << "profile=" << out.profile.id
               << ";type=" << building.building_type
               << ";floors=" << building.floors
               << ";footprint=" << building.footprint_style;
        out.sprite_assignments.push_back({
            "building",
            building.id,
            building.anchor_row,
            building.anchor_col,
            building.asset_slot,
            building.sprite_stack,
            reason.str(),
            decision_hash(config_.master_seed, building.lot_id, building.floors, SALT_BUILDINGS)
        });
    }
    out.buildings = buildings_;
    for (const auto& lot : lots_) {
        if (lot.empty()) continue;
        const auto [r, c] = representative_point(lot);
        const auto& cell = grid_.at(r, c);
        const auto building_it = building_by_lot.find(cell.lot_id);
        const BuildingAssemblyRecord* building = building_it == building_by_lot.end() ? nullptr : building_it->second;
        out.lots.push_back({cell.lot_id, cell.block_id, static_cast<int>(lot.size()), to_string(cell.zone_id),
                            building ? building->building_type : "",
                            building ? building->landmark_type : "",
                            building ? building->asset_slot : "terrain/exterior"});
    }
    return out;
}

std::string to_string(CoastSide side) {
    switch (side) {
        case CoastSide::North: return "north";
        case CoastSide::South: return "south";
        case CoastSide::East: return "east";
        case CoastSide::West: return "west";
        case CoastSide::Random: return "random";
        default: return "none";
    }
}

std::string to_string(ZoneId zone) {
    switch (zone) {
        case ZoneId::CBD: return "cbd";
        case ZoneId::Midtown: return "midtown";
        case ZoneId::Residential: return "residential";
        default: return "unassigned";
    }
}

std::string to_string(RoadCategory category) {
    switch (category) {
        case RoadCategory::Highway: return "highway";
        case RoadCategory::Connector: return "connector";
        default: return "";
    }
}

CoastSide coast_side_from_string(const std::string& value) {
    if (value == "north") return CoastSide::North;
    if (value == "south") return CoastSide::South;
    if (value == "east") return CoastSide::East;
    if (value == "west") return CoastSide::West;
    if (value == "random") return CoastSide::Random;
    return CoastSide::None;
}

} // namespace mapping_algorithm
