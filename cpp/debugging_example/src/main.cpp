#include <depthai/depthai.hpp>
#include <depthai/remote_connection/RemoteConnection.hpp>

int main(int argc, char** argv) {
    dai::RemoteConnection remoteConnector;

    dai::Pipeline pipeline;

    // Create a camera and request a 800p output
    auto cameraNode = pipeline.create<dai::node::Camera>()->build(dai::CameraBoardSocket::CAM_A);
    auto* cameraOutputVisualize = cameraNode->requestOutput(std::make_pair(1280, 800), dai::ImgFrame::Type::NV12);

    // Register the output so it's visualized on the remote connection
    remoteConnector.addTopic("stream", *cameraOutputVisualize);

    // Start the pipeline
    pipeline.start();
    while(pipeline.isRunning()) {
        int key = remoteConnector.waitKey(1);
        if(key == 'q') {
            std::cout << "Got 'q' key from the remote connection!" << std::endl;
            break;
        }
    }
    return 0;
}
