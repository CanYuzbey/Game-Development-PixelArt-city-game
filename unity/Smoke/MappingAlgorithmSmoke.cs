using System;
using System.Collections.Generic;
using GameDev.Mapping;

public static class MappingAlgorithmSmoke
{
    public static int Main()
    {
        int passed = 0;
        int failed = 0;

        CoastSide[] coasts =
        {
            CoastSide.None,
            CoastSide.North,
            CoastSide.South,
            CoastSide.East,
            CoastSide.West,
            CoastSide.Random
        };

        string[] profiles =
        {
            "generic_dense",
            "manhattan",
            "barcelona_eixample",
            "paris_haussmann",
            "london_organic"
        };

        for (uint seed = 1; seed <= 12; ++seed)
        {
            for (int i = 0; i < coasts.Length; ++i)
            {
                MapConfig config = new MapConfig();
                config.width = 80;
                config.height = 60;
                config.masterSeed = seed;
                config.coastSide = coasts[i];
                config.cityProfile = profiles[i % profiles.Length];

                if (ValidateConfig(config))
                {
                    ++passed;
                }
                else
                {
                    ++failed;
                }
            }
        }

        if (ValidatePhaseOrder()) ++passed; else ++failed;
        if (ValidateWorldGenerator()) ++passed; else ++failed;
        if (ValidateCrossChunkHighwayBoundaries()) ++passed; else ++failed;
        if (ValidateLargeMap()) ++passed; else ++failed;
        if (ValidateJsonExport()) ++passed; else ++failed;
        if (ValidateRejections()) ++passed; else ++failed;

        Console.WriteLine("mapping_algorithm_csharp_smoke PASS=" + passed + " FAIL=" + failed);
        return failed == 0 ? 0 : 1;
    }

    private static bool ValidateConfig(MapConfig config)
    {
        try
        {
            MapGenerator a = new MapGenerator(config);
            a.Generate();
            MapGenerator b = new MapGenerator(config);
            b.Generate();

            if (!SameStats(a.Stats, b.Stats))
            {
                Console.Error.WriteLine("determinism failed seed=" + config.masterSeed);
                return false;
            }

            MapGenerator reusable = new MapGenerator(config);
            reusable.Generate();
            MapStats first = reusable.Stats.Clone();
            reusable.Generate();
            if (!SameStats(first, reusable.Stats))
            {
                Console.Error.WriteLine("same-generator rerun failed seed=" + config.masterSeed);
                return false;
            }

            MapStats stats = a.Stats;
            if (stats.land <= 0 || stats.roads <= 0 || stats.blocks <= 0 || stats.lots <= 0)
            {
                Console.Error.WriteLine("empty city structure seed=" + config.masterSeed);
                return false;
            }

            if (stats.parks <= 0 || stats.landmarks <= 0 || stats.spawns <= 0 || stats.buildings <= 0)
            {
                Console.Error.WriteLine("missing gameplay layer seed=" + config.masterSeed);
                return false;
            }

            double roadRatio = (double)stats.roads / stats.land;
            if (roadRatio < 0.05 || roadRatio > 0.50)
            {
                Console.Error.WriteLine("road ratio outside guard rails seed=" + config.masterSeed + " ratio=" + roadRatio);
                return false;
            }

            DesignBlueprint blueprint = a.ToDesignBlueprint();
            if (blueprint.schema != "city_design_blueprint.v2" ||
                blueprint.profile.id != config.cityProfile ||
                blueprint.roads.Count == 0 ||
                blueprint.blocks.Count == 0 ||
                blueprint.lots.Count == 0 ||
                blueprint.buildings.Count == 0 ||
                blueprint.spriteAssignments.Count == 0 ||
                blueprint.requiredAssetSlots.Count == 0)
            {
                Console.Error.WriteLine("blueprint failed seed=" + config.masterSeed);
                return false;
            }

            if (blueprint.seed != config.masterSeed ||
                blueprint.resolvedCoastSide == "random" ||
                blueprint.buildings.Count != stats.buildings ||
                blueprint.spriteAssignments.Count != blueprint.buildings.Count)
            {
                Console.Error.WriteLine("blueprint mismatch seed=" + config.masterSeed);
                return false;
            }

            if (!HasSlot(blueprint, "street/road") ||
                !HasSlot(blueprint, "building/roof") ||
                !HasSlot(blueprint, "overlay/shadow") ||
                HasSlot(blueprint, "road/highway") ||
                HasSlot(blueprint, "road/connector"))
            {
                Console.Error.WriteLine("asset slot contract mismatch seed=" + config.masterSeed);
                return false;
            }

            if (!ValidateRoadLocalConnectivity(a.Grid) || !ValidateLotUniqueness(blueprint))
            {
                return false;
            }

            if (!ValidateBridgeAndRoadAnnotations(a.Grid))
            {
                return false;
            }

            return true;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine("validate failed seed=" + config.masterSeed + " " + ex.Message);
            return false;
        }
    }

