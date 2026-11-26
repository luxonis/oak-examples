cmake_minimum_required(VERSION 3.20)
project(nvidia_holoscan_cpp VERSION 1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(HSB_BUILD_RGB_STREAM "Build rgb_stream DepthAI example" ON)
option(HSB_FETCH_HOLOLINK "Fetch holoscan-sensor-bridge when HSB_SOURCE_DIR is not set" ON)
option(HSB_FETCH_DLPACK "Download dlpack header if not found locally" ON)

set(HSB_SOURCE_DIR "" CACHE PATH "Path to a holoscan-sensor-bridge checkout")
set(HSB_REPO_URL "https://github.com/nvidia-holoscan/holoscan-sensor-bridge.git" CACHE STRING "holoscan-sensor-bridge Git URL")
set(HSB_REPO_TAG "6930609c4ce264ec7e2936dd1f5813323fccb08e" CACHE STRING "holoscan-sensor-bridge commit/tag")

if(HSB_SOURCE_DIR)
    set(_hsb_root "${HSB_SOURCE_DIR}")
elseif(HSB_FETCH_HOLOLINK)
    include(FetchContent)
    FetchContent_Declare(holoscan_sensor_bridge
        GIT_REPOSITORY "${HSB_REPO_URL}"
        GIT_TAG "${HSB_REPO_TAG}"
        GIT_SHALLOW TRUE
    )
    FetchContent_GetProperties(holoscan_sensor_bridge)
    if(NOT holoscan_sensor_bridge_POPULATED)
        FetchContent_Populate(holoscan_sensor_bridge)
    endif()
    set(_hsb_root "${holoscan_sensor_bridge_SOURCE_DIR}")
else()
    message(FATAL_ERROR
        "HSB_SOURCE_DIR is empty and HSB_FETCH_HOLOLINK=OFF.\n"
        "Set HSB_SOURCE_DIR to your holoscan-sensor-bridge checkout."
    )
endif()

set(_hsb_emulation_dir "${_hsb_root}/src/hololink/emulation")
if(NOT EXISTS "${_hsb_emulation_dir}/hsb_emulator.hpp")
    message(FATAL_ERROR
        "HSB emulation sources not found. Expected:\n"
        "  ${_hsb_emulation_dir}/hsb_emulator.hpp"
    )
endif()

set(HOLOLINK_EMULATION_SOURCES
    "${_hsb_emulation_dir}/base_transmitter.cpp"
    "${_hsb_emulation_dir}/data_plane.cpp"
    "${_hsb_emulation_dir}/hsb_config.cpp"
    "${_hsb_emulation_dir}/hsb_emulator.cpp"
    "${_hsb_emulation_dir}/mem_register.cpp"
    "${_hsb_emulation_dir}/net.cpp"
    "${_hsb_emulation_dir}/utils.cpp"
)

find_path(DLPACK_INCLUDE_DIR dlpack/dlpack.h
    HINTS
        "${_hsb_root}/build/_deps/dlpack/include"
)
if(NOT EXISTS "${DLPACK_INCLUDE_DIR}/dlpack/dlpack.h")
    if(HSB_FETCH_DLPACK)
        set(_dlpack_dir "${CMAKE_BINARY_DIR}/_deps/dlpack/include/dlpack")
        file(MAKE_DIRECTORY "${_dlpack_dir}")
        file(DOWNLOAD
            "https://raw.githubusercontent.com/dmlc/dlpack/v1.0/include/dlpack/dlpack.h"
            "${_dlpack_dir}/dlpack.h"
            STATUS _dlpack_status
            SHOW_PROGRESS
        )
        list(GET _dlpack_status 0 _dlpack_status_code)
        if(_dlpack_status_code EQUAL 0)
            set(DLPACK_INCLUDE_DIR "${CMAKE_BINARY_DIR}/_deps/dlpack/include")
        endif()
    endif()
endif()
if(NOT EXISTS "${DLPACK_INCLUDE_DIR}/dlpack/dlpack.h")
    message(FATAL_ERROR
        "dlpack/dlpack.h not found.\n"
        "Install dlpack headers, set DLPACK_INCLUDE_DIR, or enable HSB_FETCH_DLPACK."
    )
endif()

add_library(hololink_emulation STATIC ${HOLOLINK_EMULATION_SOURCES})
target_include_directories(hololink_emulation
    PUBLIC
        "${_hsb_root}/src"
        "${_hsb_emulation_dir}"
        "${DLPACK_INCLUDE_DIR}"
)
target_link_libraries(hololink_emulation PUBLIC pthread)

if(HSB_BUILD_RGB_STREAM)
    find_package(ZLIB REQUIRED)
    find_package(CUDAToolkit REQUIRED)
    find_package(depthai REQUIRED)
    find_package(OpenCV REQUIRED COMPONENTS core highgui imgproc)

    add_library(hololink_emulation_roce STATIC
        "${_hsb_emulation_dir}/linux_data_plane.cpp"
        "${_hsb_emulation_dir}/linux_transmitter.cpp"
    )
    target_include_directories(hololink_emulation_roce
        PUBLIC
            "${_hsb_root}/src"
            "${_hsb_emulation_dir}"
            "${DLPACK_INCLUDE_DIR}"
    )
    target_link_libraries(hololink_emulation_roce
        PUBLIC
            hololink_emulation
            ZLIB::ZLIB
            CUDA::cudart
    )

    add_executable(rgb_stream rgb_stream.cpp)
    target_link_libraries(rgb_stream
        PRIVATE
            depthai::core
            hololink_emulation
            hololink_emulation_roce
            ${OpenCV_LIBS}
    )
    target_compile_options(rgb_stream PRIVATE -Wno-psabi)
endif()
