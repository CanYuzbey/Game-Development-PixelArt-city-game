cmake_minimum_required(VERSION 3.16)
project(mapping_algorithm_cpp VERSION 0.1.0 LANGUAGES CXX)

add_library(mapping_algorithm
    src/map_generator.cpp
)

target_include_directories(mapping_algorithm
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_compile_features(mapping_algorithm PUBLIC cxx_std_17)

if (MSVC)
    target_compile_options(mapping_algorithm PRIVATE /W4)
else()
    target_compile_options(mapping_algorithm PRIVATE -Wall -Wextra -Wpedantic)
endif()

add_executable(mapping_algorithm_demo examples/demo.cpp)
target_link_libraries(mapping_algorithm_demo PRIVATE mapping_algorithm)

add_executable(mapping_algorithm_smoke tests/smoke.cpp)
target_link_libraries(mapping_algorithm_smoke PRIVATE mapping_algorithm)
