using System;
using System.Collections.Generic;
using System.Text;

namespace GameDev.Mapping
{
    public sealed class MapGenerator
    {
        private const uint SaltCoast = 0xAB1234u;
        private const uint SaltRiver = 0xC0A57EA7u;
        private const uint SaltElevation = 0xE1E2E3E4u;
        private const uint SaltHighway = 0xCD5678u;
        private const uint SaltConnector = 0xEF9ABCu;
        private const uint SaltParks = 0xA1B2C3u;
        private const uint SaltBuildings = 0xB1C2D3u;
        private const int MaxMapDimension = 512;

        private static readonly MapGenerationPhase[] Pipeline =
        {
            MapGenerationPhase.LandAndSea,
            MapGenerationPhase.LocalRiverWater,
            MapGenerationPhase.Elevation,
            MapGenerationPhase.Zones,
            MapGenerationPhase.Highways,
            MapGenerationPhase.Roads,
            MapGenerationPhase.Bridges,
            MapGenerationPhase.RoadAnnotations,
            MapGenerationPhase.Sidewalks,
            MapGenerationPhase.Blocks,
            MapGenerationPhase.CivicAnchor,
            MapGenerationPhase.Parks,
            MapGenerationPhase.Lots,
            MapGenerationPhase.Density,
            MapGenerationPhase.Buildings,
            MapGenerationPhase.DistrictNames,
            MapGenerationPhase.Stats
        };

        private readonly MapConfig config;
        private MapGrid grid;
        private MapStats stats = new MapStats();
        private readonly List<SortedSet<Point>> blocks = new List<SortedSet<Point>>();
        private readonly List<SortedSet<Point>> lots = new List<SortedSet<Point>>();
        private readonly List<BuildingAssemblyRecord> buildings = new List<BuildingAssemblyRecord>();
        private readonly List<RiverBridgeCandidate> riverBridgeCandidates = new List<RiverBridgeCandidate>();
        private Point civicAnchor = new Point(-1, -1);
        private CoastSide resolvedCoastSide = CoastSide.None;
        private double cbdCenterR;
        private double cbdCenterC;
        private int archetype;

        public MapGenerator(MapConfig config)
        {
            if (config == null)
            {
                throw new ArgumentNullException("config");
            }

            this.config = config.Clone();
            grid = new MapGrid(SafeInitialGridDimension(this.config.width), SafeInitialGridDimension(this.config.height));
            ValidateConfig();
        }

        public MapConfig Config
        {
            get { return config.Clone(); }
        }

        public MapGrid Grid
        {
            get { return grid; }
        }

        public MapStats Stats
        {
            get { return stats; }
        }

        public IList<BuildingAssemblyRecord> Buildings
        {
            get { return buildings.AsReadOnly(); }
        }

        public CoastSide ResolvedCoastSide
        {
            get { return resolvedCoastSide; }
        }

        public static MapGenerationPhase[] GetPhaseOrder()
        {
            return (MapGenerationPhase[])Pipeline.Clone();
        }

        public void Generate()
        {
            ValidateConfig();
            grid = new MapGrid(config.width, config.height);
            stats = new MapStats();
            blocks.Clear();
            lots.Clear();
            buildings.Clear();
            riverBridgeCandidates.Clear();
            civicAnchor = new Point(-1, -1);
            resolvedCoastSide = CoastSide.None;

            for (int i = 0; i < Pipeline.Length; ++i)
            {
                ExecutePhase(Pipeline[i]);
            }
        }

        private void ExecutePhase(MapGenerationPhase phase)
        {
            switch (phase)
            {
                case MapGenerationPhase.LandAndSea:
                    GenerateCoastline();
                    break;
                case MapGenerationPhase.LocalRiverWater:
                    GenerateRiver();
                    break;
                case MapGenerationPhase.Elevation:
                    GenerateElevation();
                    break;
                case MapGenerationPhase.Zones:
                    GenerateZones();
                    break;
                case MapGenerationPhase.Highways:
                    GenerateHighways();
                    break;
                case MapGenerationPhase.Roads:
                    GenerateConnectors();
                    break;
                case MapGenerationPhase.Bridges:
                    GenerateBridgeCrossings();
                    break;
                case MapGenerationPhase.RoadAnnotations:
                    GenerateRoadAnnotations();
                    break;
                case MapGenerationPhase.Sidewalks:
                    GenerateSidewalks();
                    break;
                case MapGenerationPhase.Blocks:
                    GenerateBlocks();
                    break;
                case MapGenerationPhase.CivicAnchor:
                    GenerateCivicAnchor();
                    break;
                case MapGenerationPhase.Parks:
                    GenerateParks();
                    break;
                case MapGenerationPhase.Lots:
                    GenerateLots();
                    break;
                case MapGenerationPhase.Density:
                    ComputeDensity();
                    break;
                case MapGenerationPhase.Buildings:
                    GenerateBuildings();
                    break;
                case MapGenerationPhase.DistrictNames:
                    GenerateDistrictNames();
                    break;
                case MapGenerationPhase.Stats:
                    ComputeStats();
                    break;
                default:
                    throw new ArgumentOutOfRangeException("phase", phase, "Unknown map generation phase");
            }
        }

        public DesignBlueprint ToDesignBlueprint(string profileId = "")
        {
            DesignBlueprint output = new DesignBlueprint();
            output.profile = ProfileFor(string.IsNullOrEmpty(profileId) ? config.cityProfile : profileId);
            output.seed = config.masterSeed;
            output.resolvedCoastSide = MappingStrings.ToSerializedString(resolvedCoastSide);
            output.width = grid.Width;
            output.height = grid.Height;
            output.requiredAssetSlots = new List<string>
            {
                "terrain/water", "terrain/exterior", "street/road", "street/sidewalk",
                "landscape/park", "building/office", "building/shop", "building/apartment",
                "building/house", "building/restaurant", "building/market", "building/bank",
                "building/civic", "building/roof", "overlay/shadow", "prop/facade_kit",
                "landmark/town_hall", "landmark/station", "landmark/hospital",
                "landmark/police", "landmark/school"
            };

            for (int r = 0; r < grid.Height; ++r)
            {
                for (int c = 0; c < grid.Width; ++c)
                {
                    MapCell cell = grid.At(r, c);
                    if (!cell.IsRoad)
                    {
                        continue;
                    }

                    output.roads.Add(new RoadRecord
                    {
                        row = r,
                        col = c,
                        category = MappingStrings.ToSerializedString(cell.roadCategory),
                        bitmask = grid.RoadBitmask(r, c),
                        zone = MappingStrings.ToSerializedString(cell.zoneId),
                        isIntersection = cell.isIntersection,
                        assetSlot = "street/road"
                    });
                }
            }

            for (int i = 0; i < blocks.Count; ++i)
            {
                SortedSet<Point> block = blocks[i];
                if (block.Count == 0)
                {
                    continue;
                }

                int r0 = grid.Height;
                int c0 = grid.Width;
                int r1 = 0;
                int c1 = 0;
                ZoneId zone = ZoneId.Unassigned;
                bool park = false;
                int id = -1;

                foreach (Point p in block)
                {
                    MapCell cell = grid.At(p.r, p.c);
                    id = cell.blockId;
                    zone = cell.zoneId;
                    park = park || cell.isPark;
                    r0 = Math.Min(r0, p.r);
                    r1 = Math.Max(r1, p.r);
                    c0 = Math.Min(c0, p.c);
                    c1 = Math.Max(c1, p.c);
                }

                output.blocks.Add(new BlockRecord
                {
                    id = id,
                    area = block.Count,
                    r0 = r0,
                    c0 = c0,
                    r1 = r1,
                    c1 = c1,
                    zone = MappingStrings.ToSerializedString(zone),
                    isPark = park
                });
            }

            Dictionary<int, BuildingAssemblyRecord> buildingByLot = new Dictionary<int, BuildingAssemblyRecord>();
            for (int i = 0; i < buildings.Count; ++i)
            {
                BuildingAssemblyRecord building = buildings[i];
                buildingByLot[building.lotId] = building;
                if (!string.IsNullOrEmpty(building.landmarkType))
                {
                    output.landmarks.Add(new LandmarkRecord
                    {
                        type = building.landmarkType,
                        row = building.anchorRow,
                        col = building.anchorCol,
                        assetSlot = building.assetSlot
                    });
                }

                StringBuilder reason = new StringBuilder();
                reason.Append("profile=").Append(output.profile.id)
                    .Append(";type=").Append(building.buildingType)
                    .Append(";floors=").Append(building.floors)
                    .Append(";footprint=").Append(building.footprintStyle);

                output.spriteAssignments.Add(new SpriteAssignmentRecord
                {
                    targetKind = "building",
                    targetId = building.id,
                    row = building.anchorRow,
                    col = building.anchorCol,
                    assetSlot = building.assetSlot,
                    spriteIds = new List<string>(building.spriteStack),
                    reason = reason.ToString(),
                    decisionHash = DecisionHash(config.masterSeed, building.lotId, building.floors, SaltBuildings)
                });

                output.buildings.Add(building);
            }

            for (int i = 0; i < lots.Count; ++i)
            {
                SortedSet<Point> lot = lots[i];
                if (lot.Count == 0)
                {
                    continue;
                }

                Point p = RepresentativePoint(lot);
                MapCell cell = grid.At(p.r, p.c);
                BuildingAssemblyRecord building = null;
                buildingByLot.TryGetValue(cell.lotId, out building);

                output.lots.Add(new LotRecord
                {
                    id = cell.lotId,
                    blockId = cell.blockId,
                    area = lot.Count,
                    zone = MappingStrings.ToSerializedString(cell.zoneId),
                    buildingType = building != null ? building.buildingType : "",
                    landmarkType = building != null ? building.landmarkType : "",
                    assetSlot = building != null ? building.assetSlot : "terrain/exterior"
                });
            }

            return output;
        }

