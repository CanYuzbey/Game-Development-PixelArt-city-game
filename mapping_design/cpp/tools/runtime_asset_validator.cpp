#include <algorithm>
#include <array>
#include <cctype>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <map>
#include <regex>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;

namespace {

struct Rect {
    int x = 0;
    int y = 0;
    int w = 0;
    int h = 0;
};

struct SpriteRecord {
    std::string id;
    std::string asset_slot;
    std::string runtime_status;
    std::string atlas_file;
    bool estimated = false;
    bool visual_trimmed = false;
    Rect atlas_rect;
    Rect trim_rect;
};

std::string read_text(const fs::path& path) {
    std::ifstream in(path);
    if (!in) {
        throw std::runtime_error("cannot open " + path.string());
    }
    return std::string(std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>());
}

std::string string_field(const std::string& object, const std::string& field) {
    const std::regex pattern("\"" + field + "\"\\s*:\\s*\"([^\"]*)\"");
    std::smatch match;
    if (!std::regex_search(object, match, pattern)) {
        return {};
    }
    return match[1].str();
}

int int_field(const std::string& text, const std::string& field, int fallback = 0) {
    const std::regex pattern("\"" + field + "\"\\s*:\\s*(-?[0-9]+)");
    std::smatch match;
    if (!std::regex_search(text, match, pattern)) {
        return fallback;
    }
    return std::stoi(match[1].str());
}

Rect rect_field(const std::string& object, const std::string& field) {
    const std::regex pattern("\"" + field + "\"\\s*:\\s*\\[\\s*(-?[0-9]+)\\s*,\\s*(-?[0-9]+)\\s*,\\s*(-?[0-9]+)\\s*,\\s*(-?[0-9]+)\\s*\\]");
    std::smatch match;
    if (!std::regex_search(object, match, pattern)) {
        return {};
    }
    return {std::stoi(match[1].str()), std::stoi(match[2].str()),
            std::stoi(match[3].str()), std::stoi(match[4].str())};
}

bool bool_true_field(const std::string& object, const std::string& field) {
    const std::regex pattern("\"" + field + "\"\\s*:\\s*true");
    return std::regex_search(object, pattern);
}

std::size_t find_matching_brace(const std::string& text, std::size_t open) {
    bool in_string = false;
    bool escaped = false;
    int depth = 0;
    for (std::size_t i = open; i < text.size(); ++i) {
        const char ch = text[i];
        if (in_string) {
            if (escaped) {
                escaped = false;
            } else if (ch == '\\') {
                escaped = true;
            } else if (ch == '"') {
                in_string = false;
            }
            continue;
        }
        if (ch == '"') {
            in_string = true;
        } else if (ch == '{') {
            ++depth;
        } else if (ch == '}') {
            --depth;
            if (depth == 0) {
                return i;
            }
        }
    }
    throw std::runtime_error("unbalanced object braces");
}

std::vector<SpriteRecord> parse_sprites(const std::string& text) {
    const auto sprites_key = text.find("\"sprites\"");
    if (sprites_key == std::string::npos) {
        throw std::runtime_error("registry has no sprites object");
    }
    const auto sprites_open = text.find('{', sprites_key);
    if (sprites_open == std::string::npos) {
        throw std::runtime_error("registry sprites object is malformed");
    }
    const auto sprites_close = find_matching_brace(text, sprites_open);

    std::vector<SpriteRecord> records;
    std::size_t pos = sprites_open + 1;
    while (pos < sprites_close) {
        while (pos < sprites_close && (std::isspace(static_cast<unsigned char>(text[pos])) || text[pos] == ',')) {
            ++pos;
        }
        if (pos >= sprites_close || text[pos] == '}') {
            break;
        }
        if (text[pos] != '"') {
            throw std::runtime_error("expected sprite id string");
        }
        const auto id_end = text.find('"', pos + 1);
        if (id_end == std::string::npos) {
            throw std::runtime_error("unterminated sprite id");
        }
        const std::string id = text.substr(pos + 1, id_end - pos - 1);
        const auto object_open = text.find('{', id_end);
        if (object_open == std::string::npos || object_open > sprites_close) {
            throw std::runtime_error("missing sprite object for " + id);
        }
        const auto object_close = find_matching_brace(text, object_open);
        const std::string object = text.substr(object_open, object_close - object_open + 1);

        SpriteRecord record;
        record.id = id;
        record.asset_slot = string_field(object, "asset_slot");
        record.runtime_status = string_field(object, "runtime_status");
        record.atlas_file = string_field(object, "atlas_file");
        record.estimated = bool_true_field(object, "estimated");
        record.visual_trimmed = string_field(object, "visual_rect") == "alpha_trimmed";
        record.atlas_rect = rect_field(object, "atlas_rect");
        record.trim_rect = rect_field(object, "trim_rect");
        records.push_back(record);
        pos = object_close + 1;
    }
    return records;
}

std::pair<int, int> png_dimensions(const fs::path& path) {
    static constexpr std::array<unsigned char, 8> expected{
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A
    };
    std::array<unsigned char, 24> header{};
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        throw std::runtime_error("cannot open atlas " + path.string());
    }
    in.read(reinterpret_cast<char*>(header.data()), static_cast<std::streamsize>(header.size()));
    if (in.gcount() != static_cast<std::streamsize>(header.size())) {
        throw std::runtime_error("short png header " + path.string());
    }
    if (!std::equal(expected.begin(), expected.end(), header.begin())) {
        throw std::runtime_error("invalid png signature " + path.string());
    }
    const std::string chunk_type(reinterpret_cast<const char*>(&header[12]), 4);
    if (chunk_type != "IHDR") {
        throw std::runtime_error("png missing IHDR " + path.string());
    }
    auto be32 = [&](int offset) {
        return (static_cast<int>(header[offset]) << 24) |
               (static_cast<int>(header[offset + 1]) << 16) |
               (static_cast<int>(header[offset + 2]) << 8) |
               static_cast<int>(header[offset + 3]);
    };
    return {be32(16), be32(20)};
}

