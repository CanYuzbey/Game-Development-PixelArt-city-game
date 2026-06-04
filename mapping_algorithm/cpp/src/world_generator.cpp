#include "mapping_algorithm/world_generator.hpp"
#include <stdexcept>

namespace mapping_algorithm {

namespace {

std::uint32_t mix_u32_wg(std::uint32_t x) {
    x ^= x >> 16;
    x *= 0x7feb352dU;
    x ^= x >> 15;
    x *= 0x846ca68bU;
    x ^= x >> 16;
    return x;
}

} // namespace

WorldGenerator::WorldGenerator(WorldConfig config)
    : world_config_(std::move(config)) {
    if (world_config_.chunk_cols <= 0 || world_config_.chunk_rows <= 0)
        throw std::invalid_argument("WorldConfig chunk dimensions must be positive");
    if (world_config_.chunk_width <= 0 || world_config_.chunk_height <= 0)
        throw std::invalid_argument("WorldConfig chunk size must be positive");
}

void WorldGenerator::plan() {
    chunks_.clear();
    chunks_.reserve(static_cast<std::size_t>(world_config_.chunk_cols * world_config_.chunk_rows));
    for (int cy = 0; cy < world_config_.chunk_rows; ++cy) {
        for (int cx = 0; cx < world_config_.chunk_cols; ++cx) {
            ChunkPlan plan;
            plan.cx = cx;
            plan.cy = cy;
            plan.chunk_seed = derive_chunk_seed(world_config_.world_seed, cx, cy);
            plan.city_profile = profile_for_chunk(cx, cy, world_config_.chunk_cols, world_config_.chunk_rows);
            plan.coast_side = coast_for_chunk(cx, cy, world_config_.chunk_cols, world_config_.chunk_rows);
            chunks_.push_back(plan);
        }
    }
}

int WorldGenerator::chunk_count() const noexcept {
    return static_cast<int>(chunks_.size());
}

const ChunkPlan& WorldGenerator::chunk_at(int cx, int cy) const {
    if (cx < 0 || cx >= world_config_.chunk_cols || cy < 0 || cy >= world_config_.chunk_rows)
        throw std::out_of_range("Chunk coordinates out of range");
    return chunks_[static_cast<std::size_t>(cy * world_config_.chunk_cols + cx)];
}

MapConfig WorldGenerator::config_for_chunk(int cx, int cy) const {
    const auto& plan = chunk_at(cx, cy);
    MapConfig cfg;
    cfg.master_seed = plan.chunk_seed;
    cfg.city_profile = plan.city_profile;
    cfg.coast_side = plan.coast_side;
    cfg.width = world_config_.chunk_width;
    cfg.height = world_config_.chunk_height;
    return cfg;
}

std::uint32_t WorldGenerator::derive_chunk_seed(std::uint32_t world_seed, int cx, int cy) noexcept {
    // Chunk seed formula from OPEN_WORLD_SPEC.md:
    // mix_u32(world_seed XOR cx*0x9e3779b9 XOR cy*0x517cc1b7)
    const std::uint32_t mixed =
        world_seed ^
        (static_cast<std::uint32_t>(cx) * 0x9e3779b9U) ^
        (static_cast<std::uint32_t>(cy) * 0x517cc1b7U);
    return mix_u32_wg(mixed);
}

std::string WorldGenerator::profile_for_chunk(int cx, int cy, int chunk_cols, int chunk_rows) noexcept {
    // World zone grid from OPEN_WORLD_SPEC.md:
    // CBD centre: cx 2–5, cy 1–4 → alternate manhattan / paris_haussmann
    // Midtown ring (one chunk out from CBD) → generic_dense
    // Residential outer → london_organic or barcelona_eixample
    const int cx_cbd_lo = chunk_cols / 4;
    const int cx_cbd_hi = (chunk_cols * 3) / 4 - 1;
    const int cy_cbd_lo = chunk_rows / 5;
    const int cy_cbd_hi = (chunk_rows * 4) / 5 - 1;

    const bool in_cbd = cx >= cx_cbd_lo && cx <= cx_cbd_hi && cy >= cy_cbd_lo && cy <= cy_cbd_hi;
    if (in_cbd) {
        return ((cx + cy) % 2 == 0) ? "manhattan" : "paris_haussmann";
    }

    const int cx_mid_lo = cx_cbd_lo - 1;
    const int cx_mid_hi = cx_cbd_hi + 1;
    const int cy_mid_lo = cy_cbd_lo - 1;
    const int cy_mid_hi = cy_cbd_hi + 1;
    const bool in_midtown = cx >= cx_mid_lo && cx <= cx_mid_hi && cy >= cy_mid_lo && cy <= cy_mid_hi;
    if (in_midtown) return "generic_dense";

    return (cx % 2 == 0) ? "london_organic" : "barcelona_eixample";
}

CoastSide WorldGenerator::coast_for_chunk(int cx, int cy, int chunk_cols, int chunk_rows) noexcept {
    // World edges get coastal chunks per OPEN_WORLD_SPEC.md
    if (cy == 0) return CoastSide::North;
    if (cy == chunk_rows - 1) return CoastSide::South;
    if (cx == 0) return CoastSide::West;
    if (cx == chunk_cols - 1) return CoastSide::East;
    return CoastSide::None;
}

} // namespace mapping_algorithm
