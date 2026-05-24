#include "mapping_algorithm/map_generator.hpp"

#include <algorithm>
#include <cmath>
#include <numeric>
#include <queue>
#include <random>
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

} // namespace

MapGrid::MapGrid(int width, int height)
    : width_(width), height_(height), cells_(static_cast<std::size_t>(width * height)) {
    if (width <= 0 || height <= 0) {
        throw std::invalid_argument("MapGrid dimensions must be positive");
    }
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
    generate_coastline();
    generate_elevation();
    generate_zones();
    generate_civic_anchor();
    generate_highways();
    generate_connectors();
    generate_sidewalks();
    generate_blocks();
    generate_parks();
    generate_lots();
    compute_density();
    generate_buildings();
    generate_district_names();
    compute_stats();
}

void MapGenerator::generate_coastline() {
    CoastSide side = config_.coast_side;
    std::mt19937 rng(config_.master_seed ^ SALT_COAST);
    if (side == CoastSide::Random) {
        std::uniform_real_distribution<double> prob(0.0, 1.0);
        if (prob(rng) < 0.50) {
            std::uniform_int_distribution<int> dir(0, 3);
            side = static_cast<CoastSide>(static_cast<int>(CoastSide::North) + dir(rng));
        } else {
            side = CoastSide::None;
        }
    }

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

    std::uniform_real_distribution<double> prob(0.0, 1.0);
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
                const double roll = prob(rng);
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
    if (config_.coast_side == CoastSide::West) center_c = cols * 0.60;
    if (config_.coast_side == CoastSide::East) center_c = cols * 0.40;
    if (config_.coast_side == CoastSide::North) center_r = rows * 0.60;
    if (config_.coast_side == CoastSide::South) center_r = rows * 0.40;

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
        }
    }
}

