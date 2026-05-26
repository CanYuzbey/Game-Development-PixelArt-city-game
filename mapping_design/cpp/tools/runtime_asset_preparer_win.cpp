#ifdef _WIN32

#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <wincodec.h>
#include <wrl/client.h>

#include <algorithm>
#include <cctype>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <map>
#include <regex>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace fs = std::filesystem;
using Microsoft::WRL::ComPtr;

namespace {

constexpr int kAtlasWidth = 2048;
constexpr int kGuardPadding = 4;
constexpr int kShelfGap = 2;

struct Rect {
    int x = 0;
    int y = 0;
    int w = 0;
    int h = 0;
};

struct Image {
    int width = 0;
    int height = 0;
    std::vector<std::uint8_t> rgba;
};

struct SpriteSource {
    std::string id;
    std::string source_sheet;
    std::string asset_slot;
    std::string atlas_file;
    Rect pixel_rect;
};

struct PreparedSprite {
    SpriteSource source;
    Image image;
    Rect trim_rect;
    Rect atlas_rect;
};

struct Rgba {
    std::uint8_t r = 0;
    std::uint8_t g = 0;
    std::uint8_t b = 0;
    std::uint8_t a = 255;
};

void check_hr(HRESULT hr, const char* operation) {
    if (FAILED(hr)) {
        std::ostringstream out;
        out << operation << " failed: HRESULT=0x" << std::hex << static_cast<unsigned long>(hr);
        throw std::runtime_error(out.str());
    }
}

std::string read_text(const fs::path& path) {
    std::ifstream in(path);
    if (!in) {
        throw std::runtime_error("cannot open " + path.string());
    }
    return std::string(std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>());
}

std::string escape_json(const std::string& value) {
    std::ostringstream out;
    for (const char ch : value) {
        switch (ch) {
            case '\\': out << "\\\\"; break;
            case '"': out << "\\\""; break;
            case '\n': out << "\\n"; break;
            case '\r': out << "\\r"; break;
            case '\t': out << "\\t"; break;
            default: out << ch; break;
        }
    }
    return out.str();
}

std::string string_field(const std::string& object, const std::string& field) {
    const std::regex pattern("\"" + field + "\"\\s*:\\s*\"([^\"]*)\"");
    std::smatch match;
    if (!std::regex_search(object, match, pattern)) {
        return {};
    }
    return match[1].str();
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

std::vector<SpriteSource> parse_sprite_sources(const std::string& text) {
    const auto sprites_key = text.find("\"sprites\"");
    if (sprites_key == std::string::npos) {
        throw std::runtime_error("registry has no sprites object");
    }
    const auto sprites_open = text.find('{', sprites_key);
    if (sprites_open == std::string::npos) {
        throw std::runtime_error("registry sprites object is malformed");
    }
    const auto sprites_close = find_matching_brace(text, sprites_open);

    std::vector<SpriteSource> sprites;
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
        const auto object_close = find_matching_brace(text, object_open);
        const std::string object = text.substr(object_open, object_close - object_open + 1);

        SpriteSource sprite;
        sprite.id = id;
        sprite.source_sheet = string_field(object, "source_sheet");
        sprite.asset_slot = string_field(object, "asset_slot");
        sprite.atlas_file = string_field(object, "atlas_file");
        sprite.pixel_rect = rect_field(object, "pixel_rect");
        if (sprite.atlas_file.empty()) {
            sprite.atlas_file = sprite.asset_slot;
            std::replace(sprite.atlas_file.begin(), sprite.atlas_file.end(), '/', '_');
            sprite.atlas_file += ".atlas.png";
        }
        if (sprite.source_sheet.empty() || sprite.asset_slot.empty() || sprite.pixel_rect.w <= 0 || sprite.pixel_rect.h <= 0) {
            throw std::runtime_error("sprite is missing required source metadata: " + id);
        }
        sprites.push_back(sprite);
        pos = object_close + 1;
    }
    return sprites;
}

Image load_png(IWICImagingFactory* factory, const fs::path& path) {
    ComPtr<IWICBitmapDecoder> decoder;
    check_hr(factory->CreateDecoderFromFilename(path.wstring().c_str(), nullptr, GENERIC_READ,
                                                WICDecodeMetadataCacheOnLoad, &decoder),
             "CreateDecoderFromFilename");

    ComPtr<IWICBitmapFrameDecode> frame;
    check_hr(decoder->GetFrame(0, &frame), "GetFrame");

    UINT width = 0;
    UINT height = 0;
    check_hr(frame->GetSize(&width, &height), "GetSize");

    ComPtr<IWICFormatConverter> converter;
    check_hr(factory->CreateFormatConverter(&converter), "CreateFormatConverter");
    check_hr(converter->Initialize(frame.Get(), GUID_WICPixelFormat32bppRGBA, WICBitmapDitherTypeNone,
                                   nullptr, 0.0, WICBitmapPaletteTypeCustom),
             "FormatConverter::Initialize");

    Image image;
    image.width = static_cast<int>(width);
    image.height = static_cast<int>(height);
    image.rgba.resize(static_cast<std::size_t>(image.width) * static_cast<std::size_t>(image.height) * 4U);
    check_hr(converter->CopyPixels(nullptr, static_cast<UINT>(image.width * 4),
                                   static_cast<UINT>(image.rgba.size()), image.rgba.data()),
             "CopyPixels");
    return image;
}

void save_png(IWICImagingFactory* factory, const fs::path& path, const Image& image) {
    fs::create_directories(path.parent_path());

    ComPtr<IWICStream> stream;
    check_hr(factory->CreateStream(&stream), "CreateStream");
    check_hr(stream->InitializeFromFilename(path.wstring().c_str(), GENERIC_WRITE), "InitializeFromFilename");

    ComPtr<IWICBitmapEncoder> encoder;
    check_hr(factory->CreateEncoder(GUID_ContainerFormatPng, nullptr, &encoder), "CreateEncoder");
    check_hr(encoder->Initialize(stream.Get(), WICBitmapEncoderNoCache), "Encoder::Initialize");

    ComPtr<IWICBitmapFrameEncode> frame;
    ComPtr<IPropertyBag2> properties;
    check_hr(encoder->CreateNewFrame(&frame, &properties), "CreateNewFrame");
    check_hr(frame->Initialize(properties.Get()), "Frame::Initialize");
    check_hr(frame->SetSize(static_cast<UINT>(image.width), static_cast<UINT>(image.height)), "Frame::SetSize");

    WICPixelFormatGUID format = GUID_WICPixelFormat32bppBGRA;
    check_hr(frame->SetPixelFormat(&format), "Frame::SetPixelFormat");
    if (!IsEqualGUID(format, GUID_WICPixelFormat32bppBGRA)) {
        throw std::runtime_error("PNG encoder did not accept 32bpp BGRA");
    }

    std::vector<std::uint8_t> bgra(image.rgba.size(), 0);
    for (std::size_t i = 0; i < image.rgba.size(); i += 4U) {
        bgra[i + 0U] = image.rgba[i + 2U];
        bgra[i + 1U] = image.rgba[i + 1U];
        bgra[i + 2U] = image.rgba[i + 0U];
        bgra[i + 3U] = image.rgba[i + 3U];
    }
    check_hr(frame->WritePixels(static_cast<UINT>(image.height), static_cast<UINT>(image.width * 4),
                                static_cast<UINT>(bgra.size()),
                                reinterpret_cast<BYTE*>(bgra.data())),
             "Frame::WritePixels");
    check_hr(frame->Commit(), "Frame::Commit");
    check_hr(encoder->Commit(), "Encoder::Commit");
}

std::uint8_t alpha_at(const Image& image, int x, int y) {
    return image.rgba[(static_cast<std::size_t>(y) * image.width + x) * 4U + 3U];
}

void set_pixel(Image& image, int x, int y, Rgba color) {
    if (x < 0 || y < 0 || x >= image.width || y >= image.height) {
        return;
    }
    const std::size_t offset = (static_cast<std::size_t>(y) * image.width + x) * 4U;
    image.rgba[offset + 0U] = color.r;
    image.rgba[offset + 1U] = color.g;
    image.rgba[offset + 2U] = color.b;
    image.rgba[offset + 3U] = color.a;
}

void draw_disk(Image& image, int cx, int cy, int radius, Rgba color) {
    const int rr = radius * radius;
    for (int y = cy - radius; y <= cy + radius; ++y) {
        for (int x = cx - radius; x <= cx + radius; ++x) {
            const int dx = x - cx;
            const int dy = y - cy;
            if (dx * dx + dy * dy <= rr) {
                set_pixel(image, x, y, color);
            }
        }
    }
}

void draw_line(Image& image, int x0, int y0, int x1, int y1, int radius, Rgba color) {
    int dx = std::abs(x1 - x0);
    int sx = x0 < x1 ? 1 : -1;
    int dy = -std::abs(y1 - y0);
    int sy = y0 < y1 ? 1 : -1;
    int err = dx + dy;
    while (true) {
        draw_disk(image, x0, y0, radius, color);
        if (x0 == x1 && y0 == y1) {
            break;
        }
        const int e2 = 2 * err;
        if (e2 >= dy) {
            err += dy;
            x0 += sx;
        }
        if (e2 <= dx) {
            err += dx;
            y0 += sy;
        }
    }
}

bool in_diamond(int x, int y, int left, int top, int width, int height) {
    const int cx = left + width / 2;
    const int cy = top + height / 2;
    const int hw = width / 2;
    const int hh = height / 2;
    return std::abs(x - cx) * hh + std::abs(y - cy) * hw <= hw * hh;
}

Rgba shade(Rgba color, int delta) {
    auto clamp_channel = [](int value) {
        return static_cast<std::uint8_t>(std::clamp(value, 0, 255));
    };
    return {
        clamp_channel(static_cast<int>(color.r) + delta),
        clamp_channel(static_cast<int>(color.g) + delta),
        clamp_channel(static_cast<int>(color.b) + delta),
        color.a
    };
}

Image make_procedural_tile(bool sidewalk, int bitmask) {
    constexpr int visual_w = 192;
    constexpr int visual_h = 128;
    Image image;
    image.width = visual_w + kGuardPadding * 2;
    image.height = visual_h + kGuardPadding * 2;
    image.rgba.assign(static_cast<std::size_t>(image.width) * static_cast<std::size_t>(image.height) * 4U, 0);

    const int left = kGuardPadding;
    const int top = kGuardPadding;
    const int cx = left + visual_w / 2;
    const int cy = top + visual_h / 2;
    const Rgba base = sidewalk ? Rgba{142, 132, 116, 255} : Rgba{70, 66, 60, 255};
    const Rgba edge = sidewalk ? Rgba{104, 98, 88, 255} : Rgba{42, 40, 38, 255};
    const Rgba line = sidewalk ? Rgba{168, 158, 140, 255} : Rgba{214, 188, 82, 255};

    for (int y = top; y < top + visual_h; ++y) {
        for (int x = left; x < left + visual_w; ++x) {
            if (!in_diamond(x, y, left, top, visual_w, visual_h)) {
                continue;
            }
            const int texture = ((x / 7 + y / 5 + bitmask) % 5 == 0) ? 6 : 0;
            set_pixel(image, x, y, shade(base, texture));
        }
    }

    draw_line(image, left, cy, left + visual_w / 2, top, 1, edge);
    draw_line(image, left + visual_w / 2, top, left + visual_w - 1, cy, 1, edge);
    draw_line(image, left + visual_w - 1, cy, left + visual_w / 2, top + visual_h - 1, 1, edge);
    draw_line(image, left + visual_w / 2, top + visual_h - 1, left, cy, 1, edge);

    if (sidewalk) {
        for (int offset = -72; offset <= 72; offset += 24) {
            draw_line(image, cx + offset, cy - 40, cx + offset + 72, cy + 8, 1, shade(base, -14));
            draw_line(image, cx + offset, cy + 40, cx + offset + 72, cy - 8, 1, shade(base, -14));
        }
    } else {
        if ((bitmask & 8) != 0) draw_line(image, cx, cy, cx, top + 12, 2, line);
        if ((bitmask & 2) != 0) draw_line(image, cx, cy, cx, top + visual_h - 13, 2, line);
        if ((bitmask & 1) != 0) draw_line(image, cx, cy, left + 14, cy, 2, line);
        if ((bitmask & 4) != 0) draw_line(image, cx, cy, left + visual_w - 15, cy, 2, line);
        draw_disk(image, cx, cy, bitmask == 15 ? 9 : 5, shade(line, 10));
    }

    return image;
}

void add_procedural_street_tiles(std::map<std::string, std::vector<PreparedSprite>>& groups) {
    auto add_tile = [&](const std::string& id, const std::string& slot, bool sidewalk, int bitmask) {
        PreparedSprite sprite;
        sprite.source.id = id;
        sprite.source.source_sheet = "procedural_cpp";
        sprite.source.asset_slot = slot;
        sprite.source.atlas_file = "streets_orthogonal.atlas.png";
        sprite.source.pixel_rect = {0, 0, 192, 128};
        sprite.trim_rect = {kGuardPadding, kGuardPadding, 192, 128};
        sprite.image = make_procedural_tile(sidewalk, bitmask);
        groups[sprite.source.atlas_file].push_back(std::move(sprite));
    };

    for (int bitmask = 0; bitmask < 16; ++bitmask) {
        std::ostringstream road_id;
        road_id << "road_bitmask_";
        if (bitmask < 10) {
            road_id << '0';
        }
        road_id << bitmask;
        add_tile(road_id.str(), "street/road", false, bitmask);

        std::ostringstream sidewalk_id;
        sidewalk_id << "sidewalk_bitmask_";
        if (bitmask < 10) {
            sidewalk_id << '0';
        }
        sidewalk_id << bitmask;
        add_tile(sidewalk_id.str(), "street/sidewalk", true, bitmask);
    }
}

Image crop_alpha_trimmed(const Image& sheet, const Rect& rect, Rect& trim_rect) {
    const int x0 = std::clamp(rect.x, 0, sheet.width - 1);
    const int y0 = std::clamp(rect.y, 0, sheet.height - 1);
    const int x1 = std::clamp(rect.x + rect.w, 0, sheet.width);
    const int y1 = std::clamp(rect.y + rect.h, 0, sheet.height);
    if (x1 <= x0 || y1 <= y0) {
        throw std::runtime_error("sprite crop is outside source sheet");
    }

    int min_x = x1;
    int min_y = y1;
    int max_x = x0 - 1;
    int max_y = y0 - 1;
    for (int y = y0; y < y1; ++y) {
        for (int x = x0; x < x1; ++x) {
            if (alpha_at(sheet, x, y) != 0) {
                min_x = std::min(min_x, x);
                min_y = std::min(min_y, y);
                max_x = std::max(max_x, x);
                max_y = std::max(max_y, y);
            }
        }
    }
    if (max_x < min_x || max_y < min_y) {
        min_x = x0;
        min_y = y0;
        max_x = x0;
        max_y = y0;
    }

    trim_rect = {min_x - rect.x, min_y - rect.y, max_x - min_x + 1, max_y - min_y + 1};
    Image out;
    out.width = trim_rect.w + kGuardPadding * 2;
    out.height = trim_rect.h + kGuardPadding * 2;
    out.rgba.assign(static_cast<std::size_t>(out.width) * static_cast<std::size_t>(out.height) * 4U, 0);

    for (int y = 0; y < trim_rect.h; ++y) {
        for (int x = 0; x < trim_rect.w; ++x) {
            const std::size_t src = (static_cast<std::size_t>(min_y + y) * sheet.width + (min_x + x)) * 4U;
            const std::size_t dst = (static_cast<std::size_t>(y + kGuardPadding) * out.width + (x + kGuardPadding)) * 4U;
            out.rgba[dst + 0] = sheet.rgba[src + 0];
            out.rgba[dst + 1] = sheet.rgba[src + 1];
            out.rgba[dst + 2] = sheet.rgba[src + 2];
            out.rgba[dst + 3] = sheet.rgba[src + 3];
        }
    }
    return out;
}

Image make_atlas(std::vector<PreparedSprite>& sprites) {
    int x = 0;
    int y = 0;
    int row_h = 0;
    int atlas_h = 0;
    for (auto& sprite : sprites) {
        if (sprite.image.width > kAtlasWidth) {
            throw std::runtime_error("sprite wider than atlas width: " + sprite.source.id);
        }
        if (x != 0 && x + sprite.image.width > kAtlasWidth) {
            y += row_h + kShelfGap;
            x = 0;
            row_h = 0;
        }
        sprite.atlas_rect = {x, y, sprite.image.width, sprite.image.height};
        x += sprite.image.width + kShelfGap;
        row_h = std::max(row_h, sprite.image.height);
        atlas_h = std::max(atlas_h, y + row_h);
    }

    Image atlas;
    atlas.width = kAtlasWidth;
    atlas.height = std::max(1, atlas_h);
    atlas.rgba.assign(static_cast<std::size_t>(atlas.width) * static_cast<std::size_t>(atlas.height) * 4U, 0);
    for (const auto& sprite : sprites) {
        for (int sy = 0; sy < sprite.image.height; ++sy) {
            for (int sx = 0; sx < sprite.image.width; ++sx) {
                const std::size_t src = (static_cast<std::size_t>(sy) * sprite.image.width + sx) * 4U;
                const std::size_t dst = (static_cast<std::size_t>(sprite.atlas_rect.y + sy) * atlas.width +
                                         (sprite.atlas_rect.x + sx)) * 4U;
                atlas.rgba[dst + 0] = sprite.image.rgba[src + 0];
                atlas.rgba[dst + 1] = sprite.image.rgba[src + 1];
                atlas.rgba[dst + 2] = sprite.image.rgba[src + 2];
                atlas.rgba[dst + 3] = sprite.image.rgba[src + 3];
            }
        }
    }
    return atlas;
}

void write_runtime_manifest(const fs::path& path, const std::map<std::string, std::vector<PreparedSprite>>& groups) {
    fs::create_directories(path.parent_path());
    std::ofstream out(path);
    if (!out) {
        throw std::runtime_error("cannot write manifest " + path.string());
    }

    out << "{\n"
        << "  \"schema\": \"runtime_sprite_atlas.v2\",\n"
        << "  \"guard_padding\": " << kGuardPadding << ",\n"
        << "  \"atlas_width\": " << kAtlasWidth << ",\n"
        << "  \"sprites\": {\n";

    bool first = true;
    for (const auto& [atlas_file, sprites] : groups) {
        for (const auto& sprite : sprites) {
            if (!first) {
                out << ",\n";
            }
            first = false;
            out << "    \"" << escape_json(sprite.source.id) << "\": {"
                << "\"asset_slot\": \"" << escape_json(sprite.source.asset_slot) << "\", "
                << "\"atlas_file\": \"" << escape_json(atlas_file) << "\", "
                << "\"atlas_rect\": [" << sprite.atlas_rect.x << ", " << sprite.atlas_rect.y
                << ", " << sprite.atlas_rect.w << ", " << sprite.atlas_rect.h << "], "
                << "\"trim_rect\": [" << sprite.trim_rect.x << ", " << sprite.trim_rect.y
                << ", " << sprite.trim_rect.w << ", " << sprite.trim_rect.h << "]}";
        }
    }

    out << "\n  }\n}\n";
}

} // namespace

