cmake_minimum_required(VERSION 3.16)
project(mapping_algorithm_cpp VERSION 0.1.0 LANGUAGES CXX)

enable_testing()

add_library(mapping_algorithm
    src/map_generator.cpp
    src/world_generator.cpp
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

add_executable(mapping_city_exporter tools/city_exporter.cpp)
target_link_libraries(mapping_city_exporter PRIVATE mapping_algorithm)

add_executable(mapping_algorithm_smoke tests/smoke.cpp)
target_link_libraries(mapping_algorithm_smoke PRIVATE mapping_algorithm)

add_test(NAME mapping_algorithm_smoke COMMAND $<TARGET_FILE:mapping_algorithm_smoke>)

add_test(
    NAME mapping_city_exporter_exports_seed
    COMMAND $<TARGET_FILE:mapping_city_exporter>
        --seed 1
        --width 96
        --height 72
        --profile generic_dense
        --coast none
        --out "${CMAKE_CURRENT_BINARY_DIR}/ctest_city_seed_1.json"
)
set_tests_properties(
    mapping_city_exporter_exports_seed
    PROPERTIES PASS_REGULAR_EXPRESSION "exported"
)

add_test(
    NAME mapping_city_exporter_reject_bad_coast
    COMMAND ${CMAKE_COMMAND}
        -DEXPORTER=$<TARGET_FILE:mapping_city_exporter>
        -DARG_NAME=--coast
        -DARG_VALUE=wets
        "-DEXPECTED_TEXT=unknown coast side"
        -P "${CMAKE_CURRENT_SOURCE_DIR}/tests/expect_exporter_failure.cmake"
)
add_test(
    NAME mapping_city_exporter_reject_bad_profile
    COMMAND ${CMAKE_COMMAND}
        -DEXPORTER=$<TARGET_FILE:mapping_city_exporter>
        -DARG_NAME=--profile
        -DARG_VALUE=unknown_profile
        "-DEXPECTED_TEXT=unknown profile"
        -P "${CMAKE_CURRENT_SOURCE_DIR}/tests/expect_exporter_failure.cmake"
)
