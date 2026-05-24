cmake_minimum_required(VERSION 3.16)
project(mapping_design_cpp VERSION 0.1.0 LANGUAGES CXX)

add_executable(mapping_asset_validator tools/asset_validator.cpp)
target_compile_features(mapping_asset_validator PRIVATE cxx_std_17)

if (MSVC)
    target_compile_options(mapping_asset_validator PRIVATE /W4)
else()
    target_compile_options(mapping_asset_validator PRIVATE -Wall -Wextra -Wpedantic)
endif()
