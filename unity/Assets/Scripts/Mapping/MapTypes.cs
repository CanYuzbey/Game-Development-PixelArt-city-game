using System;
using System.Collections.Generic;

namespace GameDev.Mapping
{
    public enum CoastSide
    {
        None = 0,
        North = 1,
        South = 2,
        East = 3,
        West = 4,
        Random = 5
    }

    public enum ZoneId
    {
        Unassigned = -1,
        CBD = 0,
        Midtown = 1,
        Residential = 2
    }

    public enum RoadCategory
    {
        None = 0,
        Highway = 1,
        Connector = 2
    }

    [Serializable]
    public sealed class MapConfig
    {
        public int width = 96;
        public int height = 72;
        public uint masterSeed = 1;
        public string cityProfile = "generic_dense";

        public CoastSide coastSide = CoastSide.None;
        public double coastCoverage = 0.24;
        public double coastNoiseScale = 3.5;
        public int coastSmoothingPasses = 2;

        public int highwayNsMin = 2;
        public int highwayNsMax = 5;
        public int highwayEwMin = 0;
        public int highwayEwMax = 3;
        public double highwayOrganic = 0.3;
        public double connectorOrganic = 0.08;

        public double connectorDensity = 0.65;
        public int connectorSpacing = 8;
        public int avenueSpacing = 18;
        public int minBlockDepth = 2;
        public double connectorTurnBias = 0.08;
        public int roundaboutCount = 8;
        public int diagonalStreets = 2;
        public int sidewalkDepth = 1;
        public double sidewalkDamageRate = 0.15;

        public bool forceWestHighway;
        public bool forceEastHighway;
        public bool forceNorthHighway;
        public bool forceSouthHighway;
        public bool enableLocalRivers = true;

        public bool hasWorldChunkMetadata;
        public uint worldSeed;
        public int chunkX = -1;
        public int chunkY = -1;
        public int chunkSize;

        public MapConfig Clone()
        {
            return (MapConfig)MemberwiseClone();
        }
    }

    [Serializable]
    public sealed class MapCell
    {
        public bool isWater;
        public bool isLand;
        public RoadCategory roadCategory = RoadCategory.None;
        public ZoneId zoneId = ZoneId.Unassigned;
        public int blockId = -1;
        public int lotId = -1;
        public double densityScore;
        public bool isPark;
        public bool isCivicAnchor;
        public bool isSetback;
        public bool isDamaged;
        public bool isBridge;
        public bool isRoadTurn;
        public bool isIntersection;
        public string coastType = "";
        public string tileRole = "";
        public string buildingType = "";
        public double encounterChance;
        public bool isSpawnPoint;
        public string landmarkType = "";
        public double elevation;
        public string footprintStyle = "";
        public string districtName = "";
        public string streetFacing = "";

        public bool IsRoad
        {
            get { return roadCategory != RoadCategory.None; }
        }
    }

    public sealed class MapGrid
    {
        private readonly int width;
        private readonly int height;
        private readonly MapCell[] cells;

        public MapGrid(int width, int height)
        {
            if (width <= 0 || height <= 0)
            {
                throw new ArgumentException("MapGrid dimensions must be positive");
            }

            this.width = width;
            this.height = height;
            cells = new MapCell[width * height];
            for (int i = 0; i < cells.Length; ++i)
            {
                cells[i] = new MapCell();
            }
        }

        public int Width
        {
            get { return width; }
        }

        public int Height
        {
            get { return height; }
        }

        public bool InBounds(int row, int col)
        {
            return row >= 0 && row < height && col >= 0 && col < width;
        }

        public MapCell At(int row, int col)
        {
            if (!InBounds(row, col))
            {
                throw new ArgumentOutOfRangeException("row", "MapGrid.At");
            }

            return cells[row * width + col];
        }

        public int RoadBitmask(int row, int col)
        {
            int mask = 0;
            int[] bits = { 8, 2, 1, 4 };
            int[] dr = { -1, 1, 0, 0 };
            int[] dc = { 0, 0, -1, 1 };

            for (int i = 0; i < 4; ++i)
            {
                int nr = row + dr[i];
                int nc = col + dc[i];
                if (InBounds(nr, nc) && At(nr, nc).IsRoad)
                {
                    mask |= bits[i];
                }
            }

            return mask;
        }

