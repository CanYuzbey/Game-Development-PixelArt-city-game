using System.Collections.Generic;
using System.Text;

namespace GameDev.Mapping
{
    public static class CityMapJsonExporter
    {
        public static string ToJson(MapGenerator generator)
        {
            DesignBlueprint blueprint = generator.ToDesignBlueprint();
            return ToJson(generator, blueprint);
        }

        public static string ToJson(MapGenerator generator, DesignBlueprint blueprint)
        {
            StringBuilder output = new StringBuilder(1024 * 64);
            MapConfig config = generator.Config;
            output.Append("{\n")
                .Append("  \"schema\": \"deployable_city_map.v2\",\n")
                .Append("  \"algorithm_version\": \"").Append(EscapeJson(blueprint.algorithmVersion)).Append("\",\n")
                .Append("  \"resolved_coast_side\": \"").Append(EscapeJson(blueprint.resolvedCoastSide)).Append("\",\n");

            if (config.hasWorldChunkMetadata)
            {
                output.Append("  \"world_seed\": ").Append(config.worldSeed).Append(",\n")
                    .Append("  \"chunk_x\": ").Append(config.chunkX).Append(",\n")
                    .Append("  \"chunk_y\": ").Append(config.chunkY).Append(",\n")
                    .Append("  \"chunk_size\": ").Append(config.chunkSize).Append(",\n");
            }

            WriteStats(output, generator.Stats);
            WriteProfile(output, blueprint.profile);
            output.Append("  \"required_asset_slots\": ");
            WriteStringArray(output, blueprint.requiredAssetSlots);
            output.Append(",\n");
            WriteRoads(output, blueprint.roads);
            WriteBlocks(output, blueprint.blocks);
            WriteLots(output, blueprint.lots);
            WriteLandmarks(output, blueprint.landmarks);
            WriteBuildings(output, blueprint.buildings);
            WriteSpriteAssignments(output, blueprint.spriteAssignments);
            WriteCells(output, generator.Grid);
            output.Append("}\n");
            return output.ToString();
        }

        private static void WriteStats(StringBuilder output, MapStats stats)
        {
            output.Append("  \"stats\": {\n")
                .Append("    \"seed\": ").Append(stats.seed).Append(",\n")
                .Append("    \"width\": ").Append(stats.width).Append(",\n")
                .Append("    \"height\": ").Append(stats.height).Append(",\n")
                .Append("    \"land\": ").Append(stats.land).Append(",\n")
                .Append("    \"water\": ").Append(stats.water).Append(",\n")
                .Append("    \"roads\": ").Append(stats.roads).Append(",\n")
                .Append("    \"sidewalks\": ").Append(stats.sidewalks).Append(",\n")
                .Append("    \"blocks\": ").Append(stats.blocks).Append(",\n")
                .Append("    \"parks\": ").Append(stats.parks).Append(",\n")
                .Append("    \"lots\": ").Append(stats.lots).Append(",\n")
                .Append("    \"spawns\": ").Append(stats.spawns).Append(",\n")
                .Append("    \"landmarks\": ").Append(stats.landmarks).Append(",\n")
                .Append("    \"buildings\": ").Append(stats.buildings).Append("\n")
                .Append("  },\n");
        }

        private static void WriteProfile(StringBuilder output, CityProfile profile)
        {
            output.Append("  \"profile\": {\n")
                .Append("    \"id\": \"").Append(EscapeJson(profile.id)).Append("\",\n")
                .Append("    \"label\": \"").Append(EscapeJson(profile.label)).Append("\",\n")
                .Append("    \"street_pattern\": \"").Append(EscapeJson(profile.streetPattern)).Append("\",\n")
                .Append("    \"block_ratio\": \"").Append(EscapeJson(profile.blockRatio)).Append("\",\n")
                .Append("    \"design_tags\": ");
            WriteStringArray(output, profile.designTags);
            output.Append(",\n    \"asset_style_tags\": ");
            WriteStringArray(output, profile.assetStyleTags);
            output.Append("\n  },\n");
        }

        private static void WriteRoads(StringBuilder output, List<RoadRecord> roads)
        {
            output.Append("  \"roads\": [\n");
            for (int i = 0; i < roads.Count; ++i)
            {
                RoadRecord road = roads[i];
                output.Append("    {\"row\": ").Append(road.row)
                    .Append(", \"col\": ").Append(road.col)
                    .Append(", \"category\": \"").Append(EscapeJson(road.category))
                    .Append("\", \"bitmask\": ").Append(road.bitmask)
                    .Append(", \"zone\": \"").Append(EscapeJson(road.zone))
                    .Append("\", \"intersection\": ").Append(road.isIntersection ? "true" : "false")
                    .Append(", \"asset_slot\": \"").Append(EscapeJson(road.assetSlot)).Append("\"}");
                output.Append(i + 1 == roads.Count ? "\n" : ",\n");
            }
            output.Append("  ],\n");
        }

