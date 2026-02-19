cmake_minimum_required(VERSION 3.20)
project(camera_stream LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(depthai REQUIRED)

add_executable(main src/main.cpp)
target_link_libraries(main PRIVATE depthai::core)
target_compile_options(main PRIVATE -Wno-psabi)