        public int LandCount()
        {
            int count = 0;
            for (int i = 0; i < cells.Length; ++i)
            {
                if (cells[i].isLand)
                {
                    ++count;
                }
            }

            return count;
        }

        public int WaterCount()
        {
            int count = 0;
            for (int i = 0; i < cells.Length; ++i)
            {
                if (cells[i].isWater)
                {
                    ++count;
                }
            }

            return count;
        }

        public int RoadCount()
        {
            int count = 0;
            for (int i = 0; i < cells.Length; ++i)
            {
                if (cells[i].IsRoad)
                {
                    ++count;
                }
            }

            return count;
        }

        public int SidewalkCount()
        {
            int count = 0;
            for (int i = 0; i < cells.Length; ++i)
            {
                if (cells[i].tileRole == "sidewalk")
                {
                    ++count;
                }
            }

            return count;
        }
    }

    [Serializable]
    public sealed class MapStats
    {
        public uint seed;
        public int width;
        public int height;
        public int land;
        public int water;
        public int roads;
        public int sidewalks;
        public int blocks;
        public int parks;
        public int lots;
        public int spawns;
        public int landmarks;
        public int buildings;

        public MapStats Clone()
        {
            return (MapStats)MemberwiseClone();
        }
    }

    [Serializable]
    public sealed class CityProfile
    {
        public string id = "";
        public string label = "";
        public string streetPattern = "";
        public string blockRatio = "";
        public List<string> designTags = new List<string>();
        public List<string> assetStyleTags = new List<string>();
    }

    [Serializable]
    public sealed class RoadRecord
    {
        public int row;
        public int col;
        public string category = "";
        public int bitmask;
        public string zone = "";
        public bool isIntersection;
        public string assetSlot = "";
    }

    [Serializable]
    public sealed class BlockRecord
    {
        public int id = -1;
        public int area;
        public int r0;
        public int c0;
        public int r1;
        public int c1;
        public string zone = "";
        public bool isPark;
    }

    [Serializable]
    public sealed class LotRecord
    {
        public int id = -1;
        public int blockId = -1;
        public int area;
        public string zone = "";
        public string buildingType = "";
        public string landmarkType = "";
        public string assetSlot = "";
    }

    [Serializable]
    public sealed class LandmarkRecord
    {
        public string type = "";
        public int row;
        public int col;
        public string assetSlot = "";
    }

    [Serializable]
    public sealed class BuildingAssemblyRecord
    {
        public int id = -1;
        public int lotId = -1;
        public int blockId = -1;
        public int anchorRow;
        public int anchorCol;
        public int footprintR0;
        public int footprintC0;
        public int footprintR1;
        public int footprintC1;
        public int floors = 1;
        public string zone = "";
        public string buildingType = "";
        public string landmarkType = "";
        public string footprintStyle = "";
        public string facadeFamily = "";
        public string roofType = "";
        public string assetSlot = "";
        public List<string> spriteStack = new List<string>();
    }

    [Serializable]
    public sealed class SpriteAssignmentRecord
    {
        public string targetKind = "";
        public int targetId = -1;
        public int row;
        public int col;
        public string assetSlot = "";
        public List<string> spriteIds = new List<string>();
        public string reason = "";
        public uint decisionHash;
    }

    [Serializable]
    public sealed class DesignBlueprint
    {
        public string schema = "city_design_blueprint.v2";
        public uint seed;
        public string algorithmVersion = "mapping_algorithm_csharp.v1";
        public string resolvedCoastSide = "";
        public CityProfile profile = new CityProfile();
        public int width;
        public int height;
        public List<RoadRecord> roads = new List<RoadRecord>();
        public List<BlockRecord> blocks = new List<BlockRecord>();
        public List<LotRecord> lots = new List<LotRecord>();
        public List<LandmarkRecord> landmarks = new List<LandmarkRecord>();
        public List<BuildingAssemblyRecord> buildings = new List<BuildingAssemblyRecord>();
        public List<SpriteAssignmentRecord> spriteAssignments = new List<SpriteAssignmentRecord>();
        public List<string> requiredAssetSlots = new List<string>();
    }
}