    private static bool ValidateWorldGenerator()
    {
        WorldConfig config = new WorldConfig();
        config.worldSeed = 0xDEADBEEF;
        config.chunkCols = 8;
        config.chunkRows = 6;
        config.chunkWidth = 64;
        config.chunkHeight = 48;
        WorldGenerator world = new WorldGenerator(config);
        world.Plan();
        if (world.ChunkCount() != 48) return false;
        ChunkPlan cbd = world.ChunkAt(3, 2);
        if (cbd.worldZone != WorldZone.CBD) return false;
        if (cbd.cityProfile != "paris_haussmann") return false;
        if (world.ChunkAt(0, 0).coastSide != CoastSide.North) return false;
        if (world.ChunkAt(0, 5).coastSide != CoastSide.South) return false;
        MapConfig cbdConfig = world.ConfigForChunk(3, 2);
        if (cbdConfig.masterSeed != cbd.chunkSeed) return false;
        if (cbdConfig.enableLocalRivers) return false;
        if (!cbdConfig.hasWorldChunkMetadata || cbdConfig.worldSeed != config.worldSeed ||
            cbdConfig.chunkX != 3 || cbdConfig.chunkY != 2 || cbdConfig.chunkSize != config.chunkWidth)
        {
            return false;
        }
        return world.HighwayNsColumns().Count > 0 && world.HighwayEwRows().Count > 0;
    }

    private static bool ValidatePhaseOrder()
    {
        MapGenerationPhase[] order = MapGenerator.GetPhaseOrder();
        return IndexOf(order, MapGenerationPhase.LandAndSea) <
               IndexOf(order, MapGenerationPhase.Highways) &&
               IndexOf(order, MapGenerationPhase.Highways) <
               IndexOf(order, MapGenerationPhase.Roads) &&
               IndexOf(order, MapGenerationPhase.Roads) <
               IndexOf(order, MapGenerationPhase.Bridges) &&
               IndexOf(order, MapGenerationPhase.Bridges) <
               IndexOf(order, MapGenerationPhase.Buildings);
    }

    private static int IndexOf(MapGenerationPhase[] order, MapGenerationPhase phase)
    {
        for (int i = 0; i < order.Length; ++i)
        {
            if (order[i] == phase)
            {
                return i;
            }
        }

        return -1;
    }

    private static bool ValidateCrossChunkHighwayBoundaries()
    {
        WorldConfig config = new WorldConfig();
        config.worldSeed = 0xBADC0DE;
        config.chunkCols = 8;
        config.chunkRows = 6;
        config.chunkWidth = 64;
        config.chunkHeight = 48;

        WorldGenerator world = new WorldGenerator(config);
        world.Plan();

        List<int> nsColumns = world.HighwayNsColumns();
        if (nsColumns.Count == 0)
        {
            Console.Error.WriteLine("world highway planner produced no N-S columns");
            return false;
        }

        int boundaryCx = nsColumns[0];
        int cy = 2;
        MapGenerator left = new MapGenerator(world.ConfigForChunk(boundaryCx, cy));
        MapGenerator right = new MapGenerator(world.ConfigForChunk(boundaryCx + 1, cy));
        left.Generate();
        right.Generate();

        for (int r = 0; r < config.chunkHeight; ++r)
        {
            MapCell leftEdge = left.Grid.At(r, config.chunkWidth - 1);
            MapCell rightEdge = right.Grid.At(r, 0);
            if (leftEdge.roadCategory != RoadCategory.Highway ||
                rightEdge.roadCategory != RoadCategory.Highway)
            {
                Console.Error.WriteLine("N-S highway boundary mismatch row=" + r);
                return false;
            }
        }

        List<int> ewRows = world.HighwayEwRows();
        if (ewRows.Count == 0)
        {
            Console.Error.WriteLine("world highway planner produced no E-W rows");
            return false;
        }

        int boundaryCy = ewRows[0];
        int cx = 3;
        MapGenerator top = new MapGenerator(world.ConfigForChunk(cx, boundaryCy));
        MapGenerator bottom = new MapGenerator(world.ConfigForChunk(cx, boundaryCy + 1));
        top.Generate();
        bottom.Generate();

        for (int c = 0; c < config.chunkWidth; ++c)
        {
            MapCell topEdge = top.Grid.At(config.chunkHeight - 1, c);
            MapCell bottomEdge = bottom.Grid.At(0, c);
            if (topEdge.roadCategory != RoadCategory.Highway ||
                bottomEdge.roadCategory != RoadCategory.Highway)
            {
                Console.Error.WriteLine("E-W highway boundary mismatch col=" + c);
                return false;
            }
        }

        return true;
    }

    private static bool ValidateLargeMap()
    {
        MapConfig config = new MapConfig();
        config.width = 256;
        config.height = 256;
        config.masterSeed = 42;
        config.coastSide = CoastSide.West;
        config.cityProfile = "manhattan";
        MapGenerator generator = new MapGenerator(config);
        generator.Generate();
        return generator.Stats.land > 0 &&
               generator.Stats.roads > 0 &&
               generator.Stats.blocks > 0 &&
               generator.Stats.lots > 0 &&
               generator.Stats.buildings > 0;
    }

