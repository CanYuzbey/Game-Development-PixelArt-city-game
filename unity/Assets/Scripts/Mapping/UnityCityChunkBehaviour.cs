#if UNITY_5_3_OR_NEWER
using UnityEngine;

namespace GameDev.Mapping
{
    public sealed class UnityCityChunkBehaviour : MonoBehaviour
    {
        [Header("Generation")]
        public int width = 96;
        public int height = 72;
        public uint seed = 42;
        public string cityProfile = "manhattan";
        public CoastSide coastSide = CoastSide.Random;
        public bool generateOnStart = true;

        public MapGenerator GeneratedMap { get; private set; }
        public DesignBlueprint GeneratedBlueprint { get; private set; }

        private void Start()
        {
            if (generateOnStart)
            {
                Generate();
            }
        }

        [ContextMenu("Generate City Chunk")]
        public void Generate()
        {
            MapConfig config = new MapConfig();
            config.width = width;
            config.height = height;
            config.masterSeed = seed;
            config.cityProfile = cityProfile;
            config.coastSide = coastSide;

            GeneratedMap = new MapGenerator(config);
            GeneratedMap.Generate();
            GeneratedBlueprint = GeneratedMap.ToDesignBlueprint();
        }
    }
}
#endif
