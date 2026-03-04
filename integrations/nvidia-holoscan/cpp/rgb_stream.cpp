#include <opencv2/core/hal/interface.h>

#include <chrono>
#include <cstddef>
#include <cstdio>
#include <iostream>
#include <limits>
#include <map>
#include <memory>
#include <opencv2/core.hpp>
#include <opencv2/highgui.hpp>
#include <opencv2/opencv.hpp>
#include <utility>

#include "depthai/depthai.hpp"
#include "depthai/pipeline/datatype/ImgFrame.hpp"
#include "hsb_emulator.hpp"
#include "net.hpp"

using namespace hololink::emulation;

// Hololink register constants used by the emulator transport metadata setup.
// These values match hololink/core/data_channel.hpp.
constexpr uint32_t kDpPacketSize = 0x04;
constexpr uint32_t kDpPacketUdpPort = 0x08;
constexpr uint32_t kDpQp = 0x00;
constexpr uint32_t kDpRkey = 0x04;
constexpr uint32_t kDpAddress0 = 0x08;
constexpr uint32_t kDpBufferMask = 0x1C;

int main() {
  IPAddress emulatorIp = IPAddress_from_string("10.12.101.183");

  std::cout << "IPAddress: " << emulatorIp.if_name << ", "
            << inet_ntoa(*(in_addr *)&emulatorIp.ip_address) << ", "
            << inet_ntoa(*(in_addr *)&emulatorIp.subnet_mask) << ", "
            << inet_ntoa(*(in_addr *)&emulatorIp.broadcast_address) << ", "
            << std::hex << emulatorIp.mac[0] << ":" << std::hex
            << emulatorIp.mac[1] << ":" << std::hex << emulatorIp.mac[2] << ":"
            << std::hex << emulatorIp.mac[3] << ":" << std::hex
            << emulatorIp.mac[4] << ":" << std::hex << emulatorIp.mac[5]
            << std::dec << ", port: " << emulatorIp.port
            << ", flags: " << static_cast<int>(emulatorIp.flags) << std::endl;

  auto device = std::make_shared<dai::Device>();

  // Create pipeline
  dai::Pipeline pipeline{device};

  // Create and configure camera node
  auto cameraNode = pipeline.create<dai::node::Camera>();
  cameraNode->build();
  auto cameraOut = cameraNode->requestOutput(std::make_pair(640, 640));

  auto qRgb = cameraOut->createOutputQueue();

  HSBEmulator hsb;
  constexpr uint32_t kHifAddressBase = 0x02000300;
  constexpr uint32_t kHifAddressStep = 0x00010000;
  constexpr uint32_t kVpAddressBase = 0x00001000;
  constexpr uint32_t kVpAddressStep = 0x00000040;
  constexpr uint32_t kDefaultPacketPages = 1;
  constexpr uint32_t kDefaultQp = 1;
  constexpr uint32_t kDefaultRkey = 1;

  uint8_t data_plane_id = 0;
  uint8_t sensor_id = 0;
  const auto hifAddress = kHifAddressBase + kHifAddressStep * data_plane_id;
  const auto sif0Index =
      static_cast<uint8_t>(sensor_id * HSB_EMULATOR_CONFIG.sifs_per_sensor);
  const auto vpAddress = kVpAddressBase + kVpAddressStep * sif0Index;

  // Program default transport metadata. Destination IP/port is typically set by
  // host-side configuration after enumeration; these defaults ensure payload
  // metadata is valid.
  hsb.write(hifAddress + kDpPacketSize, kDefaultPacketPages);
  hsb.write(hifAddress + kDpPacketUdpPort, hololink::DATA_SOURCE_UDP_PORT);
  hsb.write(vpAddress + kDpQp, kDefaultQp);
  hsb.write(vpAddress + kDpRkey, kDefaultRkey);
  hsb.write(vpAddress + kDpBufferMask, 0x1u);
  hsb.write(vpAddress + kDpAddress0, 0u);

  pipeline.start();
  hsb.start();

  std::cout << "Running basic emulator mode (no RoCE/CUDA transport)."
            << std::endl;

  while (pipeline.isRunning()) {
    auto inRgb = qRgb->get<dai::ImgFrame>();
    if (inRgb == nullptr) {
      std::cerr << "Invalid frame. Skipping." << std::endl;
      continue;
    }

    cv::Mat cvFrame = inRgb->getCvFrame();
    cv::imshow("RGB Frame", cvFrame);
    auto key = cv::waitKey(1);
    if (key == 'q') {
      break;
    }
    if (cvFrame.empty()) {
      std::cerr << "Empty frame payload. Skipping frame." << std::endl;
      continue;
    }

    // cv::Mat bayerFrame(cvFrame.rows, cvFrame.cols, CV_8UC1);
    // for(int y = 0; y < cvFrame.rows; ++y) {
    //     const cv::Vec3b* srcRow = cvFrame.ptr<cv::Vec3b>(y);
    //     uint8_t* dstRow = bayerFrame.ptr<uint8_t>(y);
    //     const bool evenRow = (y & 1) == 0;
    //     for(int x = 0; x < cvFrame.cols; ++x) {
    //         const cv::Vec3b& p = srcRow[x];  // BGR
    //         const bool evenCol = (x & 1) == 0;
    //         // BGGR Bayer layout:
    //         // B G
    //         // G R
    //         if(evenRow) {
    //             dstRow[x] = evenCol ? p[0] : p[1];
    //         } else {
    //             dstRow[x] = evenCol ? p[1] : p[2];
    //         }
    //     }
    // }

    cv::Mat rgbFrame;
    cv::cvtColor(cvFrame, rgbFrame, cv::COLOR_BGR2RGB);

    // cv::Mat bayerFrame = cvFrame.clone();
    // if(!bayerFrame.isContinuous()) {
    //     bayerFrame = bayerFrame.clone();
    // }

    const size_t bayerSize = rgbFrame.total() * rgbFrame.elemSize();
    if (bayerSize == 0) {
      std::cerr << "Converted Bayer frame is empty. Skipping frame."
                << std::endl;
      continue;
    }

    if (bayerSize > std::numeric_limits<uint32_t>::max()) {
      std::cerr << "Frame payload too large for DP_BUFFER_LENGTH register. "
                   "Skipping frame."
                << std::endl;
      continue;
    }
  }

  hsb.stop();

  return 0;
}