        private void ValidateConfig()
        {
            if (config.width <= 0 || config.height <= 0)
            {
                throw new ArgumentException("MapConfig dimensions must be positive");
            }

            if (config.width > MaxMapDimension || config.height > MaxMapDimension)
            {
                throw new ArgumentException("MapConfig dimensions exceed supported 512x512 guard rail");
            }

            if (!IsValidCoastSide(config.coastSide))
            {
                throw new ArgumentException("MapConfig coastSide is invalid");
            }

            if (!MappingStrings.IsValidCityProfile(config.cityProfile))
            {
                throw new ArgumentException("MapConfig cityProfile is unknown");
            }

            if (config.connectorSpacing <= 0 || config.avenueSpacing <= 0)
            {
                throw new ArgumentException("MapConfig road spacing must be positive");
            }

            if (config.minBlockDepth <= 0)
            {
                throw new ArgumentException("MapConfig minBlockDepth must be positive");
            }

            if (config.coastSmoothingPasses < 0)
            {
                throw new ArgumentException("MapConfig coastSmoothingPasses must be non-negative");
            }

            if (config.coastSmoothingPasses > Math.Max(config.width, config.height))
            {
                throw new ArgumentException("MapConfig coastSmoothingPasses exceeds map dimensions");
            }

            if (config.highwayNsMin < 0 || config.highwayEwMin < 0 ||
                config.highwayNsMax < config.highwayNsMin ||
                config.highwayEwMax < config.highwayEwMin)
            {
                throw new ArgumentException("MapConfig highway ranges are invalid");
            }

            if (config.highwayNsMax > config.width || config.highwayEwMax > config.height)
            {
                throw new ArgumentException("MapConfig highway ranges exceed map dimensions");
            }

            if (double.IsNaN(config.coastCoverage) || double.IsInfinity(config.coastCoverage) ||
                config.coastCoverage < 0.0 || config.coastCoverage > 0.75)
            {
                throw new ArgumentException("MapConfig coastCoverage must be in [0.0, 0.75]");
            }

            if (double.IsNaN(config.coastNoiseScale) || double.IsInfinity(config.coastNoiseScale) ||
                config.coastNoiseScale <= 0.0)
            {
                throw new ArgumentException("MapConfig coastNoiseScale must be positive");
            }

            if (double.IsNaN(config.highwayOrganic) || double.IsInfinity(config.highwayOrganic) ||
                config.highwayOrganic < 0.0 || config.highwayOrganic > 1.0)
            {
                throw new ArgumentException("MapConfig highwayOrganic must be in [0.0, 1.0]");
            }

            if (double.IsNaN(config.connectorOrganic) || double.IsInfinity(config.connectorOrganic) ||
                config.connectorOrganic < 0.0 || config.connectorOrganic > 0.5)
            {
                throw new ArgumentException("MapConfig connectorOrganic must be in [0.0, 0.5]");
            }

            if (double.IsNaN(config.connectorDensity) || double.IsInfinity(config.connectorDensity) ||
                config.connectorDensity < 0.0 || config.connectorDensity > 1.0)
            {
                throw new ArgumentException("MapConfig connectorDensity must be in [0.0, 1.0]");
            }

            if (double.IsNaN(config.connectorTurnBias) || double.IsInfinity(config.connectorTurnBias) ||
                config.connectorTurnBias < 0.0 || config.connectorTurnBias > 1.0)
            {
                throw new ArgumentException("MapConfig connectorTurnBias must be in [0.0, 1.0]");
            }

            if (config.roundaboutCount < 0 || config.diagonalStreets < 0 || config.sidewalkDepth < 0)
            {
                throw new ArgumentException("MapConfig generated feature counts must be non-negative");
            }

            if (config.diagonalStreets > Math.Max(config.width, config.height))
            {
                throw new ArgumentException("MapConfig diagonalStreets exceeds map dimensions");
            }

            if (config.sidewalkDepth > Math.Min(config.width, config.height))
            {
                throw new ArgumentException("MapConfig sidewalkDepth exceeds map dimensions");
            }

            if (double.IsNaN(config.sidewalkDamageRate) || double.IsInfinity(config.sidewalkDamageRate) ||
                config.sidewalkDamageRate < 0.0 || config.sidewalkDamageRate > 1.0)
            {
                throw new ArgumentException("MapConfig sidewalkDamageRate must be in [0.0, 1.0]");
            }
        }

        private void GenerateCoastline()
        {
            CoastSide side = config.coastSide;
            if (side == CoastSide.Random)
            {
                if (Decision01(config.masterSeed, 11, 7, SaltCoast) < 0.50)
                {
                    int dir = DecisionRange(config.masterSeed, 19, 3, SaltCoast, 0, 3);
                    side = (CoastSide)((int)CoastSide.North + dir);
                }
                else
                {
                    side = CoastSide.None;
                }
            }

            resolvedCoastSide = side;
            int rows = grid.Height;
            int cols = grid.Width;

            if (side == CoastSide.None)
            {
                for (int r = 0; r < rows; ++r)
                {
                    for (int c = 0; c < cols; ++c)
                    {
                        MapCell cell = grid.At(r, c);
                        cell.isLand = true;
                        cell.isWater = false;
                    }
                }

                return;
            }

            List<double> flat = new List<double>(rows * cols);
            double[,] raw = new double[rows, cols];
            for (int r = 0; r < rows; ++r)
            {
                for (int c = 0; c < cols; ++c)
                {
                    double nx = (double)c / cols * config.coastNoiseScale;
                    double ny = (double)r / rows * config.coastNoiseScale;
                    double noise = Fbm(nx, ny, config.masterSeed ^ SaltCoast, 4);
                    double bias = DirectionalGradient(r, c, rows, cols, side);
                    raw[r, c] = noise * 0.72 + bias * 0.28;
                    flat.Add(raw[r, c]);
                }
            }

            flat.Sort();
            int cutoff = Math.Min(flat.Count - 1, (int)(config.coastCoverage * flat.Count));
            double threshold = flat[cutoff];
            bool[,] land = new bool[rows, cols];
            for (int r = 0; r < rows; ++r)
            {
                for (int c = 0; c < cols; ++c)
                {
                    land[r, c] = raw[r, c] >= threshold;
                }
            }

            land = SmoothLand(land, config.coastSmoothingPasses);

            for (int r = 0; r < rows; ++r)
            {
                for (int c = 0; c < cols; ++c)
                {
                    MapCell cell = grid.At(r, c);
                    cell.isLand = land[r, c];
                    cell.isWater = !land[r, c];
                }
            }

            for (int r = 0; r < rows; ++r)
            {
                for (int c = 0; c < cols; ++c)
                {
                    MapCell cell = grid.At(r, c);
                    if (!cell.isLand)
                    {
                        continue;
                    }

                    bool shoreline = false;
                    List<Point> neighbours = Neighbours4(r, c);
                    for (int i = 0; i < neighbours.Count; ++i)
                    {
                        Point n = neighbours[i];
                        if (grid.InBounds(n.r, n.c) && grid.At(n.r, n.c).isWater)
                        {
                            shoreline = true;
                            break;
                        }
                    }

                    if (shoreline)
                    {
                        int segmentId = (r + c) / 6;
                        double roll = Decision01(config.masterSeed, segmentId, 0x7CE, SaltCoast);
                        cell.coastType = roll < 0.35 ? "cliff" : (roll < 0.80 ? "beach" : "dock");
                    }
                }
            }
        }

        private void GenerateRiver()
        {
            if (!config.enableLocalRivers)
            {
                return;
            }

            if (resolvedCoastSide != CoastSide.None)
            {
                return;
            }

            if (Decision01(config.masterSeed, 0x4A, 0x3B, SaltRiver) >= 0.40)
            {
                return;
            }

            int rows = grid.Height;
            int cols = grid.Width;
            bool ns = Decision01(config.masterSeed, 0x7C, 0x2E, SaltRiver) < 0.50;
            double amplitude = (ns ? cols : rows) / 8.0;
            int perpRange = ns ? cols : rows;
            int startPos = perpRange / 4 +
                (int)(Decision01(config.masterSeed, 0x1A, 0x5F, SaltRiver) * (perpRange / 2.0));

            int travel = ns ? rows : cols;
            List<Point> riverCells = new List<Point>(travel);
            for (int i = 0; i < travel; ++i)
            {
                double t = (double)i / Math.Max(travel - 1, 1);
                double noise = (Fbm(t * 3.0, 0.0, config.masterSeed ^ SaltRiver, 4) - 0.5) * 2.0;
                int pos = RoundToInt(startPos + noise * amplitude);
                int r = ns ? i : ClampInt(pos, 0, rows - 1);
                int c = ns ? ClampInt(pos, 0, cols - 1) : i;
                MapCell cell = grid.At(r, c);
                cell.isWater = true;
                cell.isLand = false;
                cell.coastType = "";
                riverCells.Add(new Point(r, c));
            }

            int crossingSpacing = Math.Max(6, ns ? config.connectorSpacing : config.avenueSpacing);
            bool recordedBridge = false;

            for (int i = 0; i < riverCells.Count; ++i)
            {
                Point p = riverCells[i];
                int axis = ns ? p.r : p.c;
                if (axis > 0 && axis < travel - 1 && axis % crossingSpacing == 0)
                {
                    riverBridgeCandidates.Add(new RiverBridgeCandidate(p, ns));
                    recordedBridge = true;
                }
            }

            if (!recordedBridge && riverCells.Count > 0)
            {
                riverBridgeCandidates.Add(new RiverBridgeCandidate(riverCells[riverCells.Count / 2], ns));
            }

            for (int r = 0; r < rows; ++r)
            {
                for (int c = 0; c < cols; ++c)
                {
                    MapCell cell = grid.At(r, c);
                    if (!cell.isLand)
                    {
                        continue;
                    }

                    bool shoreline = false;
                    List<Point> neighbours = Neighbours4(r, c);
                    for (int i = 0; i < neighbours.Count; ++i)
                    {
                        Point n = neighbours[i];
                        if (grid.InBounds(n.r, n.c) && grid.At(n.r, n.c).isWater)
                        {
                            shoreline = true;
                            break;
                        }
                    }

                    if (shoreline)
                    {
                        int segmentId = (r + c) / 6;
                        double roll = Decision01(config.masterSeed, segmentId, 0x7CF, SaltRiver);
                        cell.coastType = roll < 0.35 ? "cliff" : (roll < 0.80 ? "beach" : "dock");
                    }
                }
            }
        }

        private void GenerateBridgeCrossings()
        {
            for (int i = 0; i < riverBridgeCandidates.Count; ++i)
            {
                RiverBridgeCandidate candidate = riverBridgeCandidates[i];
                MarkBridge(candidate.cell, candidate.northSouthRiver);
            }
        }

        private void MarkBridge(Point p, bool northSouthRiver)
        {
            MapCell cell = grid.At(p.r, p.c);
            cell.isWater = false;
            cell.isLand = true;
            cell.isBridge = true;
            cell.coastType = "";
            ApplyBridgeContext(cell, p);
            SetRoad(p.r, p.c, RoadCategory.Connector);

            Point[] approaches = northSouthRiver
                ? new[] { new Point(p.r, p.c - 1), new Point(p.r, p.c + 1) }
                : new[] { new Point(p.r - 1, p.c), new Point(p.r + 1, p.c) };

            for (int i = 0; i < approaches.Length; ++i)
            {
                SetRoad(approaches[i].r, approaches[i].c, RoadCategory.Connector);
            }

            if (northSouthRiver)
            {
                StitchBridgeApproach(p.r, p.c - 1, 0, -1);
                StitchBridgeApproach(p.r, p.c + 1, 0, 1);
            }
            else
            {
                StitchBridgeApproach(p.r - 1, p.c, -1, 0);
                StitchBridgeApproach(p.r + 1, p.c, 1, 0);
            }
        }

        private void ApplyBridgeContext(MapCell bridgeCell, Point bridgePoint)
        {
            bridgeCell.elevation = 0.12;
            bridgeCell.zoneId = ZoneId.Midtown;

            List<Point> neighbours = Neighbours4(bridgePoint.r, bridgePoint.c);
            for (int i = 0; i < neighbours.Count; ++i)
            {
                Point n = neighbours[i];
                if (!grid.InBounds(n.r, n.c))
                {
                    continue;
                }

                MapCell neighbour = grid.At(n.r, n.c);
                if (!neighbour.isLand || neighbour.isWater)
                {
                    continue;
                }

                bridgeCell.zoneId = neighbour.zoneId == ZoneId.Unassigned ? ZoneId.Midtown : neighbour.zoneId;
                bridgeCell.elevation = Math.Max(0.05, neighbour.elevation);
                return;
            }
        }

        private void StitchBridgeApproach(int row, int col, int dr, int dc)
        {
            const int MaxBridgeConnectorLength = 8;
            if (!grid.InBounds(row, col) || grid.At(row, col).isWater)
            {
                return;
            }

            List<Point> path = new List<Point>();
            int r = row;
            int c = col;
            for (int step = 0; step <= MaxBridgeConnectorLength; ++step)
            {
                if (!grid.InBounds(r, c) || grid.At(r, c).isWater)
                {
                    return;
                }

                path.Add(new Point(r, c));
                if (grid.At(r, c).IsRoad && step > 0)
                {
                    for (int i = 0; i < path.Count; ++i)
                    {
                        SetRoad(path[i].r, path[i].c, RoadCategory.Connector);
                    }
                    return;
                }

                r += dr;
                c += dc;
            }

            for (int i = 0; i < Math.Min(path.Count, 3); ++i)
            {
                SetRoad(path[i].r, path[i].c, RoadCategory.Connector);
            }
        }

