# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Luxonis, Inc.
# 
# Contact: <support@luxonis.com>

cmake_minimum_required(VERSION 3.20)

project(uvc_example LANGUAGES C CXX)

add_subdirectory(uvc-gadget)

find_package(depthai REQUIRED)
message(STATUS "Found depthai: ${depthai_DIR}")

add_executable(uvc_example
    src/uvc_controls.cpp
    src/uvc_example.cpp
)

target_compile_features(uvc_example PRIVATE cxx_std_17)

target_link_libraries(uvc_example PRIVATE
    depthai::core
    uvcgadget
)
