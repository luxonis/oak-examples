#ifndef DAI_ROS_PLUGINS__DAI_ROS_PLUGINS_HPP_
#define DAI_ROS_PLUGINS__DAI_ROS_PLUGINS_HPP_

#include "dai_ros_plugins/visibility_control.h"
#include "depthai_ros_driver/pipeline/base_pipeline.hpp"

namespace dai {
class Pipeline;
class Device;
}  // namespace dai
namespace rclcpp {
class Node;
}
namespace depthai_ros_driver {
namespace param_handlers {
class PipelineGenParamHandler;
}
}  // namespace depthai_ros_driver

namespace dai_ros_plugins {

class DaiRosPlugins : public depthai_ros_driver::pipeline_gen::BasePipeline {
   public:
    DaiRosPlugins();
    std::vector<std::unique_ptr<depthai_ros_driver::dai_nodes::BaseNode>> createPipeline(
        std::shared_ptr<rclcpp::Node> node,
        std::shared_ptr<dai::Device> device,
        std::shared_ptr<dai::Pipeline> pipeline,
        std::shared_ptr<depthai_ros_driver::param_handlers::PipelineGenParamHandler> ph,
        const std::string& deviceName,
        bool rsCompat,
        const std::string& /*nnType*/);
    virtual ~DaiRosPlugins();
};

}  // namespace dai_ros_plugins

#endif  // DAI_ROS_PLUGINS__DAI_ROS_PLUGINS_HPP_
