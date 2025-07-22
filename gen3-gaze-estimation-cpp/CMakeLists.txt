cmake_minimum_required(VERSION 3.4)

# Add depthai-core dependency
add_subdirectory(${CMAKE_CURRENT_LIST_DIR}/depthai-core EXCLUDE_FROM_ALL)

# Create a project with name 'gen3'
set(TARGET_NAME gen3)
project(${TARGET_NAME})

# Dependencies (optional, only used for example)
find_package(OpenCV REQUIRED)

# Add source files
add_executable("${TARGET_NAME}"
    src/main.cpp
)

# Link with libraries
target_link_libraries(${TARGET_NAME}
    PUBLIC
        depthai::core
        ${OpenCV_LIBS} # optional, used for example
)

# Copy files to /build 
file(COPY script.py DESTINATION "${CMAKE_CURRENT_BINARY_DIR}")
file(COPY face-detection-retail-0004.blob DESTINATION "${CMAKE_CURRENT_BINARY_DIR}")
file(COPY gaze-estimation-adas-0002.blob DESTINATION "${CMAKE_CURRENT_BINARY_DIR}")
file(COPY head-pose-estimation-adas-0001.blob DESTINATION "${CMAKE_CURRENT_BINARY_DIR}")
file(COPY landmarks-regression-retail-0009.blob DESTINATION "${CMAKE_CURRENT_BINARY_DIR}")


# Set some errors
if(NOT MSVC)
    target_compile_options(${TARGET_NAME} PRIVATE $<$<COMPILE_LANGUAGE:CXX>:-Werror=return-type>)
endif()

# Set compiler features (c++14)
set_property(TARGET ${TARGET_NAME} PROPERTY CXX_STANDARD 17)


# Windows - Add runtime dependencies
if(WIN32)
    if(CMAKE_VERSION VERSION_LESS "3.21")
        message(WARNING "CMake version less than 3.21 - automatic DLL handling not available. Make sure to copy required DLLs to the same folder as .exe")
    else()
        # TARGET_RUNTIME_DLLS generator expression available since CMake 3.21
        set(depthai_dll_libraries "$<TARGET_RUNTIME_DLLS:${TARGET_NAME}>")
        # Copy the required dlls
        add_custom_command(TARGET ${TARGET_NAME} POST_BUILD COMMAND
            ${CMAKE_COMMAND} -E copy_if_different ${depthai_dll_libraries} $<TARGET_FILE_DIR:${TARGET_NAME}>
            COMMAND_EXPAND_LISTS
        )
    endif()
endif()