        private static void WriteBlocks(StringBuilder output, List<BlockRecord> blocks)
        {
            output.Append("  \"blocks\": [\n");
            for (int i = 0; i < blocks.Count; ++i)
            {
                BlockRecord block = blocks[i];
                output.Append("    {\"id\": ").Append(block.id)
                    .Append(", \"area\": ").Append(block.area)
                    .Append(", \"bounds\": [").Append(block.r0).Append(", ").Append(block.c0)
                    .Append(", ").Append(block.r1).Append(", ").Append(block.c1).Append("]")
                    .Append(", \"zone\": \"").Append(EscapeJson(block.zone))
                    .Append("\", \"park\": ").Append(block.isPark ? "true" : "false").Append("}");
                output.Append(i + 1 == blocks.Count ? "\n" : ",\n");
            }
            output.Append("  ],\n");
        }

        private static void WriteLots(StringBuilder output, List<LotRecord> lots)
        {
            output.Append("  \"lots\": [\n");
            for (int i = 0; i < lots.Count; ++i)
            {
                LotRecord lot = lots[i];
                output.Append("    {\"id\": ").Append(lot.id)
                    .Append(", \"block_id\": ").Append(lot.blockId)
                    .Append(", \"area\": ").Append(lot.area)
                    .Append(", \"zone\": \"").Append(EscapeJson(lot.zone))
                    .Append("\", \"building_type\": \"").Append(EscapeJson(lot.buildingType))
                    .Append("\", \"landmark_type\": \"").Append(EscapeJson(lot.landmarkType))
                    .Append("\", \"asset_slot\": \"").Append(EscapeJson(lot.assetSlot)).Append("\"}");
                output.Append(i + 1 == lots.Count ? "\n" : ",\n");
            }
            output.Append("  ],\n");
        }

        private static void WriteLandmarks(StringBuilder output, List<LandmarkRecord> landmarks)
        {
            output.Append("  \"landmarks\": [\n");
            for (int i = 0; i < landmarks.Count; ++i)
            {
                LandmarkRecord landmark = landmarks[i];
                output.Append("    {\"type\": \"").Append(EscapeJson(landmark.type))
                    .Append("\", \"row\": ").Append(landmark.row)
                    .Append(", \"col\": ").Append(landmark.col)
                    .Append(", \"asset_slot\": \"").Append(EscapeJson(landmark.assetSlot)).Append("\"}");
                output.Append(i + 1 == landmarks.Count ? "\n" : ",\n");
            }
            output.Append("  ],\n");
        }

        private static void WriteBuildings(StringBuilder output, List<BuildingAssemblyRecord> buildings)
        {
            output.Append("  \"buildings\": [\n");
            for (int i = 0; i < buildings.Count; ++i)
            {
                BuildingAssemblyRecord building = buildings[i];
                output.Append("    {\"id\": ").Append(building.id)
                    .Append(", \"lot_id\": ").Append(building.lotId)
                    .Append(", \"block_id\": ").Append(building.blockId)
                    .Append(", \"anchor\": [").Append(building.anchorRow).Append(", ").Append(building.anchorCol).Append("]")
                    .Append(", \"footprint\": [").Append(building.footprintR0).Append(", ").Append(building.footprintC0)
                    .Append(", ").Append(building.footprintR1).Append(", ").Append(building.footprintC1).Append("]")
                    .Append(", \"floors\": ").Append(building.floors)
                    .Append(", \"zone\": \"").Append(EscapeJson(building.zone))
                    .Append("\", \"building_type\": \"").Append(EscapeJson(building.buildingType))
                    .Append("\", \"landmark_type\": \"").Append(EscapeJson(building.landmarkType))
                    .Append("\", \"footprint_style\": \"").Append(EscapeJson(building.footprintStyle))
                    .Append("\", \"facade_family\": \"").Append(EscapeJson(building.facadeFamily))
                    .Append("\", \"roof_type\": \"").Append(EscapeJson(building.roofType))
                    .Append("\", \"asset_slot\": \"").Append(EscapeJson(building.assetSlot))
                    .Append("\", \"sprite_stack\": ");
                WriteStringArray(output, building.spriteStack);
                output.Append("}");
                output.Append(i + 1 == buildings.Count ? "\n" : ",\n");
            }
            output.Append("  ],\n");
        }