        private void GenerateRoadAnnotations()
        {
            for (int r = 0; r < grid.Height; ++r)
            {
                for (int c = 0; c < grid.Width; ++c)
                {
                    MapCell cell = grid.At(r, c);
                    cell.isRoadTurn = false;
                    cell.isIntersection = false;

                    if (!cell.IsRoad)
                    {
                        continue;
                    }

                    int bitmask = grid.RoadBitmask(r, c);
                    int connections = 0;
                    for (int bit = 0; bit < 4; ++bit)
                    {
                        connections += (bitmask >> bit) & 1;
                    }

                    cell.isIntersection = connections >= 3;
                    cell.isRoadTurn = connections == 2 && bitmask != 10 && bitmask != 5;
                }
            }
        }

        private void GenerateElevation()
        {
            for (int r = 0; r < grid.Height; ++r)
            {
                for (int c = 0; c < grid.Width; ++c)
                {
                    MapCell cell = grid.At(r, c);
                    cell.elevation = cell.isWater
                        ? 0.0
                        : Clamp01(Fbm(c / 50.0, r / 50.0, config.masterSeed ^ SaltElevation, 3));
                }
            }
        }

        private void GenerateZones()
        {
            ProfileRules rules = RulesForProfile(config.cityProfile, config);
            int rows = grid.Height;
            int cols = grid.Width;
            double centerR = rows / 2.0;
            double centerC = cols / 2.0;
            if (resolvedCoastSide == CoastSide.West) centerC = cols * 0.60;
            if (resolvedCoastSide == CoastSide.East) centerC = cols * 0.40;
            if (resolvedCoastSide == CoastSide.North) centerR = rows * 0.60;
            if (resolvedCoastSide == CoastSide.South) centerR = rows * 0.40;

            double offsetR = (Decision01(config.masterSeed, 77, 99, SaltElevation) - 0.5) * 0.10 * rows;
            double offsetC = (Decision01(config.masterSeed, 88, 77, SaltElevation) - 0.5) * 0.10 * cols;
            centerR = ClampDouble(centerR + offsetR, rows * 0.20, rows * 0.80);
            centerC = ClampDouble(centerC + offsetC, cols * 0.20, cols * 0.80);
            cbdCenterR = centerR;
            cbdCenterC = centerC;

            double cbdR = rules.cbdRadius;
            double midR = rules.midtownRadius;

            for (int r = 0; r < rows; ++r)
            {
                for (int c = 0; c < cols; ++c)
                {
                    MapCell cell = grid.At(r, c);
                    if (!cell.isLand)
                    {
                        continue;
                    }

                    double dr = Math.Abs(r - centerR) / (rows / 2.0);
                    double dc = Math.Abs(c - centerC) / (cols / 2.0);
                    double dist = Hypot(dr, dc);
                    cell.zoneId = dist < cbdR ? ZoneId.CBD : (dist < midR ? ZoneId.Midtown : ZoneId.Residential);

                    double transition = Decision01(config.masterSeed, r, c, SaltElevation);
                    if (dist >= cbdR - 0.04 && dist < cbdR + 0.08 && transition < 0.40)
                    {
                        cell.zoneId = ZoneId.Midtown;
                    }
                    else if (dist >= midR - 0.04 && dist < midR + 0.08 && transition < 0.35)
                    {
                        cell.zoneId = ZoneId.Residential;
                    }
                }
            }
        }

        private void GenerateCivicAnchor()
        {
            int[,] waterDist = BfsWaterDistance(grid);
            double bestScore = -1.0;
            Point best = new Point(-1, -1);

            for (int r = 0; r < grid.Height; ++r)
            {
                for (int c = 0; c < grid.Width; ++c)
                {
                    MapCell cell = grid.At(r, c);
                    if (!cell.isLand || cell.isWater || cell.IsRoad || cell.zoneId != ZoneId.CBD || cell.blockId < 0)
                    {
                        continue;
                    }

                    int wd = waterDist[r, c] == int.MaxValue ? 999 : waterDist[r, c];
                    double centerScore = -Hypot(r - cbdCenterR, c - cbdCenterC);
                    double score = wd * 4.0 + centerScore;
                    if (score > bestScore)
                    {
                        bestScore = score;
                        best = new Point(r, c);
                    }
                }
            }

            if (best.r >= 0)
            {
                civicAnchor = best;
                MapCell cell = grid.At(best.r, best.c);
                cell.isCivicAnchor = true;
                cell.tileRole = "civic_anchor";
            }
        }

        private bool CanPlaceRoad(int row, int col)
        {
            return grid.InBounds(row, col) && grid.At(row, col).isLand && !grid.At(row, col).isWater;
        }

        private void SetRoad(int row, int col, RoadCategory category)
        {
            if (CanPlaceRoad(row, col))
            {
                grid.At(row, col).roadCategory = category;
            }
        }

        private void GenerateHighways()
        {
            const double Pi = 3.14159265358979323846;
            ProfileRules rules = RulesForProfile(config.cityProfile, config);
            int rows = grid.Height;
            int cols = grid.Width;

            archetype = (int)(MixU32(config.masterSeed ^ 0x3A7F9B2Cu) % 3u);

            Func<int, int, List<Point>> routeNs = delegate(int targetC, int iSalt)
            {
                List<Point> path = new List<Point>(rows);
                int curC = targetC;
                for (int r = 0; r < rows; ++r)
                {
                    double bestCost = 1e18;
                    int bestC = ClampInt(curC, 0, cols - 1);
                    for (int dc = -5; dc <= 5; ++dc)
                    {
                        int cand = ClampInt(curC + dc, 0, cols - 1);
                        if (grid.At(r, cand).isWater)
                        {
                            continue;
                        }

                        double elevCost = grid.At(r, cand).elevation * 4.0;
                        double lateral = Math.Abs(dc) * 0.25;
                        double driftPen = Math.Abs(cand - targetC) * 0.04;
                        double fbmBonus = -(Fbm(r / 20.0, iSalt, config.masterSeed ^ SaltHighway, 4) - 0.5) *
                                          rules.highwayOrganic * 1.5;
                        double cost = elevCost + lateral + driftPen + fbmBonus;
                        if (cost < bestCost)
                        {
                            bestCost = cost;
                            bestC = cand;
                        }
                    }

                    path.Add(new Point(r, bestC));
                    curC = bestC;
                }

                return path;
            };

            Func<int, int, List<Point>> routeEw = delegate(int targetR, int iSalt)
            {
                List<Point> path = new List<Point>(cols);
                int curR = targetR;
                for (int c = 0; c < cols; ++c)
                {
                    double bestCost = 1e18;
                    int bestR = ClampInt(curR, 0, rows - 1);
                    for (int dr = -5; dr <= 5; ++dr)
                    {
                        int cand = ClampInt(curR + dr, 0, rows - 1);
                        if (grid.At(cand, c).isWater)
                        {
                            continue;
                        }

                        double elevCost = grid.At(cand, c).elevation * 4.0;
                        double lateral = Math.Abs(dr) * 0.25;
                        double driftPen = Math.Abs(cand - targetR) * 0.04;
                        double fbmBonus = -(Fbm(c / 20.0, iSalt + 99, config.masterSeed ^ SaltHighway, 4) - 0.5) *
                                          rules.highwayOrganic * 1.5;
                        double cost = elevCost + lateral + driftPen + fbmBonus;
                        if (cost < bestCost)
                        {
                            bestCost = cost;
                            bestR = cand;
                        }
                    }

                    path.Add(new Point(bestR, c));
                    curR = bestR;
                }

                return path;
            };

            Action<List<Point>, RoadCategory> drawPath = delegate(List<Point> path, RoadCategory category)
            {
                int prevR = -1;
                int prevC = -1;
                for (int i = 0; i < path.Count; ++i)
                {
                    Point p = path[i];
                    SetRoad(p.r, p.c, category);
                    if (prevR >= 0 && p.r != prevR && p.c != prevC)
                    {
                        SetRoad(p.r, prevC, category);
                    }

                    prevR = p.r;
                    prevC = p.c;
                }
            };

            if (archetype == 1)
            {
                int numRadial = 4 + (int)(MixU32(config.masterSeed ^ 0xF1E2D3C4u) % 3u);
                for (int i = 0; i < numRadial; ++i)
                {
                    double baseAngle = Pi * 2.0 * i / numRadial;
                    double angleNoise = (Decision01(config.masterSeed, i, 7, SaltHighway) - 0.5) * 0.4;
                    double angle = baseAngle + angleNoise;
                    double stepR = Math.Sin(angle);
                    double stepC = Math.Cos(angle);
                    double curR = cbdCenterR;
                    double curC = cbdCenterC;
                    int prevGr = -1;
                    int prevGc = -1;

                    while (true)
                    {
                        int gr = RoundToInt(curR);
                        int gc = RoundToInt(curC);
                        if (!grid.InBounds(gr, gc))
                        {
                            break;
                        }

                        if (!grid.At(gr, gc).isWater)
                        {
                            SetRoad(gr, gc, RoadCategory.Highway);
                        }

                        if (prevGr >= 0 && Math.Abs(gr - prevGr) + Math.Abs(gc - prevGc) > 1)
                        {
                            if (grid.InBounds(gr, prevGc) && !grid.At(gr, prevGc).isWater)
                            {
                                SetRoad(gr, prevGc, RoadCategory.Highway);
                            }
                        }

                        prevGr = gr;
                        prevGc = gc;
                        curR += stepR;
                        curC += stepC;
                    }
                }

                GenerateRingRoad();
            }
            else
            {
                int nsCount = DecisionRange(config.masterSeed, 3, 5, SaltHighway, config.highwayNsMin, config.highwayNsMax);
                int ewCount = DecisionRange(config.masterSeed, 7, 11, SaltHighway, config.highwayEwMin, config.highwayEwMax);

                for (int i = 0; i < nsCount; ++i)
                {
                    drawPath(routeNs((i + 1) * cols / (nsCount + 1), i), RoadCategory.Highway);
                }

                for (int i = 0; i < ewCount; ++i)
                {
                    drawPath(routeEw((i + 1) * rows / (ewCount + 1), i), RoadCategory.Highway);
                }

                if (archetype == 2)
                {
                    int diagStartC = cols / 4;
                    int diagEndC = cols * 3 / 4;
                    int prevC = diagStartC;
                    for (int r = 0; r < rows; ++r)
                    {
                        double t = (double)r / Math.Max(rows - 1, 1);
                        int tgt = RoundToInt(diagStartC + t * (diagEndC - diagStartC));
                        int bestC = tgt;
                        double bestElev = 1e18;
                        for (int dc = -3; dc <= 3; ++dc)
                        {
                            int cand = ClampInt(tgt + dc, 0, cols - 1);
                            if (!grid.At(r, cand).isWater && grid.At(r, cand).elevation < bestElev)
                            {
                                bestElev = grid.At(r, cand).elevation;
                                bestC = cand;
                            }
                        }

                        if (!grid.At(r, bestC).IsRoad)
                        {
                            SetRoad(r, bestC, RoadCategory.Highway);
                        }

                        if (bestC != prevC)
                        {
                            SetRoad(r, prevC, RoadCategory.Highway);
                        }

                        prevC = bestC;
                    }
                }
            }

            if (config.roundaboutCount > 0)
            {
                int placed = 0;
                for (int r = 2; r < rows - 2 && placed < config.roundaboutCount; ++r)
                {
                    for (int c = 2; c < cols - 2 && placed < config.roundaboutCount; ++c)
                    {
                        if (grid.At(r, c).roadCategory != RoadCategory.Highway)
                        {
                            continue;
                        }

                        int hwNb = 0;
                        List<Point> neighbours = Neighbours4(r, c);
                        for (int i = 0; i < neighbours.Count; ++i)
                        {
                            Point n = neighbours[i];
                            if (grid.InBounds(n.r, n.c) &&
                                grid.At(n.r, n.c).roadCategory == RoadCategory.Highway)
                            {
                                ++hwNb;
                            }
                        }

                        if (hwNb >= 3)
                        {
                            Point[] ring =
                            {
                                new Point(r - 1, c - 1), new Point(r - 1, c), new Point(r - 1, c + 1),
                                new Point(r, c - 1), new Point(r, c + 1),
                                new Point(r + 1, c - 1), new Point(r + 1, c), new Point(r + 1, c + 1)
                            };

                            for (int i = 0; i < ring.Length; ++i)
                            {
                                Point n = ring[i];
                                if (grid.InBounds(n.r, n.c) && !grid.At(n.r, n.c).isWater &&
                                    grid.At(n.r, n.c).roadCategory == RoadCategory.None)
                                {
                                    SetRoad(n.r, n.c, RoadCategory.Connector);
                                }
                            }

                            ++placed;
                        }
                    }
                }
            }

            ApplyBoundaryHighways();
        }

