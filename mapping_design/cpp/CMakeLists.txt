cmake_minimum_required(VERSION 3.16)
project(mapping_design_cpp VERSION 0.1.0 LANGUAGES CXX)

add_executable(mapping_asset_validator tools/asset_validator.cpp)
target_compile_features(mapping_asset_validator PRIVATE cxx_std_17)

add_executable(mapping_runtime_asset_validator tools/runtime_asset_validator.cpp)
target_compile_features(mapping_runtime_asset_validator PRIVATE cxx_std_17)

add_executable(mapping_runtime_asset_preparer tools/runtime_asset_preparer_win.cpp)
target_compile_features(mapping_runtime_asset_preparer PRIVATE cxx_std_17)
if (WIN32)
    target_link_libraries(mapping_runtime_asset_preparer PRIVATE windowscodecs ole32)
endif()

if (MSVC)
    target_compile_options(mapping_asset_validator PRIVATE /W4)
    target_compile_options(mapping_runtime_asset_validator PRIVATE /W4)
    target_compile_options(mapping_runtime_asset_preparer PRIVATE /W4)
else()
    target_compile_options(mapping_asset_validator PRIVATE -Wall -Wextra -Wpedantic)
    target_compile_options(mapping_runtime_asset_validator PRIVATE -Wall -Wextra -Wpedantic)
    target_compile_options(mapping_runtime_asset_preparer PRIVATE -Wall -Wextra -Wpedantic)
endif()