void MapGenerator::generate_civic_anchor() {
    double best_score = -1.0;
    Point best{-1, -1};
    for (int r = 0; r < grid_.height(); ++r) {
        for (int c = 0; c < grid_.width(); ++c) {
            const auto& cell = grid_.at(r, c);
            if (!cell.is_land || cell.zone_id != ZoneId::CBD) {
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
        grid_.at(best.first, best.second).is_civic_anchor = true;
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
    std::mt19937 rng(config_.master_seed ^ SALT_HIGHWAY);
    std::uniform_int_distribution<int> ns_dist(config_.highway_ns_min, std::max(config_.highway_ns_min, config_.highway_ns_max));
    std::uniform_int_distribution<int> ew_dist(config_.highway_ew_min, std::max(config_.highway_ew_min, config_.highway_ew_max));
    const int ns_count = ns_dist(rng);
    const int ew_count = ew_dist(rng);
    for (int i = 0; i < ns_count; ++i) {
        const int c = (i + 1) * grid_.width() / (ns_count + 1);
        for (int r = 0; r < grid_.height(); ++r) {
            const int drift = static_cast<int>(std::round((fbm(r / 20.0, i, config_.master_seed ^ SALT_HIGHWAY) - 0.5) * 2.0 * config_.highway_organic * 3.0));
            set_road(r, std::clamp(c + drift, 0, grid_.width() - 1), RoadCategory::Highway);
        }
    }
    for (int i = 0; i < ew_count; ++i) {
        const int r = (i + 1) * grid_.height() / (ew_count + 1);
        for (int c = 0; c < grid_.width(); ++c) {
            const int drift = static_cast<int>(std::round((fbm(c / 20.0, i + 99, config_.master_seed ^ SALT_HIGHWAY) - 0.5) * 2.0 * config_.highway_organic * 3.0));
            set_road(std::clamp(r + drift, 0, grid_.height() - 1), c, RoadCategory::Highway);
        }
    }
}

void MapGenerator::generate_connectors() {
    std::mt19937 rng(config_.master_seed ^ SALT_CONNECTOR);
    std::uniform_real_distribution<double> prob(0.0, 1.0);
    for (int c = config_.avenue_spacing; c < grid_.width(); c += config_.avenue_spacing) {
        if (prob(rng) > config_.connector_density) {
            continue;
        }
        for (int r = 0; r < grid_.height(); ++r) {
            if (!grid_.at(r, c).is_road()) {
                set_road(r, c, RoadCategory::Connector);
            }
        }
    }
    for (int r = config_.connector_spacing; r < grid_.height(); r += config_.connector_spacing) {
        if (prob(rng) > config_.connector_density) {
            continue;
        }
        for (int c = 0; c < grid_.width(); ++c) {
            if (!grid_.at(r, c).is_road()) {
                set_road(r, c, RoadCategory::Connector);
            }
        }
    }
    for (int d = 0; d < config_.diagonal_streets; ++d) {
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
            if (edge) {
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
    std::mt19937 rng(config_.master_seed ^ SALT_PARKS);
    std::vector<int> order(blocks_.size());
    std::iota(order.begin(), order.end(), 0);
    std::shuffle(order.begin(), order.end(), rng);
    const int target = std::max(1, static_cast<int>(blocks_.size()) / 8);
    for (int i = 0; i < target && i < static_cast<int>(order.size()); ++i) {
        for (const auto [r, c] : blocks_[static_cast<std::size_t>(order[i])]) {
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
        const int mid_c = (c0 + c1) / 2;
        std::set<Point> left;
        std::set<Point> right;
        for (const auto [r, c] : block) {
            (c <= mid_c ? left : right).insert({r, c});
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
    std::mt19937 rng(config_.master_seed ^ SALT_BUILDINGS);
    std::uniform_real_distribution<double> prob(0.0, 1.0);
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
                if (cell.zone_id == ZoneId::CBD) {
                    cell.tile_role = "bldg_cbd";
                    cell.building_type = prob(rng) < 0.7 ? "office" : "bank";
                } else if (cell.zone_id == ZoneId::Midtown) {
                    cell.tile_role = "bldg_mid";
                    cell.building_type = prob(rng) < 0.5 ? "shop" : "apartment";
                } else {
                    cell.tile_role = "bldg_resi";
                    cell.building_type = prob(rng) < 0.75 ? "house" : "school";
                }
            } else {
                cell.tile_role = "exterior";
            }
        }
    }
    if (civic_anchor_.first >= 0) {
        auto& c = grid_.at(civic_anchor_.first, civic_anchor_.second);
        c.landmark_type = "town_hall";
        c.building_type = "civic_hall";
        c.tile_role = "bldg_civic";
    }
    std::vector<std::string> landmarks = {"station", "hospital", "police", "school"};
    int placed = 0;
    for (auto& lot : lots_) {
        if (placed >= static_cast<int>(landmarks.size())) {
            break;
        }
        if (lot.empty()) {
            continue;
        }
        const auto [r, c] = *lot.begin();
        auto& cell = grid_.at(r, c);
        if (!cell.landmark_type.empty()) {
            continue;
        }
        cell.landmark_type = landmarks[static_cast<std::size_t>(placed)];
        cell.building_type = landmarks[static_cast<std::size_t>(placed)];
        cell.tile_role = "bldg_civic";
        ++placed;
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
    stats_.seed = config_.master_seed;
    stats_.width = grid_.width();
    stats_.height = grid_.height();
    stats_.land = grid_.land_count();
    stats_.water = grid_.water_count();
    stats_.roads = grid_.road_count();
    stats_.sidewalks = grid_.sidewalk_count();
    stats_.blocks = static_cast<int>(blocks_.size());
    stats_.lots = static_cast<int>(lots_.size());
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
    out.width = grid_.width();
    out.height = grid_.height();
    out.required_asset_slots = {
        "terrain/water", "terrain/exterior", "road/highway", "road/connector",
        "street/sidewalk", "landscape/park", "building/office", "building/shop",
        "building/apartment", "building/house", "landmark/town_hall",
        "landmark/station", "landmark/hospital", "landmark/police", "landmark/school"
    };
    for (int r = 0; r < grid_.height(); ++r) {
        for (int c = 0; c < grid_.width(); ++c) {
            const auto& cell = grid_.at(r, c);
            if (cell.is_road()) {
                out.roads.push_back({r, c, to_string(cell.road_category), grid_.road_bitmask(r, c),
                                     to_string(cell.zone_id), grid_.road_bitmask(r, c) == 15,
                                     cell.road_category == RoadCategory::Highway ? "road/highway" : "road/connector"});
            }
            if (!cell.landmark_type.empty()) {
                out.landmarks.push_back({cell.landmark_type, r, c, "landmark/" + cell.landmark_type});
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
    for (const auto& lot : lots_) {
        if (lot.empty()) continue;
        const auto [r, c] = *lot.begin();
        const auto& cell = grid_.at(r, c);
        out.lots.push_back({cell.lot_id, cell.block_id, static_cast<int>(lot.size()), to_string(cell.zone_id),
                            cell.building_type, cell.landmark_type,
                            cell.landmark_type.empty() ? "building/" + cell.building_type : "landmark/" + cell.landmark_type});
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