        private void ApplyBoundaryHighways()
        {
            if (config.forceWestHighway)
            {
                for (int r = 0; r < grid.Height; ++r)
                {
                    SetRoad(r, 0, RoadCategory.Highway);
                }
            }

            if (config.forceEastHighway)
            {
                int col = grid.Width - 1;
                for (int r = 0; r < grid.Height; ++r)
                {
                    SetRoad(r, col, RoadCategory.Highway);
                }
            }

            if (config.forceNorthHighway)
            {
                for (int c = 0; c < grid.Width; ++c)
                {
                    SetRoad(0, c, RoadCategory.Highway);
                }
            }

            if (config.forceSouthHighway)
            {
                int row = grid.Height - 1;
                for (int c = 0; c < grid.Width; ++c)
                {
                    SetRoad(row, c, RoadCategory.Highway);
                }
            }
        }

        private void GenerateRingRoad()
        {
            const double Pi = 3.14159265358979323846;
            int rows = grid.Height;
            int cols = grid.Width;
            int radius = RoundToInt(Math.Min(rows, cols) * 0.28);
            if (radius < 4)
            {
                return;
            }

            int steps = (int)(2.0 * Pi * radius * 2.5);
            int prevR = -1;
            int prevC = -1;
            for (int step = 0; step <= steps; ++step)
            {
                double theta = 2.0 * Pi * step / steps;
                int r = RoundToInt(cbdCenterR + radius * Math.Sin(theta));
                int c = RoundToInt(cbdCenterC + radius * Math.Cos(theta));
                if (!grid.InBounds(r, c) || grid.At(r, c).isWater)
                {
                    prevR = r;
                    prevC = c;
                    continue;
                }

                if (!grid.At(r, c).IsRoad)
                {
                    SetRoad(r, c, RoadCategory.Connector);
                }

                if (prevR >= 0 && grid.InBounds(prevR, prevC))
                {
                    if (Math.Abs(r - prevR) + Math.Abs(c - prevC) > 1)
                    {
                        if (grid.InBounds(r, prevC) && !grid.At(r, prevC).isWater && !grid.At(r, prevC).IsRoad)
                        {
                            SetRoad(r, prevC, RoadCategory.Connector);
                        }
                        else if (grid.InBounds(prevR, c) && !grid.At(prevR, c).isWater && !grid.At(prevR, c).IsRoad)
                        {
                            SetRoad(prevR, c, RoadCategory.Connector);
                        }
                    }
                }

                prevR = r;
                prevC = c;
            }
        }

        private void GenerateConnectors()
        {
            ProfileRules rules = RulesForProfile(config.cityProfile, config);

            for (int c = rules.avenueSpacing; c < grid.Width; c += rules.avenueSpacing)
            {
                if (Decision01(config.masterSeed, c, 17, SaltConnector) > rules.connectorDensity)
                {
                    continue;
                }

                int maxDrift = RoundToInt(rules.connectorOrganic * (grid.Width / 12.0));
                int prevCol = c;
                double prevNoiseValV = 0.5;
                for (int r = 0; r < grid.Height; ++r)
                {
                    double noiseVal = Fbm(r / 28.0, (double)c / Math.Max(grid.Width, 1) * 8.0,
                        config.masterSeed ^ SaltConnector ^ 0xC0D1u, 3);
                    int rawDrift = RoundToInt((noiseVal - 0.5) * 2.0 * maxDrift);
                    int amplifiedDrift = rawDrift;
                    if (config.connectorTurnBias > 0.0)
                    {
                        double prevC2 = prevNoiseValV - 0.5;
                        double currC2 = noiseVal - 0.5;
                        if (prevC2 * currC2 < 0.0)
                        {
                            double biasMult = 1.0 + config.connectorTurnBias * 3.0;
                            amplifiedDrift = RoundToInt(rawDrift * biasMult);
                        }
                    }

                    prevNoiseValV = noiseVal;
                    int drift = ClampInt(amplifiedDrift, -maxDrift, maxDrift);
                    int col = ClampInt(c + drift, 0, grid.Width - 1);
                    if (col != prevCol && r > 0)
                    {
                        SetRoad(r, prevCol, RoadCategory.Connector);
                    }

                    if (!grid.At(r, col).IsRoad)
                    {
                        SetRoad(r, col, RoadCategory.Connector);
                    }

                    prevCol = col;
                }
            }

            for (int r = rules.connectorSpacing; r < grid.Height; r += rules.connectorSpacing)
            {
                if (Decision01(config.masterSeed, 23, r, SaltConnector) > rules.connectorDensity)
                {
                    continue;
                }

                int maxDrift = RoundToInt(rules.connectorOrganic * (grid.Height / 12.0));
                int prevRow = r;
                double prevNoiseValH = 0.5;
                for (int c = 0; c < grid.Width; ++c)
                {
                    double noiseVal = Fbm(c / 28.0, (double)r / Math.Max(grid.Height, 1) * 8.0,
                        config.masterSeed ^ SaltConnector ^ 0xC0D2u, 3);
                    int rawDrift = RoundToInt((noiseVal - 0.5) * 2.0 * maxDrift);
                    int amplifiedDrift = rawDrift;
                    if (config.connectorTurnBias > 0.0)
                    {
                        double prevH2 = prevNoiseValH - 0.5;
                        double currH2 = noiseVal - 0.5;
                        if (prevH2 * currH2 < 0.0)
                        {
                            double biasMult = 1.0 + config.connectorTurnBias * 3.0;
                            amplifiedDrift = RoundToInt(rawDrift * biasMult);
                        }
                    }

                    prevNoiseValH = noiseVal;
                    int drift = ClampInt(amplifiedDrift, -maxDrift, maxDrift);
                    int row = ClampInt(r + drift, 0, grid.Height - 1);
                    if (row != prevRow && c > 0)
                    {
                        SetRoad(prevRow, c, RoadCategory.Connector);
                    }

                    if (!grid.At(row, c).IsRoad)
                    {
                        SetRoad(row, c, RoadCategory.Connector);
                    }

                    prevRow = row;
                }
            }

            if (rules.diagonalStreets > 0)
            {
                int centerR = grid.Height / 2;
                int centerC = grid.Width / 2;

                if (config.cityProfile == "paris_haussmann")
                {
                    Point[] dirs =
                    {
                        new Point(-1, -1), new Point(-1, 1),
                        new Point(1, -1), new Point(1, 1)
                    };
                    int diagCount = Math.Min(4, rules.diagonalStreets);
                    for (int d = 0; d < diagCount; ++d)
                    {
                        int r = centerR;
                        int c = centerC;
                        int dr = dirs[d].r;
                        int dc = dirs[d].c;
                        while (grid.InBounds(r, c))
                        {
                            if (!grid.At(r, c).IsRoad)
                            {
                                SetRoad(r, c, RoadCategory.Connector);
                            }

                            int nextR = r + dr;
                            if (grid.InBounds(nextR, c) && !grid.At(nextR, c).IsRoad)
                            {
                                SetRoad(nextR, c, RoadCategory.Connector);
                            }

                            r = nextR;
                            c += dc;
                        }
                    }
                }
                else if (config.cityProfile == "manhattan")
                {
                    int r = 0;
                    int c = grid.Width * 2 / 5;
                    while (r < grid.Height - 1)
                    {
                        if (grid.InBounds(r, c) && !grid.At(r, c).IsRoad)
                        {
                            SetRoad(r, c, RoadCategory.Connector);
                        }

                        int nextR = r + 1;
                        if (grid.InBounds(nextR, c) && !grid.At(nextR, c).IsRoad)
                        {
                            SetRoad(nextR, c, RoadCategory.Connector);
                        }

                        r = nextR;
                        if (r % 8 == 0 && c + 1 < grid.Width - 1)
                        {
                            ++c;
                        }
                    }
                }
                else
                {
                    for (int d = 0; d < rules.diagonalStreets; ++d)
                    {
                        int r = Math.Max(1, grid.Height / 8 + d * 5);
                        int c = Math.Max(1, grid.Width / 8 + d * 7);
                        while (r < grid.Height - 1 && c < grid.Width - 1)
                        {
                            if (!grid.At(r, c).IsRoad)
                            {
                                SetRoad(r, c, RoadCategory.Connector);
                            }

                            if ((r + c + d) % 2 == 0)
                            {
                                ++r;
                            }
                            else
                            {
                                ++c;
                            }
                        }
                    }
                }
            }

            bool removedIsolated = true;
            while (removedIsolated)
            {
                List<Point> isolated = new List<Point>();
                for (int r = 0; r < grid.Height; ++r)
                {
                    for (int c = 0; c < grid.Width; ++c)
                    {
                        if (!grid.At(r, c).IsRoad)
                        {
                            continue;
                        }

                        bool connected = false;
                        List<Point> neighbours = Neighbours4(r, c);
                        for (int i = 0; i < neighbours.Count; ++i)
                        {
                            Point n = neighbours[i];
                            if (grid.InBounds(n.r, n.c) && grid.At(n.r, n.c).IsRoad)
                            {
                                connected = true;
                                break;
                            }
                        }

                        if (!connected)
                        {
                            isolated.Add(new Point(r, c));
                        }
                    }
                }

                removedIsolated = isolated.Count > 0;
                for (int i = 0; i < isolated.Count; ++i)
                {
                    Point p = isolated[i];
                    grid.At(p.r, p.c).roadCategory = RoadCategory.None;
                }
            }
        }

        private void GenerateSidewalks()
        {
            List<Point> sidewalks = new List<Point>();
            for (int r = 0; r < grid.Height; ++r)
            {
                for (int c = 0; c < grid.Width; ++c)
                {
                    MapCell cell = grid.At(r, c);
                    if (!cell.isLand || cell.IsRoad)
                    {
                        continue;
                    }

                    List<Point> neighbours = Neighbours4(r, c);
                    for (int i = 0; i < neighbours.Count; ++i)
                    {
                        Point n = neighbours[i];
                        if (grid.InBounds(n.r, n.c) && grid.At(n.r, n.c).roadCategory == RoadCategory.Connector)
                        {
                            sidewalks.Add(new Point(r, c));
                            break;
                        }
                    }
                }
            }

            for (int i = 0; i < sidewalks.Count; ++i)
            {
                Point p = sidewalks[i];
                MapCell cell = grid.At(p.r, p.c);
                cell.tileRole = "sidewalk";
                if (Decision01(config.masterSeed, p.r, p.c, SaltConnector ^ 0xDAu) < config.sidewalkDamageRate)
                {
                    cell.isDamaged = true;
                }
            }
        }

