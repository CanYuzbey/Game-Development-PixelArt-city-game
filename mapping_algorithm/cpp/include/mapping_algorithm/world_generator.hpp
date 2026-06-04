#pragma once

#include "mapping_algorithm/map_generator.hpp"
#include <cstdint>
#include <string>
#include <vector>

namespace mapping_algorithm {

struct WorldConfig {
    std::uint32_t world_seed = 1;
    int chunk_cols = 8;
    int chunk_rows = 6;
    int chunk_width = 256;
    int chunk_height = 256;
};

struct ChunkPlan {
    int cx = 0;
    int cy = 0;
    std::uint32_t chunk_seed = 0;
    std::string city_profile;
    CoastSide coast_side = CoastSide::None;
};

class WorldGenerator {
public:
    explicit WorldGenerator(WorldConfig config);

    // Plan all chunks — computes seeds and profiles; no MapGenerator runs.
    void plan();

    int chunk_count() const noexcept;
    const ChunkPlan& chunk_at(int cx, int cy) const;

    // Build a MapConfig for one chunk (ready to pass to MapGenerator).
    MapConfig config_for_chunk(int cx, int cy) const;

private:
    WorldConfig world_config_;
    std::vector<ChunkPlan> chunks_;

    static std::uint32_t derive_chunk_seed(std::uint32_t world_seed, int cx, int cy) noexcept;
    static std::string profile_for_chunk(int cx, int cy, int chunk_cols, int chunk_rows) noexcept;
    static CoastSide coast_for_chunk(int cx, int cy, int chunk_cols, int chunk_rows) noexcept;
};

} // namespace mapping_algorithm
