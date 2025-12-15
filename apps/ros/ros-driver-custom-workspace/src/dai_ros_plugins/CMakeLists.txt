cmake_minimum_required(VERSION 3.20)
project(dai_ros_plugins)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_ros REQUIRED)
find_package(depthai_ros_driver REQUIRED)
find_package(pluginlib REQUIRED)

add_library(dai_ros_plugins src/dai_ros_plugins.cpp)
add_library(dai_ros_plugins::dai_ros_plugins ALIAS dai_ros_plugins)
target_compile_features(dai_ros_plugins PUBLIC c_std_99 cxx_std_17)  # Require C99 and C++17
target_include_directories(dai_ros_plugins PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include/${PROJECT_NAME}>)
target_link_libraries(
  dai_ros_plugins PUBLIC
  ${depthai_ros_driver_TARGETS}
  ${pluginlib_TARGETS}
)

# Causes the visibility macros to use dllexport rather than dllimport,
# which is appropriate when building the dll but not consuming it.
target_compile_definitions(dai_ros_plugins PRIVATE "DAI_ROS_PLUGINS_BUILDING_LIBRARY")

install(
  DIRECTORY include/
  DESTINATION include/${PROJECT_NAME}
)
install(
  TARGETS dai_ros_plugins
  EXPORT export_${PROJECT_NAME}
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)

ament_export_include_directories(
  "include/${PROJECT_NAME}"
)
pluginlib_export_plugin_description_file(depthai_ros_driver plugins.xml)

ament_export_libraries(
  dai_ros_plugins
)
ament_export_targets(
  export_${PROJECT_NAME}
)

ament_package()
