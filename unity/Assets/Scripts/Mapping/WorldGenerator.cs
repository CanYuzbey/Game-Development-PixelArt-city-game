using System;
using System.Collections.Generic;

namespace GameDev.Mapping
{
    public enum WorldZone
    {
        CBD = 0,
        Midtown = 1,
        Residential = 2
    }

    [Serializable]
    public sealed class WorldConfig
    {
        public uint worldSeed = 1;
        public int chunkCols = 8;
        public int chunkRows = 6;
        public int chunkWidth = 256;
        public int chunkHeight = 256;
    }

    [Serializable]
    public sealed class ChunkPlan
    {
        public int cx;
        public int cy;
        public uint chunkSeed;
        public string cityProfile = "";
        public CoastSide coastSide = CoastSide.None;
        public WorldZone worldZone = WorldZone.Residential;
    }

    public sealed class WorldGenerator
    {
        private const uint SaltWorldHighwayNs = 0xDEADBEEFu;
        private const uint SaltWorldHighwayEw = 0xBEEFCAFEu;

        private readonly WorldConfig config;
        private readonly List<ChunkPlan> chunks = new List<ChunkPlan>();

        public WorldGenerator(WorldConfig config)
        {
            if (config == null)
            {
                throw new ArgumentNullException("config");
            }

            if (config.chunkCols <= 0 || config.chunkRows <= 0)
            {
                throw new ArgumentException("WorldConfig chunk dimensions must be positive");
            }

            if (config.chunkWidth <= 0 || config.chunkHeight <= 0)
            {
                throw new ArgumentException("WorldConfig chunk size must be positive");
            }

            this.config = config;
        }

        public IList<ChunkPlan> Chunks
        {
            get { return chunks.AsReadOnly(); }
        }

        public void Plan()
        {
            chunks.Clear();
            chunks.Capacity = Math.Max(chunks.Capacity, config.chunkCols * config.chunkRows);

            for (int cy = 0; cy < config.chunkRows; ++cy)
            {
                for (int cx = 0; cx < config.chunkCols; ++cx)
                {
                    WorldZone zone = WorldZoneForChunk(cx, cy, config.chunkCols, config.chunkRows);
                    chunks.Add(new ChunkPlan
                    {
                        cx = cx,
                        cy = cy,
                        chunkSeed = DeriveChunkSeed(config.worldSeed, cx, cy),
                        cityProfile = ProfileForChunk(cx, cy, config.chunkCols, config.chunkRows),
                        coastSide = CoastForChunk(cx, cy, config.chunkCols, config.chunkRows),
                        worldZone = zone
                    });
                }
            }
        }

        public int ChunkCount()
        {
            EnsurePlanned();
            return chunks.Count;
        }

        public ChunkPlan ChunkAt(int cx, int cy)
        {
            EnsurePlanned();
            if (cx < 0 || cx >= config.chunkCols || cy < 0 || cy >= config.chunkRows)
            {
                throw new ArgumentOutOfRangeException("cx", "Chunk coordinates out of range");
            }

            return chunks[cy * config.chunkCols + cx];
        }

        public MapConfig ConfigForChunk(int cx, int cy)
        {
            ChunkPlan plan = ChunkAt(cx, cy);
            MapConfig mapConfig = new MapConfig();
            mapConfig.masterSeed = plan.chunkSeed;
            mapConfig.cityProfile = plan.cityProfile;
            mapConfig.coastSide = plan.coastSide;
            mapConfig.width = config.chunkWidth;
            mapConfig.height = config.chunkHeight;
            mapConfig.enableLocalRivers = false;
            mapConfig.hasWorldChunkMetadata = true;
            mapConfig.worldSeed = config.worldSeed;
            mapConfig.chunkX = cx;
            mapConfig.chunkY = cy;
            mapConfig.chunkSize = config.chunkWidth;
            ApplyHighwayBoundaryConstraints(mapConfig, cx, cy);
            return mapConfig;
        }

        public List<int> HighwayNsColumns()
        {
            return HighwayNsColumns(config.worldSeed, config.chunkCols);
        }

        public List<int> HighwayEwRows()
        {
            return HighwayEwRows(config.worldSeed, config.chunkRows);
        }

        public static uint DeriveChunkSeed(uint worldSeed, int cx, int cy)
        {
            unchecked
            {
                uint mixed = worldSeed ^
                    ((uint)cx * 0x9e3779b9u) ^
                    ((uint)cy * 0x517cc1b7u);
                return MapGenerator.MixU32(mixed);
            }
        }

        public static WorldZone WorldZoneForChunk(int cx, int cy, int chunkCols = 8, int chunkRows = 6)
        {
            double nx = Math.Abs(cx - (chunkCols - 1) / 2.0) / (chunkCols / 2.0);
            double ny = Math.Abs(cy - (chunkRows - 1) / 2.0) / (chunkRows / 2.0);
            double dist = Math.Max(nx, ny);

            if (dist <= 0.30) return WorldZone.CBD;
            if (dist <= 0.65) return WorldZone.Midtown;
            return WorldZone.Residential;
        }

        public static string ProfileForChunk(int cx, int cy, int chunkCols = 8, int chunkRows = 6)
        {
            WorldZone zone = WorldZoneForChunk(cx, cy, chunkCols, chunkRows);
            switch (zone)
            {
                case WorldZone.CBD:
                    return (cx + cy) % 2 == 0 ? "manhattan" : "paris_haussmann";
                case WorldZone.Midtown:
                    return "generic_dense";
                default:
                    return "london_organic";
            }
        }

        public static CoastSide CoastForChunk(int cx, int cy, int chunkCols = 8, int chunkRows = 6)
        {
            if (cy == 0) return CoastSide.North;
            if (cy == chunkRows - 1) return CoastSide.South;
            if (cx == 0) return CoastSide.West;
            if (cx == chunkCols - 1) return CoastSide.East;
            return CoastSide.None;
        }

        public static List<int> HighwayNsColumns(uint worldSeed, int chunkCols = 8)
        {
            uint h = MapGenerator.MixU32(worldSeed ^ SaltWorldHighwayNs);
            int offset = (int)(h % 2u);
            List<int> columns = new List<int> { 1 + offset, 3, 5 + offset };
            return FilterInterior(columns, chunkCols);
        }

        public static List<int> HighwayEwRows(uint worldSeed, int chunkRows = 6)
        {
            uint h = MapGenerator.MixU32(worldSeed ^ SaltWorldHighwayEw);
            int offset = (int)(h % 2u);
            List<int> rows = new List<int> { 1 + offset, 4 };
            return FilterInterior(rows, chunkRows);
        }

        private static List<int> FilterInterior(List<int> values, int upperBound)
        {
            List<int> filtered = new List<int>();
            for (int i = 0; i < values.Count; ++i)
            {
                int value = values[i];
                if (value > 0 && value < upperBound - 1 && !filtered.Contains(value))
                {
                    filtered.Add(value);
                }
            }

            filtered.Sort();
            return filtered;
        }

        private void ApplyHighwayBoundaryConstraints(MapConfig mapConfig, int cx, int cy)
        {
            List<int> nsColumns = HighwayNsColumns();
            List<int> ewRows = HighwayEwRows();

            mapConfig.forceWestHighway = nsColumns.Contains(cx - 1);
            mapConfig.forceEastHighway = nsColumns.Contains(cx);
            mapConfig.forceNorthHighway = ewRows.Contains(cy - 1);
            mapConfig.forceSouthHighway = ewRows.Contains(cy);
        }

        private void EnsurePlanned()
        {
            if (chunks.Count == 0)
            {
                Plan();
            }
        }
    }
}