        private void GenerateBlocks()
        {
            int rows = grid.Height;
            int cols = grid.Width;
            bool[,] visited = new bool[rows, cols];
            int blockId = 0;

            for (int sr = 0; sr < rows; ++sr)
            {
                for (int sc = 0; sc < cols; ++sc)
                {
                    if (visited[sr, sc] || grid.At(sr, sc).IsRoad || grid.At(sr, sc).isWater)
                    {
                        visited[sr, sc] = true;
                        continue;
                    }

                    Queue<Point> q = new Queue<Point>();
                    SortedSet<Point> region = new SortedSet<Point>();
                    bool edge = false;
                    q.Enqueue(new Point(sr, sc));
                    visited[sr, sc] = true;

                    while (q.Count > 0)
                    {
                        Point p = q.Dequeue();
                        region.Add(p);
                        if (p.r == 0 || p.c == 0 || p.r == rows - 1 || p.c == cols - 1)
                        {
                            edge = true;
                        }

                        List<Point> neighbours = Neighbours4(p.r, p.c);
                        for (int i = 0; i < neighbours.Count; ++i)
                        {
                            Point n = neighbours[i];
                            if (grid.InBounds(n.r, n.c) && !visited[n.r, n.c] &&
                                !grid.At(n.r, n.c).IsRoad && !grid.At(n.r, n.c).isWater)
                            {
                                visited[n.r, n.c] = true;
                                q.Enqueue(n);
                            }
                        }
                    }

                    int r0 = rows;
                    int c0 = cols;
                    int r1 = 0;
                    int c1 = 0;
                    foreach (Point p in region)
                    {
                        r0 = Math.Min(r0, p.r);
                        r1 = Math.Max(r1, p.r);
                        c0 = Math.Min(c0, p.c);
                        c1 = Math.Max(c1, p.c);
                    }

                    int depth = Math.Min(r1 - r0 + 1, c1 - c0 + 1);
                    bool tooSmall = region.Count < Math.Max(4, config.minBlockDepth * 2) ||
                                    depth < Math.Max(1, config.minBlockDepth);

                    if (edge || tooSmall)
                    {
                        foreach (Point p in region)
                        {
                            grid.At(p.r, p.c).blockId = -1;
                        }
                    }
                    else
                    {
                        foreach (Point p in region)
                        {
                            grid.At(p.r, p.c).blockId = blockId;
                        }

                        blocks.Add(region);
                        ++blockId;
                    }
                }
            }

            for (int i = 0; i < blocks.Count; ++i)
            {
                foreach (Point p in blocks[i])
                {
                    MapCell cell = grid.At(p.r, p.c);
                    List<Point> neighbours = Neighbours4(p.r, p.c);
                    for (int n = 0; n < neighbours.Count; ++n)
                    {
                        Point nbPoint = neighbours[n];
                        if (!grid.InBounds(nbPoint.r, nbPoint.c))
                        {
                            continue;
                        }

                        MapCell nb = grid.At(nbPoint.r, nbPoint.c);
                        if (!nb.IsRoad)
                        {
                            continue;
                        }

                        if (nb.roadCategory == RoadCategory.Highway)
                        {
                            cell.streetFacing = "highway";
                            break;
                        }

                        if (nb.roadCategory == RoadCategory.Connector && string.IsNullOrEmpty(cell.streetFacing))
                        {
                            cell.streetFacing = "connector";
                        }
                    }
                }
            }
        }

        private void GenerateParks()
        {
            ProfileRules rules = RulesForProfile(config.cityProfile, config);
            List<int> candidates = new List<int>(blocks.Count);
            for (int i = 0; i < blocks.Count; ++i)
            {
                SortedSet<Point> block = blocks[i];
                bool containsCivic = false;
                foreach (Point p in block)
                {
                    if (grid.At(p.r, p.c).isCivicAnchor)
                    {
                        containsCivic = true;
                        break;
                    }
                }

                if (!containsCivic && block.Count >= rules.parkMinArea && block.Count <= rules.parkMaxArea)
                {
                    candidates.Add(i);
                }
            }

            candidates.Sort(delegate(int a, int b)
            {
                uint ha = DecisionHash(config.masterSeed, a, blocks[a].Count, SaltParks);
                uint hb = DecisionHash(config.masterSeed, b, blocks[b].Count, SaltParks);
                int cmp = ha.CompareTo(hb);
                return cmp != 0 ? cmp : a.CompareTo(b);
            });

            int landCells = grid.LandCount();
            int target = Math.Max(1, landCells / 500);
            for (int i = 0; i < target && i < candidates.Count; ++i)
            {
                SortedSet<Point> block = blocks[candidates[i]];
                foreach (Point p in block)
                {
                    MapCell cell = grid.At(p.r, p.c);
                    cell.isPark = true;
                    cell.tileRole = "park";
                }
            }

            int pocketBudget = Math.Max(1, landCells / 800);
            for (int i = 0; i < blocks.Count && pocketBudget > 0; ++i)
            {
                SortedSet<Point> block = blocks[i];
                if (block.Count < 4 || block.Count > 8)
                {
                    continue;
                }

                bool containsCivic = false;
                bool alreadyPark = false;
                bool nonCbd = true;
                foreach (Point p in block)
                {
                    MapCell cell = grid.At(p.r, p.c);
                    containsCivic = containsCivic || cell.isCivicAnchor;
                    alreadyPark = alreadyPark || cell.isPark;
                    nonCbd = nonCbd && cell.zoneId != ZoneId.CBD;
                }

                if (containsCivic || alreadyPark || !nonCbd)
                {
                    continue;
                }

                foreach (Point p in block)
                {
                    MapCell cell = grid.At(p.r, p.c);
                    cell.isPark = true;
                    cell.tileRole = "park";
                }

                --pocketBudget;
            }
        }

        private void GenerateLots()
        {
            int lotId = 0;

            Func<SortedSet<Point>, List<SortedSet<Point>>> components = delegate(SortedSet<Point> region)
            {
                List<SortedSet<Point>> result = new List<SortedSet<Point>>();
                SortedSet<Point> remaining = new SortedSet<Point>(region);
                while (remaining.Count > 0)
                {
                    SortedSet<Point> component = new SortedSet<Point>();
                    Queue<Point> q = new Queue<Point>();
                    Point start = FirstPoint(remaining);
                    q.Enqueue(start);
                    remaining.Remove(start);

                    while (q.Count > 0)
                    {
                        Point p = q.Dequeue();
                        component.Add(p);
                        List<Point> neighbours = Neighbours4(p.r, p.c);
                        for (int i = 0; i < neighbours.Count; ++i)
                        {
                            Point n = neighbours[i];
                            if (remaining.Contains(n))
                            {
                                q.Enqueue(n);
                                remaining.Remove(n);
                            }
                        }
                    }

                    result.Add(component);
                }

                return result;
            };

            Action<SortedSet<Point>> subdivide = null;
            subdivide = delegate(SortedSet<Point> region)
            {
                if (region.Count < 4)
                {
                    return;
                }

                if (region.Count < 12)
                {
                    foreach (Point p in region)
                    {
                        grid.At(p.r, p.c).lotId = lotId;
                    }

                    lots.Add(new SortedSet<Point>(region));
                    ++lotId;
                    return;
                }

                int r0 = grid.Height;
                int c0 = grid.Width;
                int r1 = 0;
                int c1 = 0;
                foreach (Point p in region)
                {
                    r0 = Math.Min(r0, p.r);
                    r1 = Math.Max(r1, p.r);
                    c0 = Math.Min(c0, p.c);
                    c1 = Math.Max(c1, p.c);
                }

                bool splitByCol = (c1 - c0) >= (r1 - r0);
                int midpoint = splitByCol ? (c0 + c1) / 2 : (r0 + r1) / 2;
                SortedSet<Point> left = new SortedSet<Point>();
                SortedSet<Point> right = new SortedSet<Point>();

                foreach (Point p in region)
                {
                    if ((splitByCol ? p.c : p.r) <= midpoint)
                    {
                        left.Add(p);
                    }
                    else
                    {
                        right.Add(p);
                    }
                }

                List<SortedSet<Point>> leftPieces = components(left);
                for (int i = 0; i < leftPieces.Count; ++i)
                {
                    subdivide(leftPieces[i]);
                }

                List<SortedSet<Point>> rightPieces = components(right);
                for (int i = 0; i < rightPieces.Count; ++i)
                {
                    subdivide(rightPieces[i]);
                }
            };

            for (int i = 0; i < blocks.Count; ++i)
            {
                SortedSet<Point> block = blocks[i];
                if (block.Count == 0)
                {
                    continue;
                }

                bool isPark = false;
                foreach (Point p in block)
                {
                    if (grid.At(p.r, p.c).isPark)
                    {
                        isPark = true;
                        break;
                    }
                }

                if (isPark)
                {
                    continue;
                }

                subdivide(block);
            }
        }

        private void ComputeDensity()
        {
            for (int r = 0; r < grid.Height; ++r)
            {
                for (int c = 0; c < grid.Width; ++c)
                {
                    MapCell cell = grid.At(r, c);
                    if (!cell.isLand)
                    {
                        continue;
                    }

                    cell.densityScore = cell.zoneId == ZoneId.CBD ? 0.85 :
                        (cell.zoneId == ZoneId.Midtown ? 0.55 : 0.25);
                }
            }
        }

