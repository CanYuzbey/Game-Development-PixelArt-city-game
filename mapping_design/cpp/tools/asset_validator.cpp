#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <regex>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;

namespace {

bool has_png_signature(const fs::path& path) {
    static constexpr unsigned char expected[8] = {
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A
    };
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        return false;
    }
    unsigned char actual[8] = {};
    in.read(reinterpret_cast<char*>(actual), sizeof(actual));
    if (in.gcount() != static_cast<std::streamsize>(sizeof(actual))) {
        return false;
    }
    for (std::size_t i = 0; i < sizeof(actual); ++i) {
        if (actual[i] != expected[i]) {
            return false;
        }
    }
    return true;
}

std::string read_text(const fs::path& path) {
    std::ifstream in(path);
    if (!in) {
        throw std::runtime_error("cannot open " + path.string());
    }
    return std::string(std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>());
}

std::vector<std::string> manifest_files(const std::string& manifest_text) {
    std::vector<std::string> files;
    const std::regex file_pattern("\"file\"\\s*:\\s*\"([^\"]+)\"");
    for (std::sregex_iterator it(manifest_text.begin(), manifest_text.end(), file_pattern), end;
         it != end;
         ++it) {
        files.push_back((*it)[1].str());
    }
    return files;
}

} // namespace

int main(int argc, char** argv) {
    const fs::path root = argc > 1 ? fs::path(argv[1]) : fs::path("mapping_design/assets");
    const fs::path manifest = root / "asset_manifest.json";

    try {
        const std::string text = read_text(manifest);
        if (text.find("\"schema\"") == std::string::npos ||
            text.find("existing_city_assets.v1") == std::string::npos) {
            std::cerr << "manifest schema missing or unsupported\n";
            return EXIT_FAILURE;
        }

        const auto files = manifest_files(text);
        if (files.empty()) {
            std::cerr << "manifest has no raw sheet file entries\n";
            return EXIT_FAILURE;
        }

        int checked = 0;
        for (const auto& file : files) {
            const fs::path asset_path = root / fs::path(file);
            if (!fs::exists(asset_path)) {
                std::cerr << "missing asset: " << asset_path.string() << "\n";
                return EXIT_FAILURE;
            }
            if (asset_path.extension() == ".png" && !has_png_signature(asset_path)) {
                std::cerr << "invalid png signature: " << asset_path.string() << "\n";
                return EXIT_FAILURE;
            }
            ++checked;
        }

        std::cout << "asset manifest ok: " << checked << " raw sheets checked\n";
        return EXIT_SUCCESS;
    } catch (const std::exception& ex) {
        std::cerr << "asset validator failed: " << ex.what() << "\n";
        return EXIT_FAILURE;
    }
}
