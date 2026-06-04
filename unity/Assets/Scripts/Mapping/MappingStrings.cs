using System;

namespace GameDev.Mapping
{
    public static class MappingStrings
    {
        public static bool IsValidCityProfile(string id)
        {
            string key = string.IsNullOrEmpty(id) ? "generic_dense" : id;
            return key == "generic_dense" ||
                   key == "manhattan" ||
                   key == "barcelona_eixample" ||
                   key == "paris_haussmann" ||
                   key == "london_organic";
        }

        public static string ToSerializedString(CoastSide side)
        {
            switch (side)
            {
                case CoastSide.North: return "north";
                case CoastSide.South: return "south";
                case CoastSide.East: return "east";
                case CoastSide.West: return "west";
                case CoastSide.Random: return "random";
                default: return "none";
            }
        }

        public static string ToSerializedString(ZoneId zone)
        {
            switch (zone)
            {
                case ZoneId.CBD: return "cbd";
                case ZoneId.Midtown: return "midtown";
                case ZoneId.Residential: return "residential";
                default: return "unassigned";
            }
        }

        public static string ToSerializedString(RoadCategory category)
        {
            switch (category)
            {
                case RoadCategory.Highway: return "highway";
                case RoadCategory.Connector: return "connector";
                default: return "";
            }
        }

        public static CoastSide CoastSideFromString(string value)
        {
            switch (value)
            {
                case "none": return CoastSide.None;
                case "north": return CoastSide.North;
                case "south": return CoastSide.South;
                case "east": return CoastSide.East;
                case "west": return CoastSide.West;
                case "random": return CoastSide.Random;
                default: throw new ArgumentException("unknown coast side: " + value);
            }
        }
    }
}