        private void GenerateBuildings()
        {
            for (int r = 0; r < grid.Height; ++r)
            {
                for (int c = 0; c < grid.Width; ++c)
                {
                    MapCell cell = grid.At(r, c);
                    if (cell.isWater)
                    {
                        cell.tileRole = "water";
                    }
                    else if (cell.IsRoad)
                    {
                        cell.tileRole = cell.roadCategory == RoadCategory.Highway ? "highway" : "road";
                        cell.encounterChance = cell.roadCategory == RoadCategory.Highway ? 0.02 : 0.10;
                    }
                    else if (cell.isPark)
                    {
                        cell.tileRole = "park";
                        cell.isSpawnPoint = true;
                        cell.encounterChance = 0.04;
                    }
                    else if (cell.tileRole == "sidewalk")
                    {
                        cell.encounterChance = 0.08;
                    }
                    else if (cell.lotId >= 0)
                    {
                        cell.tileRole = "lot";
                    }
                    else
                    {
                        cell.tileRole = "exterior";
                    }
                }
            }

            Dictionary<int, string> landmarkByLot = new Dictionary<int, string>();
            if (civicAnchor.r >= 0 && grid.InBounds(civicAnchor.r, civicAnchor.c))
            {
                int civicLot = grid.At(civicAnchor.r, civicAnchor.c).lotId;
                if (civicLot >= 0)
                {
                    landmarkByLot[civicLot] = "town_hall";
                }
            }

            List<int> candidateLots = new List<int>(lots.Count);
            for (int i = 0; i < lots.Count; ++i)
            {
                SortedSet<Point> buildable = new SortedSet<Point>();
                foreach (Point p in lots[i])
                {
                    MapCell cell = grid.At(p.r, p.c);
                    if (cell.tileRole != "sidewalk" && !cell.IsRoad && !cell.isWater && !cell.isPark)
                    {
                        buildable.Add(p);
                    }
                }

                if (buildable.Count < 6)
                {
                    continue;
                }

                Point anchor = RepresentativePoint(buildable);
                int lotId = grid.At(anchor.r, anchor.c).lotId;
                if (!landmarkByLot.ContainsKey(lotId))
                {
                    candidateLots.Add(i);
                }
            }

            candidateLots.Sort(delegate(int a, int b)
            {
                SortedSet<Point> lotA = lots[a];
                SortedSet<Point> lotB = lots[b];
                Point pa = RepresentativePoint(lotA);
                Point pb = RepresentativePoint(lotB);
                uint ha = DecisionHash(config.masterSeed, grid.At(pa.r, pa.c).lotId, lotA.Count, SaltBuildings);
                uint hb = DecisionHash(config.masterSeed, grid.At(pb.r, pb.c).lotId, lotB.Count, SaltBuildings);
                int cmp = ha.CompareTo(hb);
                return cmp != 0 ? cmp : a.CompareTo(b);
            });

            string[] civicLandmarks = { "station", "hospital", "police", "school" };
            for (int i = 0; i < civicLandmarks.Length && i < candidateLots.Count; ++i)
            {
                Point anchor = RepresentativePoint(lots[candidateLots[i]]);
                landmarkByLot[grid.At(anchor.r, anchor.c).lotId] = civicLandmarks[i];
            }

            int buildingId = 0;
            for (int i = 0; i < lots.Count; ++i)
            {
                SortedSet<Point> lot = lots[i];
                if (lot.Count == 0)
                {
                    continue;
                }

                SortedSet<Point> buildable = new SortedSet<Point>();
                foreach (Point p in lot)
                {
                    MapCell cell = grid.At(p.r, p.c);
                    if (cell.tileRole != "sidewalk" && !cell.IsRoad && !cell.isWater && !cell.isPark)
                    {
                        buildable.Add(p);
                    }
                }

                if (buildable.Count == 0)
                {
                    continue;
                }

                Point lotAnchor = RepresentativePoint(buildable);
                int lotId = grid.At(lotAnchor.r, lotAnchor.c).lotId;
                if (lotId < 0)
                {
                    continue;
                }

                Bounds bounds = BoundsFor(buildable);
                ZoneId zone = DominantZone(buildable, grid);
                bool waterfront = TouchesWaterfront(buildable, grid);
                string landmarkType = landmarkByLot.ContainsKey(lotId) ? landmarkByLot[lotId] : "";
                double roll = Decision01(config.masterSeed, lotId, buildable.Count, SaltBuildings);

                string buildingType;
                if (landmarkType == "town_hall")
                {
                    buildingType = "civic";
                }
                else if (!string.IsNullOrEmpty(landmarkType))
                {
                    buildingType = landmarkType;
                }
                else
                {
                    buildingType = PickBuildingType(zone, roll, waterfront, grid.At(lotAnchor.r, lotAnchor.c).elevation);
                }

                if (buildingType == "empty")
                {
                    foreach (Point p in buildable)
                    {
                        MapCell cell = grid.At(p.r, p.c);
                        cell.tileRole = "exterior";
                        cell.buildingType = "";
                        cell.landmarkType = "";
                    }

                    continue;
                }

                bool usesSetback = zone == ZoneId.Residential &&
                                   buildable.Count >= 9 &&
                                   string.IsNullOrEmpty(landmarkType) &&
                                   buildingType != "apartment";
                SortedSet<Point> footprint = new SortedSet<Point>();
                foreach (Point p in buildable)
                {
                    bool perimeter = p.r == bounds.r0 || p.r == bounds.r1 || p.c == bounds.c0 || p.c == bounds.c1;
                    MapCell cell = grid.At(p.r, p.c);
                    if (usesSetback && perimeter)
                    {
                        cell.isSetback = true;
                        cell.tileRole = "setback";
                        cell.encounterChance = 0.28;
                        continue;
                    }

                    footprint.Add(p);
                }

                if (footprint.Count == 0)
                {
                    footprint.Add(lotAnchor);
                    grid.At(lotAnchor.r, lotAnchor.c).isSetback = false;
                }

                Bounds footprintBounds = BoundsFor(footprint);
                Point anchor = RepresentativePoint(footprint);
                int floors = FloorCountFor(zone, buildingType, config.masterSeed, lotId,
                    grid.At(lotAnchor.r, lotAnchor.c).elevation);
                string profileId = ProfileFor(config.cityProfile).id;
                string footprintStyle = FootprintStyleFor(profileId, zone, buildingType, footprintBounds);
                string roofType = string.IsNullOrEmpty(landmarkType) ? RoofFor(profileId, buildingType, floors) : "";
                string facade = FacadeFamilyFor(profileId, buildingType);
                string tileRole = TileRoleForBuilding(zone, buildingType, landmarkType);
                string assetSlot = AssetSlotForBuildingRecord(buildingType, landmarkType);

                double encounter = 0.06;
                if (buildingType == "market" || buildingType == "restaurant" || buildingType == "shop")
                {
                    encounter = 0.18;
                }
                else if (tileRole == "bldg_civic")
                {
                    encounter = 0.14;
                }
                else if (zone == ZoneId.CBD)
                {
                    encounter = 0.05;
                }
                else if (zone == ZoneId.Residential)
                {
                    encounter = 0.08;
                }

                foreach (Point p in footprint)
                {
                    MapCell cell = grid.At(p.r, p.c);
                    cell.tileRole = tileRole;
                    cell.buildingType = buildingType;
                    cell.landmarkType = landmarkType;
                    cell.footprintStyle = footprintStyle;
                    cell.encounterChance = encounter;
                }

                if (!string.IsNullOrEmpty(landmarkType))
                {
                    foreach (Point p in footprint)
                    {
                        grid.At(p.r, p.c).isSpawnPoint = true;
                    }
                }

                BuildingAssemblyRecord record = new BuildingAssemblyRecord();
                record.id = buildingId++;
                record.lotId = lotId;
                record.blockId = grid.At(anchor.r, anchor.c).blockId;
                record.anchorRow = anchor.r;
                record.anchorCol = anchor.c;
                record.footprintR0 = footprintBounds.r0;
                record.footprintC0 = footprintBounds.c0;
                record.footprintR1 = footprintBounds.r1;
                record.footprintC1 = footprintBounds.c1;
                record.floors = floors;
                record.zone = MappingStrings.ToSerializedString(zone);
                record.buildingType = buildingType;
                record.landmarkType = landmarkType;
                record.footprintStyle = footprintStyle;
                record.facadeFamily = facade;
                record.roofType = roofType;
                record.assetSlot = assetSlot;
                record.spriteStack = SpriteStackFor(profileId, buildingType, landmarkType, floors, config.masterSeed, lotId);
                buildings.Add(record);
            }

            for (int r = 0; r < grid.Height; ++r)
            {
                for (int c = 0; c < grid.Width; ++c)
                {
                    MapCell cell = grid.At(r, c);
                    if (!cell.IsRoad)
                    {
                        continue;
                    }

                    int bitmask = grid.RoadBitmask(r, c);
                    int connections = 0;
                    for (int bit = 0; bit < 4; ++bit)
                    {
                        connections += (bitmask >> bit) & 1;
                    }

                    if (connections >= 3)
                    {
                        cell.isSpawnPoint = true;
                        if (cell.roadCategory == RoadCategory.Highway)
                        {
                            int hwConnections = 0;
                            List<Point> neighbours = Neighbours4(r, c);
                            for (int i = 0; i < neighbours.Count; ++i)
                            {
                                Point n = neighbours[i];
                                if (grid.InBounds(n.r, n.c) &&
                                    grid.At(n.r, n.c).roadCategory == RoadCategory.Highway)
                                {
                                    ++hwConnections;
                                }
                            }

                            if (hwConnections >= 3)
                            {
                                cell.tileRole = "highway_junction";
                            }
                        }
                    }
                }
            }
        }

        private void GenerateDistrictNames()
        {
            string[,] cbdNames =
            {
                { "Civic Core", "Financial Quarter", "Central District", "City Hall Area" },
                { "Financial District", "Lower East Side", "Wall Street", "Battery Park" },
                { "Eixample Centre", "Dreta", "Esquerra", "Gracia" },
                { "1er Arrondissement", "Marais", "Ile de la Cite", "Chatelet" },
                { "City of London", "Guildhall", "Barbican", "Monument" }
            };
            string[,] midNames =
            {
                { "Midtown", "Uptown", "Commerce Row", "Arts District" },
                { "Midtown East", "Midtown West", "Chelsea", "Murray Hill" },
                { "Sagrada Familia", "Pedralbes", "Sant Gervasi", "Horta" },
                { "Saint-Germain", "Montparnasse", "Opera Quarter", "Republique" },
                { "Soho", "Marylebone", "Clerkenwell", "Islington" }
            };
            string[,] resiNames =
            {
                { "Residential Quarter", "Westside", "Eastside", "Old Town" },
                { "Upper West Side", "Harlem", "Washington Heights", "Inwood" },
                { "Sarria", "Les Corts", "Sants", "Poblenou" },
                { "Belleville", "Nation", "Montmartre", "Batignolles" },
                { "Hackney", "Peckham", "Brixton", "Dalston" }
            };

            string prof = config.cityProfile;
            int pi = 0;
            if (prof == "manhattan") pi = 1;
            else if (prof == "barcelona_eixample") pi = 2;
            else if (prof == "paris_haussmann") pi = 3;
            else if (prof == "london_organic") pi = 4;

            for (int r = 0; r < grid.Height; ++r)
            {
                for (int c = 0; c < grid.Width; ++c)
                {
                    MapCell cell = grid.At(r, c);
                    if (!cell.isLand)
                    {
                        continue;
                    }

                    int quad = (r < cbdCenterR ? 0 : 2) + (c >= cbdCenterC ? 1 : 0);
                    if (cell.zoneId == ZoneId.CBD)
                    {
                        cell.districtName = cbdNames[pi, quad];
                    }
                    else if (cell.zoneId == ZoneId.Midtown)
                    {
                        cell.districtName = midNames[pi, quad];
                    }
                    else
                    {
                        cell.districtName = resiNames[pi, quad];
                    }
                }
            }
        }

        private void ComputeStats()
        {
            stats = new MapStats();
            stats.seed = config.masterSeed;
            stats.width = grid.Width;
            stats.height = grid.Height;
            stats.land = grid.LandCount();
            stats.water = grid.WaterCount();
            stats.roads = grid.RoadCount();
            stats.sidewalks = grid.SidewalkCount();
            stats.blocks = blocks.Count;
            stats.lots = lots.Count;
            stats.buildings = buildings.Count;
            stats.parks = 0;

            for (int i = 0; i < blocks.Count; ++i)
            {
                bool isParkBlock = false;
                foreach (Point p in blocks[i])
                {
                    if (grid.At(p.r, p.c).isPark)
                    {
                        isParkBlock = true;
                        break;
                    }
                }

                if (isParkBlock)
                {
                    ++stats.parks;
                }
            }

            HashSet<string> landmarkTypes = new HashSet<string>(StringComparer.Ordinal);
            for (int r = 0; r < grid.Height; ++r)
            {
                for (int c = 0; c < grid.Width; ++c)
                {
                    MapCell cell = grid.At(r, c);
                    if (cell.isSpawnPoint)
                    {
                        ++stats.spawns;
                    }

                    if (!string.IsNullOrEmpty(cell.landmarkType))
                    {
                        landmarkTypes.Add(cell.landmarkType);
                    }
                }
            }

            stats.landmarks = landmarkTypes.Count;
        }

        private static ProfileRules RulesForProfile(string id, MapConfig config)
        {
            ProfileRules rules = new ProfileRules(true);
            rules.avenueSpacing = config.avenueSpacing;
            rules.connectorSpacing = config.connectorSpacing;
            rules.connectorDensity = config.connectorDensity;
            rules.diagonalStreets = config.diagonalStreets;
            rules.highwayOrganic = config.highwayOrganic;
            rules.connectorOrganic = config.connectorOrganic;

            if (id == "manhattan")
            {
                rules.avenueSpacing = Math.Max(8, config.avenueSpacing - 5);
                rules.connectorSpacing = Math.Max(5, config.connectorSpacing - 2);
                rules.connectorDensity = Math.Max(config.connectorDensity, 0.78);
                rules.diagonalStreets = Math.Max(config.diagonalStreets, 2);
                rules.highwayOrganic = Math.Min(config.highwayOrganic, 0.22);
                rules.connectorOrganic = Math.Min(config.connectorOrganic, 0.04);
            }
            else if (id == "barcelona_eixample")
            {
                rules.avenueSpacing = Math.Max(8, config.avenueSpacing - 6);
                rules.connectorSpacing = Math.Max(8, config.connectorSpacing + 1);
                rules.connectorDensity = Math.Max(config.connectorDensity, 0.86);
                rules.diagonalStreets = 0;
                rules.highwayOrganic = Math.Min(config.highwayOrganic, 0.12);
                rules.connectorOrganic = Math.Min(config.connectorOrganic, 0.02);
            }
            else if (id == "paris_haussmann")
            {
                rules.avenueSpacing = Math.Max(10, config.avenueSpacing - 3);
                rules.connectorSpacing = Math.Max(7, config.connectorSpacing);
                rules.connectorDensity = Math.Max(config.connectorDensity, 0.72);
                rules.diagonalStreets = Math.Max(config.diagonalStreets, 4);
                rules.highwayOrganic = Math.Max(config.highwayOrganic, 0.24);
                rules.connectorOrganic = Math.Max(config.connectorOrganic, 0.12);
            }
            else if (id == "london_organic")
            {
                rules.avenueSpacing = Math.Max(9, config.avenueSpacing - 4);
                rules.connectorSpacing = Math.Max(7, config.connectorSpacing + 1);
                rules.connectorDensity = Math.Min(config.connectorDensity, 0.62);
                rules.diagonalStreets = Math.Max(1, config.diagonalStreets);
                rules.highwayOrganic = Math.Max(config.highwayOrganic, 0.52);
                rules.connectorOrganic = Math.Max(config.connectorOrganic, 0.18);
                rules.parkMinArea = 10;
                rules.parkMaxArea = 110;
                rules.cbdRadius = 0.36;
                rules.midtownRadius = 0.66;
            }

            if (id == "manhattan")
            {
                rules.cbdRadius = 0.40;
                rules.midtownRadius = 0.68;
            }
            else if (id == "barcelona_eixample")
            {
                rules.cbdRadius = 0.52;
                rules.midtownRadius = 0.76;
            }
            else if (id == "paris_haussmann")
            {
                rules.cbdRadius = 0.48;
                rules.midtownRadius = 0.72;
            }
            else if (id == "generic_dense")
            {
                rules.cbdRadius = 0.45;
                rules.midtownRadius = 0.72;
            }

            return rules;
        }