void validate_required_slots(const std::set<std::string>& slots) {
    const std::vector<std::string> required = {
        "terrain/exterior", "terrain/water", "street/road", "street/sidewalk",
        "landscape/park", "building/office", "building/apartment", "building/house",
        "building/shop", "building/restaurant", "building/market", "building/bank",
        "building/civic", "building/roof", "overlay/shadow", "prop/facade_kit",
        "landmark/town_hall", "landmark/station", "landmark/hospital",
        "landmark/police", "landmark/school"
    };
    for (const auto& slot : required) {
        if (slots.find(slot) == slots.end()) {
            throw std::runtime_error("required asset slot missing: " + slot);
        }
    }
}

} // namespace

int main(int argc, char** argv) {
    const fs::path asset_root = argc > 1 ? fs::path(argv[1]) : fs::path("assets");
    const fs::path prepared_registry_path = asset_root / "manifests" / "runtime_registry_cpp.json";
    const bool use_prepared_registry = fs::exists(prepared_registry_path);
    const fs::path registry_path = use_prepared_registry
        ? prepared_registry_path
        : asset_root / "manifests" / "sprite_registry.json";
    const fs::path runtime_root = use_prepared_registry
        ? asset_root / "runtime_cpp"
        : asset_root / "runtime";

    try {
        const std::string registry_text = read_text(registry_path);
        const bool registry_v1 = registry_text.find("\"sprite_registry.v1\"") != std::string::npos;
        const bool registry_v2 = registry_text.find("\"runtime_sprite_atlas.v2\"") != std::string::npos;
        if (!registry_v1 && !registry_v2) {
            throw std::runtime_error("unsupported sprite registry schema");
        }

        const auto sprites = parse_sprites(registry_text);
        const int expected_total = int_field(registry_text, "total_sprites", -1);
        if (expected_total >= 0 && expected_total != static_cast<int>(sprites.size())) {
            throw std::runtime_error("total_sprites does not match parsed sprite count");
        }
        const int guard_padding = int_field(registry_text, "guard_padding", registry_v1 ? 0 : -1);
        if (registry_v2 && guard_padding <= 0) {
            throw std::runtime_error("prepared registry must declare positive guard_padding");
        }

        std::set<std::string> slots;
        std::map<std::string, std::pair<int, int>> atlas_dimensions;
        for (const auto& sprite : sprites) {
            if (sprite.id.empty() || sprite.asset_slot.empty()) {
                throw std::runtime_error("sprite has empty id or asset_slot");
            }
            if (sprite.estimated) {
                throw std::runtime_error("estimated sprite rect remains: " + sprite.id);
            }
            if (registry_v1 && sprite.runtime_status != "exported") {
                throw std::runtime_error("sprite is not exported: " + sprite.id);
            }
            if (registry_v1 && !sprite.visual_trimmed) {
                throw std::runtime_error("sprite lacks alpha-trimmed visual rect marker: " + sprite.id);
            }
            if (registry_v2 && (sprite.trim_rect.w <= 0 || sprite.trim_rect.h <= 0)) {
                throw std::runtime_error("prepared sprite lacks trim_rect: " + sprite.id);
            }
            if (sprite.atlas_file.empty()) {
                throw std::runtime_error("sprite has no atlas file: " + sprite.id);
            }
            if (sprite.atlas_rect.w <= 0 || sprite.atlas_rect.h <= 0) {
                throw std::runtime_error("sprite has invalid atlas rect: " + sprite.id);
            }

            const fs::path atlas_path = runtime_root / sprite.atlas_file;
            auto atlas_it = atlas_dimensions.find(sprite.atlas_file);
            if (atlas_it == atlas_dimensions.end()) {
                atlas_it = atlas_dimensions.emplace(sprite.atlas_file, png_dimensions(atlas_path)).first;
            }
            const auto [atlas_w, atlas_h] = atlas_it->second;
            if (sprite.atlas_rect.x < 0 || sprite.atlas_rect.y < 0 ||
                sprite.atlas_rect.x + sprite.atlas_rect.w > atlas_w ||
                sprite.atlas_rect.y + sprite.atlas_rect.h > atlas_h) {
                throw std::runtime_error("sprite atlas rect out of bounds: " + sprite.id);
            }
            slots.insert(sprite.asset_slot);
        }

        validate_required_slots(slots);
        std::cout << "runtime asset registry ok: " << sprites.size()
                  << " sprites, " << atlas_dimensions.size()
                  << " atlases, " << slots.size()
                  << " slots, registry=" << registry_path.string()
                  << "\n";
        return EXIT_SUCCESS;
    } catch (const std::exception& ex) {
        std::cerr << "runtime asset validator failed: " << ex.what() << "\n";
        return EXIT_FAILURE;
    }
}