    private static bool ValidateJsonExport()
    {
        MapConfig config = new MapConfig();
        config.width = 32;
        config.height = 24;
        config.masterSeed = 7;
        config.cityProfile = "generic_dense";
        MapGenerator generator = new MapGenerator(config);
        generator.Generate();
        string json = CityMapJsonExporter.ToJson(generator);
        return json.Contains("\"schema\": \"deployable_city_map.v2\"") &&
               json.Contains("\"cells\"") &&
               json.Contains("\"sprite_assignments\"");
    }

    private static bool ValidateRejections()
    {
        try
        {
            MapConfig invalid = new MapConfig();
            invalid.cityProfile = "unknown_profile";
            new MapGenerator(invalid);
            return false;
        }
        catch (ArgumentException)
        {
        }

        try
        {
            MapConfig invalid = new MapConfig();
            invalid.width = 513;
            new MapGenerator(invalid);
            return false;
        }
        catch (ArgumentException)
        {
        }

        return true;
    }

    private static bool SameStats(MapStats a, MapStats b)
    {
        return a.land == b.land &&
               a.water == b.water &&
               a.roads == b.roads &&
               a.sidewalks == b.sidewalks &&
               a.blocks == b.blocks &&
               a.lots == b.lots &&
               a.parks == b.parks &&
               a.spawns == b.spawns &&
               a.landmarks == b.landmarks &&
               a.buildings == b.buildings;
    }

    private static bool HasSlot(DesignBlueprint blueprint, string slot)
    {
        return blueprint.requiredAssetSlots.Contains(slot);
    }

        private static bool ValidateRoadLocalConnectivity(MapGrid grid)
    {
        for (int r = 0; r < grid.Height; ++r)
        {
            for (int c = 0; c < grid.Width; ++c)
            {
                MapCell cell = grid.At(r, c);
                if (!cell.IsRoad)
                {
                    continue;
                }

                int neighbours = 0;
                if (grid.InBounds(r - 1, c) && grid.At(r - 1, c).IsRoad) ++neighbours;
                if (grid.InBounds(r + 1, c) && grid.At(r + 1, c).IsRoad) ++neighbours;
                if (grid.InBounds(r, c - 1) && grid.At(r, c - 1).IsRoad) ++neighbours;
                if (grid.InBounds(r, c + 1) && grid.At(r, c + 1).IsRoad) ++neighbours;

                if (neighbours == 0)
                {
                    Console.Error.WriteLine("isolated road cell r=" + r + " c=" + c);
                    return false;
                }
            }
        }

        return true;
        }

        private static bool ValidateBridgeAndRoadAnnotations(MapGrid grid)
        {
            int bridges = 0;
            int intersections = 0;

            for (int r = 0; r < grid.Height; ++r)
            {
                for (int c = 0; c < grid.Width; ++c)
                {
                    MapCell cell = grid.At(r, c);
                    if (cell.IsRoad && cell.isWater)
                    {
                        Console.Error.WriteLine("road on water without land bridge r=" + r + " c=" + c);
                        return false;
                    }

                    if (cell.isBridge)
                    {
                        ++bridges;
                        if (!cell.IsRoad || !cell.isLand || cell.isWater)
                        {
                            Console.Error.WriteLine("invalid bridge cell r=" + r + " c=" + c);
                            return false;
                        }
                    }

                    if (cell.isRoadTurn)
                    {
                        if (!cell.IsRoad || cell.isIntersection || !ExpectedRoadTurn(grid, r, c))
                        {
                            Console.Error.WriteLine("invalid road turn annotation r=" + r + " c=" + c);
                            return false;
                        }
                    }

                    if (cell.isIntersection)
                    {
                        ++intersections;
                        if (!cell.IsRoad || !ExpectedIntersection(grid, r, c))
                        {
                            Console.Error.WriteLine("invalid intersection annotation r=" + r + " c=" + c);
                            return false;
                        }
                    }
                }
            }

            return intersections > 0 && bridges >= 0;
        }

        private static bool ExpectedIntersection(MapGrid grid, int r, int c)
        {
            return RoadConnectionCount(grid, r, c) >= 3;
        }

        private static bool ExpectedRoadTurn(MapGrid grid, int r, int c)
        {
            int bitmask = grid.RoadBitmask(r, c);
            return RoadConnectionCount(grid, r, c) == 2 && bitmask != 10 && bitmask != 5;
        }

        private static int RoadConnectionCount(MapGrid grid, int r, int c)
        {
            int bitmask = grid.RoadBitmask(r, c);
            int connections = 0;
            for (int bit = 0; bit < 4; ++bit)
            {
                connections += (bitmask >> bit) & 1;
            }

            return connections;
        }

        private static bool ValidateLotUniqueness(DesignBlueprint blueprint)
    {
        HashSet<int> seen = new HashSet<int>();
        for (int i = 0; i < blueprint.buildings.Count; ++i)
        {
            int lotId = blueprint.buildings[i].lotId;
            if (seen.Contains(lotId))
            {
                Console.Error.WriteLine("duplicate lot id=" + lotId);
                return false;
            }

            seen.Add(lotId);
        }

        return true;
    }
}