        private static CityProfile ProfileFor(string id)
        {
            string key = string.IsNullOrEmpty(id) ? "generic_dense" : id;
            CityProfile profile = new CityProfile();

            if (key == "manhattan")
            {
                profile.id = "manhattan";
                profile.label = "Manhattan / Harlem";
                profile.streetPattern = "long_avenues_short_cross_streets_diagonal";
                profile.blockRatio = "3.4:1";
                profile.designTags.AddRange(new[] { "avenue_grid", "waterfront_edges", "brownstone_midrise" });
                profile.assetStyleTags.AddRange(new[] { "brick_facade", "brownstone", "glass_cbd" });
                return profile;
            }

            if (key == "barcelona_eixample")
            {
                profile.id = "barcelona_eixample";
                profile.label = "Barcelona Eixample";
                profile.streetPattern = "regular_square_grid_chamfered_blocks";
                profile.blockRatio = "1.1:1";
                profile.designTags.AddRange(new[] { "square_grid", "chamfered_corners", "courtyard_blocks" });
                profile.assetStyleTags.AddRange(new[] { "stucco_facade", "balcony_rows", "courtyard_midrise" });
                return profile;
            }

            if (key == "paris_haussmann")
            {
                profile.id = "paris_haussmann";
                profile.label = "Paris Haussmann";
                profile.streetPattern = "boulevard_grid_with_diagonals";
                profile.blockRatio = "1.5:1";
                profile.designTags.AddRange(new[] { "boulevard", "monument_axis", "courtyard_blocks" });
                profile.assetStyleTags.AddRange(new[] { "stone_facade", "mansard_roof", "civic_limestone" });
                return profile;
            }

            if (key == "london_organic")
            {
                profile.id = "london_organic";
                profile.label = "London Organic";
                profile.streetPattern = "irregular_grid_low_drift";
                profile.blockRatio = "1.6:1";
                profile.designTags.AddRange(new[] { "irregular_blocks", "mixed_scale", "park_squares" });
                profile.assetStyleTags.AddRange(new[] { "brick_facade", "terrace_house", "stone_civic" });
                return profile;
            }

            profile.id = "generic_dense";
            profile.label = "Generic Dense City";
            profile.streetPattern = "orthogonal_grid_with_soft_drift";
            profile.blockRatio = "2.0:1";
            profile.designTags.AddRange(new[] { "balanced", "mixed_density", "gameplay_ready" });
            profile.assetStyleTags.AddRange(new[] { "neutral_facade", "mixed_urban", "generic_props" });
            return profile;
        }

        private static Point RepresentativePoint(SortedSet<Point> points)
        {
            double avgR = 0.0;
            double avgC = 0.0;
            foreach (Point p in points)
            {
                avgR += p.r;
                avgC += p.c;
            }

            int divisor = Math.Max(points.Count, 1);
            avgR /= divisor;
            avgC /= divisor;

            Point best = FirstPoint(points);
            double bestDist = double.MaxValue;
            foreach (Point p in points)
            {
                double dist = Hypot(p.r - avgR, p.c - avgC);
                if (dist < bestDist)
                {
                    bestDist = dist;
                    best = p;
                }
            }

            return best;
        }

        private static ZoneId DominantZone(SortedSet<Point> points, MapGrid grid)
        {
            int unassigned = 0;
            int cbd = 0;
            int midtown = 0;
            int residential = 0;

            foreach (Point p in points)
            {
                switch (grid.At(p.r, p.c).zoneId)
                {
                    case ZoneId.CBD: ++cbd; break;
                    case ZoneId.Midtown: ++midtown; break;
                    case ZoneId.Residential: ++residential; break;
                    default: ++unassigned; break;
                }
            }

            ZoneId best = ZoneId.Unassigned;
            int bestCount = unassigned;
            if (cbd > bestCount) { best = ZoneId.CBD; bestCount = cbd; }
            if (midtown > bestCount) { best = ZoneId.Midtown; bestCount = midtown; }
            if (residential > bestCount) { best = ZoneId.Residential; }
            return best;
        }

        private static Bounds BoundsFor(SortedSet<Point> points)
        {
            Bounds bounds = new Bounds();
            bounds.r0 = int.MaxValue;
            bounds.c0 = int.MaxValue;
            bounds.r1 = int.MinValue;
            bounds.c1 = int.MinValue;
            foreach (Point p in points)
            {
                bounds.r0 = Math.Min(bounds.r0, p.r);
                bounds.c0 = Math.Min(bounds.c0, p.c);
                bounds.r1 = Math.Max(bounds.r1, p.r);
                bounds.c1 = Math.Max(bounds.c1, p.c);
            }

            return bounds;
        }

        private static bool TouchesWaterfront(SortedSet<Point> points, MapGrid grid)
        {
            foreach (Point p in points)
            {
                if (!string.IsNullOrEmpty(grid.At(p.r, p.c).coastType))
                {
                    return true;
                }

                List<Point> neighbours = Neighbours4(p.r, p.c);
                for (int i = 0; i < neighbours.Count; ++i)
                {
                    Point n = neighbours[i];
                    if (grid.InBounds(n.r, n.c) && grid.At(n.r, n.c).isWater)
                    {
                        return true;
                    }
                }
            }

            return false;
        }

        private static string PickBuildingType(ZoneId zone, double roll, bool waterfront, double elevation)
        {
            bool hilltop = elevation > 0.62;
            bool lowland = elevation < 0.22;

            if (waterfront)
            {
                if (roll < 0.35) return "restaurant";
                if (roll < 0.60) return "market";
                if (roll < 0.90) return "apartment";
                return "empty";
            }

            if (zone == ZoneId.CBD)
            {
                double officeThreshold = hilltop ? 0.75 : 0.64;
                if (roll < officeThreshold) return "office";
                if (roll < 0.82) return "bank";
                return "civic";
            }

            if (zone == ZoneId.Midtown)
            {
                if (lowland)
                {
                    if (roll < 0.30) return "apartment";
                    if (roll < 0.65) return "shop";
                    return "restaurant";
                }

                if (roll < 0.46) return "apartment";
                if (roll < 0.76) return "shop";
                return "restaurant";
            }

            if (hilltop)
            {
                if (roll < 0.62) return "house";
                if (roll < 0.88) return "apartment";
                return "shop";
            }

            if (roll < 0.78) return "house";
            if (roll < 0.92) return "apartment";
            return "shop";
        }

