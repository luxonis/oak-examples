cmake_minimum_required(VERSION 3.20)

project(camera_stream VERSION 1.0 LANGUAGES CXX)

# Use C++17 standard
set(CMAKE_CXX_STANDARD 17)


# Depthai dependency
find_package(depthai REQUIRED)
message(STATUS "Found depthai: ${depthai_DIR}")

# Add source files
add_executable(main src/main.cpp)

# Link with libraries
target_link_libraries(main PUBLIC depthai::core)

# Suppress warnings about C++17 ABI in GCC 10.1+
target_compile_options(main PRIVATE -Wno-psabi)
