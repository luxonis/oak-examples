#include "dai_ros_plugins/dai_ros_plugins.hpp"

#include "depthai/device/Device.hpp"
#include "depthai/pipeline/Pipeline.hpp"
#include "depthai_ros_driver/dai_nodes/base_node.hpp"
#include "depthai_ros_driver/dai_nodes/sensors/sensor_wrapper.hpp"
#include "depthai_ros_driver/dai_nodes/sensors/tof.hpp"
#include "depthai_ros_driver/param_handlers/pipeline_gen_param_handler.hpp"
#include "rclcpp/node.hpp"

namespace dai_ros_plugins {

DaiRosPlugins::DaiRosPlugins() = default;
std::vector<std::unique_ptr<depthai_ros_driver::dai_nodes::BaseNode>> DaiRosPlugins::createPipeline(
    std::shared_ptr<rclcpp::Node> node,
    std::shared_ptr<dai::Device> device,
    std::shared_ptr<dai::Pipeline> pipeline,
    std::shared_ptr<depthai_ros_driver::param_handlers::PipelineGenParamHandler> ph,
    const std::string& deviceName,
    bool rsCompat,
    const std::string& /*nnType*/) {
    namespace dai_nodes = depthai_ros_driver::dai_nodes;
    std::vector<std::unique_ptr<dai_nodes::BaseNode>> daiNodes;
    auto left = std::make_unique<dai_nodes::SensorWrapper>("left", node, pipeline, deviceName, rsCompat, dai::CameraBoardSocket::CAM_B);
    auto right = std::make_unique<dai_nodes::SensorWrapper>("right", node, pipeline, deviceName, rsCompat, dai::CameraBoardSocket::CAM_C);
    daiNodes.push_back(std::move(left));
    daiNodes.push_back(std::move(right));
    return daiNodes;
}
DaiRosPlugins::~DaiRosPlugins() {}

}  // namespace dai_ros_plugins
#include <pluginlib/class_list_macros.hpp>

PLUGINLIB_EXPORT_CLASS(dai_ros_plugins::DaiRosPlugins, depthai_ros_driver::pipeline_gen::BasePipeline)