        private static string AssetSlotForBuilding(string type)
        {
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

        private static string AssetSlotForBuildingRecord(string type, string landmarkType)
        {
            if (!string.IsNullOrEmpty(landmarkType))
            {
                return "landmark/" + landmarkType;
            }

            return AssetSlotForBuilding(type);
        }

        private static int FloorCountFor(ZoneId zone, string type, uint seed, int lotId, double elevation)
        {
            int elevBonus = elevation > 0.62 ? 1 : 0;
            if (type == "office") return DecisionRange(seed, lotId, 10, SaltBuildings, 7, 16) + elevBonus;
            if (type == "bank" || type == "civic") return DecisionRange(seed, lotId, 11, SaltBuildings, 3, 5);
            if (type == "hospital" || type == "police" || type == "station") return DecisionRange(seed, lotId, 16, SaltBuildings, 2, 4);
            if (type == "apartment")
            {
                return zone == ZoneId.CBD
                    ? DecisionRange(seed, lotId, 12, SaltBuildings, 5, 9) + elevBonus
                    : DecisionRange(seed, lotId, 13, SaltBuildings, 3, 6) + elevBonus;
            }

            if (type == "shop" || type == "restaurant" || type == "market") return DecisionRange(seed, lotId, 14, SaltBuildings, 1, 3);
            if (type == "house" || type == "school") return DecisionRange(seed, lotId, 15, SaltBuildings, 1, 3);
            return 1;
        }

        private static string RoofFor(string profileId, string type, int floors)
        {
            if (type == "office") return floors >= 8 ? "roof_glass_tower" : "roof_flat_a";
            if (profileId == "paris_haussmann") return "roof_mansard_a";
            if (profileId == "barcelona_eixample") return "roof_terracotta_a";
            if (type == "house") return "roof_peaked_a";
            if (profileId == "manhattan") return "roof_rowhouse_parapet";
            return "roof_flat_b";
        }

        private static string FacadeFamilyFor(string profileId, string type)
        {
            if (type == "office") return "glass_cbd";
            if (profileId == "manhattan") return "brick_brownstone";
            if (profileId == "barcelona_eixample") return "stucco_balcony";
            if (profileId == "paris_haussmann") return "limestone_mansard";
            if (profileId == "london_organic") return "brick_terrace";
            return "mixed_urban";
        }

        private static string FootprintStyleFor(string profileId, ZoneId zone, string type, Bounds bounds)
        {
            int w = bounds.c1 - bounds.c0 + 1;
            int h = bounds.r1 - bounds.r0 + 1;
            if (type == "civic" || type == "hospital" || type == "police" || type == "station" || type == "school")
            {
                return "institutional_courtyard";
            }

            if (profileId == "barcelona_eixample")
            {
                return Math.Abs(w - h) <= 1 ? "chamfered_courtyard" : "linear_courtyard";
            }

            if (profileId == "paris_haussmann")
            {
                return "perimeter_courtyard";
            }

            if (zone == ZoneId.Residential)
            {
                return w > h ? "rowhouse_strip" : "setback_pair";
            }

            if (zone == ZoneId.CBD)
            {
                return "tower_podium";
            }

            return w >= h ? "mixed_frontage_wide" : "mixed_frontage_deep";
        }

        private static string TileRoleForBuilding(ZoneId zone, string type, string landmarkType)
        {
            if (!string.IsNullOrEmpty(landmarkType) || type == "civic" ||
                type == "hospital" || type == "police" || type == "station")
            {
                return "bldg_civic";
            }

            if (zone == ZoneId.CBD)
            {
                return "bldg_cbd";
            }

            if (zone == ZoneId.Midtown)
            {
                return "bldg_mid";
            }

            return "bldg_resi";
        }

        private static string VariantSuffix(uint seed, int lotId, int saltShift)
        {
            char[] suffixes = { 'a', 'b', 'c', 'd' };
            uint index = DecisionHash(seed, lotId, saltShift, SaltBuildings) % 4u;
            return suffixes[(int)index].ToString();
        }

        private static List<string> SpriteStackFor(string profileId, string type, string landmarkType, int floors, uint seed, int lotId)
        {
            List<string> sprites = new List<string>();
            sprites.Add("shadow_bldg_2x2");

            if (landmarkType == "town_hall")
            {
                sprites.Add("landmark_town_hall_" + VariantSuffix(seed, lotId, 101));
                sprites.Add("bldg_civic_columns_a");
            }
            else if (landmarkType == "station")
            {
                sprites.Add("landmark_station_" + VariantSuffix(seed, lotId, 102));
            }
            else if (landmarkType == "hospital")
            {
                sprites.Add("landmark_hospital_" + VariantSuffix(seed, lotId, 103));
            }
            else if (landmarkType == "police")
            {
                sprites.Add("landmark_police_" + VariantSuffix(seed, lotId, 104));
            }
            else if (landmarkType == "school")
            {
                sprites.Add("landmark_school_" + VariantSuffix(seed, lotId, 105));
            }
            else if (type == "office")
            {
                sprites.Add(DecisionHash(seed, lotId, 1, SaltBuildings) % 2u != 0u ? "bldg_cbd_glass_a" : "bldg_cbd_glass_b");
            }
            else if (type == "apartment")
            {
                sprites.Add(DecisionHash(seed, lotId, 2, SaltBuildings) % 2u != 0u ? "bldg_mid_brownstone_a" : "bldg_mid_brick_a");
            }
            else if (type == "house")
            {
                sprites.Add(DecisionHash(seed, lotId, 3, SaltBuildings) % 2u != 0u ? "bldg_resi_detached_a" : "bldg_resi_rowhouse_a");
            }
            else if (type == "shop")
            {
                sprites.Add(DecisionHash(seed, lotId, 4, SaltBuildings) % 2u != 0u ? "bldg_shop_storefront_a" : "bldg_shop_storefront_b");
            }
            else if (type == "restaurant")
            {
                sprites.Add("bldg_restaurant_a");
            }
            else if (type == "market")
            {
                sprites.Add("bldg_market_a");
            }
            else if (type == "bank")
            {
                sprites.Add("bldg_bank_a");
            }
            else if (type == "civic")
            {
                sprites.Add("bldg_civic_a");
            }

            if (string.IsNullOrEmpty(landmarkType))
            {
                sprites.Add(RoofFor(profileId, type, floors));
            }

            if (string.IsNullOrEmpty(landmarkType) && profileId == "manhattan" && floors >= 4)
            {
                sprites.Add("kit_mhtn_fire_escape_a");
            }
            else if (string.IsNullOrEmpty(landmarkType) && profileId == "barcelona_eixample")
            {
                sprites.Add("kit_bcn_balcony_a");
            }
            else if (string.IsNullOrEmpty(landmarkType) && profileId == "paris_haussmann")
            {
                sprites.Add("kit_paris_balcony_ironwork");
            }
            else if (string.IsNullOrEmpty(landmarkType) && profileId == "london_organic" && type == "house")
            {
                sprites.Add("kit_ldn_bay_window_a");
            }

            return sprites;
        }

        private static int[,] BfsWaterDistance(MapGrid grid)
        {
            int rows = grid.Height;
            int cols = grid.Width;
            int[,] dist = new int[rows, cols];
            Queue<Point> q = new Queue<Point>();

            for (int r = 0; r < rows; ++r)
            {
                for (int c = 0; c < cols; ++c)
                {
                    dist[r, c] = int.MaxValue;
                    if (grid.At(r, c).isWater)
                    {
                        dist[r, c] = 0;
                        q.Enqueue(new Point(r, c));
                    }
                }
            }

            while (q.Count > 0)
            {
                Point p = q.Dequeue();
                List<Point> neighbours = Neighbours4(p.r, p.c);
                for (int i = 0; i < neighbours.Count; ++i)
                {
                    Point n = neighbours[i];
                    if (n.r >= 0 && n.r < rows && n.c >= 0 && n.c < cols && dist[n.r, n.c] == int.MaxValue)
                    {
                        dist[n.r, n.c] = dist[p.r, p.c] + 1;
                        q.Enqueue(n);
                    }
                }
            }

            return dist;
        }

        private static List<Point> Neighbours4(int r, int c)
        {
            return new List<Point>
            {
                new Point(r - 1, c),
                new Point(r + 1, c),
                new Point(r, c - 1),
                new Point(r, c + 1)
            };
        }

        private static bool[,] SmoothLand(bool[,] land, int passes)
        {
            int rows = land.GetLength(0);
            int cols = land.GetLength(1);

            for (int pass = 0; pass < passes; ++pass)
            {
                bool[,] next = new bool[rows, cols];
                for (int r = 0; r < rows; ++r)
                {
                    for (int c = 0; c < cols; ++c)
                    {
                        int total = 0;
                        int count = 0;
                        for (int dr = -1; dr <= 1; ++dr)
                        {
                            for (int dc = -1; dc <= 1; ++dc)
                            {
                                int nr = r + dr;
                                int nc = c + dc;
                                if (nr >= 0 && nr < rows && nc >= 0 && nc < cols)
                                {
                                    ++total;
                                    if (land[nr, nc])
                                    {
                                        ++count;
                                    }
                                }
                            }
                        }

                        next[r, c] = count * 2 > total;
                    }
                }

                land = next;
            }

            return land;
        }

        private static double DirectionalGradient(int r, int c, int rows, int cols, CoastSide side)
        {
            double t = 1.0;
            switch (side)
            {
                case CoastSide.West:
                    t = (double)c / Math.Max(cols - 1, 1);
                    break;
                case CoastSide.East:
                    t = 1.0 - (double)c / Math.Max(cols - 1, 1);
                    break;
                case CoastSide.North:
                    t = (double)r / Math.Max(rows - 1, 1);
                    break;
                case CoastSide.South:
                    t = 1.0 - (double)r / Math.Max(rows - 1, 1);
                    break;
            }

            return Math.Pow(Clamp01(t), 2.2);
        }

        private static double Fbm(double x, double y, uint seed, int octaves)
        {
            double total = 0.0;
            double amp = 1.0;
            double freq = 1.0;
            double norm = 0.0;

            for (int i = 0; i < octaves; ++i)
            {
                total += InterpolatedNoise(x * freq, y * freq, unchecked(seed + (uint)(i * 1013))) * amp;
                norm += amp;
                amp *= 0.5;
                freq *= 2.0;
            }

            return total / Math.Max(norm, 0.0001);
        }

        private static double InterpolatedNoise(double x, double y, uint seed)
        {
            int x0 = (int)Math.Floor(x);
            int y0 = (int)Math.Floor(y);
            int x1 = x0 + 1;
            int y1 = y0 + 1;
            double sx = SmoothStep(0.0, 1.0, x - x0);
            double sy = SmoothStep(0.0, 1.0, y - y0);
            double n00 = ValueNoise(x0, y0, seed);
            double n10 = ValueNoise(x1, y0, seed);
            double n01 = ValueNoise(x0, y1, seed);
            double n11 = ValueNoise(x1, y1, seed);
            double ix0 = n00 + (n10 - n00) * sx;
            double ix1 = n01 + (n11 - n01) * sx;
            return ix0 + (ix1 - ix0) * sy;
        }

        private static double ValueNoise(int x, int y, uint seed)
        {
            unchecked
            {
                uint h = seed;
                h ^= (uint)x * 0x27d4eb2du;
                h ^= (uint)y * 0x85ebca6bu;
                h ^= h >> 15;
                h *= 0x2c1b3c6du;
                h ^= h >> 12;
                return (double)(h & 0xFFFFu) / 65535.0;
            }
        }

        private static double SmoothStep(double edge0, double edge1, double x)
        {
            double t = Clamp01((x - edge0) / (edge1 - edge0));
            return t * t * (3.0 - 2.0 * t);
        }

        private static uint DecisionHash(uint seed, int a, int b, uint salt)
        {
            unchecked
            {
                uint h = seed ^ salt;
                h ^= MixU32((uint)a + 0x9e3779b9u);
                h ^= MixU32((uint)b + 0x85ebca6bu);
                return MixU32(h);
            }
        }

        private static double Decision01(uint seed, int a, int b, uint salt)
        {
            return (double)DecisionHash(seed, a, b, salt) / uint.MaxValue;
        }

        private static int DecisionRange(uint seed, int a, int b, uint salt, int minValue, int maxValue)
        {
            if (maxValue <= minValue)
            {
                return minValue;
            }

            unchecked
            {
                uint span = (uint)(maxValue - minValue + 1);
                return minValue + (int)(DecisionHash(seed, a, b, salt) % span);
            }
        }

        internal static uint MixU32(uint x)
        {
            unchecked
            {
                x ^= x >> 16;
                x *= 0x7feb352du;
                x ^= x >> 15;
                x *= 0x846ca68bu;
                x ^= x >> 16;
                return x;
            }
        }

        private static double Clamp01(double value)
        {
            if (value < 0.0) return 0.0;
            if (value > 1.0) return 1.0;
            return value;
        }

        private static int ClampInt(int value, int min, int max)
        {
            if (value < min) return min;
            if (value > max) return max;
            return value;
        }

        private static double ClampDouble(double value, double min, double max)
        {
            if (value < min) return min;
            if (value > max) return max;
            return value;
        }

        private static double Hypot(double a, double b)
        {
            return Math.Sqrt(a * a + b * b);
        }

        private static int RoundToInt(double value)
        {
            return value >= 0.0 ? (int)Math.Floor(value + 0.5) : (int)Math.Ceiling(value - 0.5);
        }

        private static int SafeInitialGridDimension(int value)
        {
            return value > 0 && value <= MaxMapDimension ? value : 1;
        }

        private static bool IsValidCoastSide(CoastSide side)
        {
            switch (side)
            {
                case CoastSide.None:
                case CoastSide.North:
                case CoastSide.South:
                case CoastSide.East:
                case CoastSide.West:
                case CoastSide.Random:
                    return true;
                default:
                    return false;
            }
        }

        private static Point FirstPoint(SortedSet<Point> points)
        {
            foreach (Point p in points)
            {
                return p;
            }

            return new Point(0, 0);
        }

        private struct ProfileRules
        {
            public int avenueSpacing;
            public int connectorSpacing;
            public double connectorDensity;
            public int diagonalStreets;
            public double highwayOrganic;
            public double connectorOrganic;
            public int parkMinArea;
            public int parkMaxArea;
            public double cbdRadius;
            public double midtownRadius;

            public ProfileRules(bool defaults)
            {
                avenueSpacing = 18;
                connectorSpacing = 8;
                connectorDensity = 0.65;
                diagonalStreets = 2;
                highwayOrganic = 0.3;
                connectorOrganic = 0.08;
                parkMinArea = 18;
                parkMaxArea = 140;
                cbdRadius = 0.45;
                midtownRadius = 0.72;
            }
        }

        private struct Bounds
        {
            public int r0;
            public int c0;
            public int r1;
            public int c1;
        }

        private struct RiverBridgeCandidate
        {
            public readonly Point cell;
            public readonly bool northSouthRiver;

            public RiverBridgeCandidate(Point cell, bool northSouthRiver)
            {
                this.cell = cell;
                this.northSouthRiver = northSouthRiver;
            }
        }

        private struct Point : IComparable<Point>, IEquatable<Point>
        {
            public readonly int r;
            public readonly int c;

            public Point(int r, int c)
            {
                this.r = r;
                this.c = c;
            }

            public int CompareTo(Point other)
            {
                int rowCompare = r.CompareTo(other.r);
                return rowCompare != 0 ? rowCompare : c.CompareTo(other.c);
            }

            public bool Equals(Point other)
            {
                return r == other.r && c == other.c;
            }

            public override bool Equals(object obj)
            {
                return obj is Point && Equals((Point)obj);
            }

            public override int GetHashCode()
            {
                unchecked
                {
                    return (r * 397) ^ c;
                }
            }
        }
    }
}