int main(int argc, char** argv) {
    const fs::path asset_root = argc > 1 ? fs::path(argv[1]) : fs::path("assets");
    const fs::path registry_path = asset_root / "manifests" / "sprite_registry.json";
    const fs::path source_root = asset_root / "source_rgba";
    const fs::path runtime_root = asset_root / "runtime_cpp";
    const fs::path output_manifest = asset_root / "manifests" / "runtime_registry_cpp.json";

    HRESULT hr = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
    if (FAILED(hr)) {
        std::cerr << "COM initialization failed\n";
        return EXIT_FAILURE;
    }

    try {
        std::size_t sprite_count = 0;
        std::size_t atlas_count = 0;
        {
            ComPtr<IWICImagingFactory> factory;
            check_hr(CoCreateInstance(CLSID_WICImagingFactory, nullptr, CLSCTX_INPROC_SERVER,
                                      IID_PPV_ARGS(&factory)),
                     "CoCreateInstance(CLSID_WICImagingFactory)");

            const auto sources = parse_sprite_sources(read_text(registry_path));
            std::map<std::string, Image> sheet_cache;
            std::map<std::string, std::vector<PreparedSprite>> groups;

            for (const auto& source : sources) {
                auto sheet_it = sheet_cache.find(source.source_sheet);
                if (sheet_it == sheet_cache.end()) {
                    const fs::path sheet_path = source_root / (source.source_sheet + ".png");
                    sheet_it = sheet_cache.emplace(source.source_sheet, load_png(factory.Get(), sheet_path)).first;
                }

                PreparedSprite prepared;
                prepared.source = source;
                prepared.image = crop_alpha_trimmed(sheet_it->second, source.pixel_rect, prepared.trim_rect);
                groups[source.atlas_file].push_back(std::move(prepared));
            }
            add_procedural_street_tiles(groups);

            for (auto& [atlas_file, sprites] : groups) {
                auto atlas = make_atlas(sprites);
                save_png(factory.Get(), runtime_root / atlas_file, atlas);
            }
            write_runtime_manifest(output_manifest, groups);

            for (const auto& [unused, sprites] : groups) {
                sprite_count += sprites.size();
            }
            atlas_count = groups.size();
        }

        CoUninitialize();
        std::cout << "runtime assets prepared: " << sprite_count
                  << " sprites, " << atlas_count
                  << " atlases, output=" << runtime_root.string()
                  << "\n";
        return EXIT_SUCCESS;
    } catch (const std::exception& ex) {
        CoUninitialize();
        std::cerr << "runtime asset preparer failed: " << ex.what() << "\n";
        return EXIT_FAILURE;
    }
}

#else

#include <cstdlib>
#include <iostream>

int main() {
    std::cerr << "mapping_runtime_asset_preparer is implemented with Windows Imaging Component and must run on Windows.\n";
    return EXIT_FAILURE;
}

#endif