        private static void WriteSpriteAssignments(StringBuilder output, List<SpriteAssignmentRecord> assignments)
        {
            output.Append("  \"sprite_assignments\": [\n");
            for (int i = 0; i < assignments.Count; ++i)
            {
                SpriteAssignmentRecord assignment = assignments[i];
                output.Append("    {\"target_kind\": \"").Append(EscapeJson(assignment.targetKind))
                    .Append("\", \"target_id\": ").Append(assignment.targetId)
                    .Append(", \"row\": ").Append(assignment.row)
                    .Append(", \"col\": ").Append(assignment.col)
                    .Append(", \"asset_slot\": \"").Append(EscapeJson(assignment.assetSlot))
                    .Append("\", \"sprite_ids\": ");
                WriteStringArray(output, assignment.spriteIds);
                output.Append(", \"reason\": \"").Append(EscapeJson(assignment.reason))
                    .Append("\", \"decision_hash\": ").Append(assignment.decisionHash).Append("}");
                output.Append(i + 1 == assignments.Count ? "\n" : ",\n");
            }
            output.Append("  ],\n");
        }

        private static void WriteCells(StringBuilder output, MapGrid grid)
        {
            output.Append("  \"cells\": [\n");
            bool first = true;
            for (int r = 0; r < grid.Height; ++r)
            {
                for (int c = 0; c < grid.Width; ++c)
                {
                    if (!first)
                    {
                        output.Append(",\n");
                    }
                    first = false;

                    MapCell cell = grid.At(r, c);
                    output.Append("    {\"row\": ").Append(r)
                        .Append(", \"col\": ").Append(c)
                        .Append(", \"role\": \"").Append(EscapeJson(cell.tileRole))
                        .Append("\", \"zone\": \"").Append(EscapeJson(MappingStrings.ToSerializedString(cell.zoneId)))
                        .Append("\", \"road\": \"").Append(EscapeJson(MappingStrings.ToSerializedString(cell.roadCategory)))
                        .Append("\", \"block_id\": ").Append(cell.blockId)
                        .Append(", \"lot_id\": ").Append(cell.lotId)
                        .Append(", \"land\": ").Append(cell.isLand ? "true" : "false")
                        .Append(", \"water\": ").Append(cell.isWater ? "true" : "false")
                        .Append(", \"park\": ").Append(cell.isPark ? "true" : "false")
                        .Append(", \"setback\": ").Append(cell.isSetback ? "true" : "false")
                        .Append(", \"spawn\": ").Append(cell.isSpawnPoint ? "true" : "false")
                        .Append(", \"damaged\": ").Append(cell.isDamaged ? "true" : "false")
                        .Append(", \"bridge\": ").Append(cell.isBridge ? "true" : "false")
                        .Append(", \"road_turn\": ").Append(cell.isRoadTurn ? "true" : "false")
                        .Append(", \"intersection\": ").Append(cell.isIntersection ? "true" : "false")
                        .Append(", \"coast\": \"").Append(EscapeJson(cell.coastType))
                        .Append("\", \"building_type\": \"").Append(EscapeJson(cell.buildingType))
                        .Append("\", \"landmark_type\": \"").Append(EscapeJson(cell.landmarkType))
                        .Append("\", \"footprint_style\": \"").Append(EscapeJson(cell.footprintStyle))
                        .Append("\", \"district\": \"").Append(EscapeJson(cell.districtName))
                        .Append("\", \"density\": ").Append(FormatNumber(cell.densityScore))
                        .Append(", \"elevation\": ").Append(FormatNumber(cell.elevation))
                        .Append(", \"encounter_chance\": ").Append(FormatNumber(cell.encounterChance))
                        .Append("}");
                }
            }
            output.Append("\n  ]\n");
        }

        private static void WriteStringArray(StringBuilder output, List<string> values)
        {
            output.Append("[");
            for (int i = 0; i < values.Count; ++i)
            {
                if (i != 0)
                {
                    output.Append(", ");
                }

                output.Append("\"").Append(EscapeJson(values[i])).Append("\"");
            }
            output.Append("]");
        }

        private static string EscapeJson(string value)
        {
            if (string.IsNullOrEmpty(value))
            {
                return "";
            }

            StringBuilder output = new StringBuilder(value.Length + 8);
            for (int i = 0; i < value.Length; ++i)
            {
                char ch = value[i];
                switch (ch)
                {
                    case '\\': output.Append("\\\\"); break;
                    case '"': output.Append("\\\""); break;
                    case '\n': output.Append("\\n"); break;
                    case '\r': output.Append("\\r"); break;
                    case '\t': output.Append("\\t"); break;
                    default: output.Append(ch); break;
                }
            }

            return output.ToString();
        }

        private static string FormatNumber(double value)
        {
            return value.ToString("0.###", System.Globalization.CultureInfo.InvariantCulture);
        }
    }
}
