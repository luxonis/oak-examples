/* SPDX-License-Identifier: MIT */
/*
 * Copyright (c) 2026 Luxonis, Inc.
 *
 * Contact: <support@luxonis.com>
 */

#include <atomic>
#include <algorithm>
#include <cstdlib>
#include <csignal>
#include <cctype>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>

#include "depthai/depthai.hpp"
#include "depthai/pipeline/MessageQueue.hpp"
#include "depthai/pipeline/datatype/Buffer.hpp"
#include "depthai/pipeline/datatype/ImgFrame.hpp"
#include "uvc_example.hpp"

extern "C" {
#include "video-buffers.h"
#include "configfs.h"
#include "events.h"
#include "stream.h"
#include "uvc.h"
#include "libcamera-source.h"
#include "v4l2-source.h"
#include "test-source.h"
#include "jpg-source.h"
#include "slideshow-source.h"
#include "depthai-source.h"
}

// Global flag for graceful shutdown
std::atomic<bool> quitEvent(false);

std::shared_ptr<dai::InputQueue> inputQueue{nullptr};
std::shared_ptr<dai::MessageQueue> outputQueue;

enum class StreamFormat {
    MJPEG,
    UNCOMPRESSED,
};

static StreamFormat gStreamFormat = StreamFormat::UNCOMPRESSED;
static std::vector<uint8_t> gNv12Buffer;

static StreamFormat parseStreamFormat() {
    const char* format = std::getenv("UVC_FORMAT");
    if(format == nullptr) return StreamFormat::UNCOMPRESSED;

    std::string formatStr(format);
    std::transform(formatStr.begin(), formatStr.end(), formatStr.begin(), [](unsigned char c) { return std::tolower(c); });

    if(formatStr == "mjpeg") return StreamFormat::MJPEG;
    if(formatStr == "uncompressed" || formatStr == "nv12") return StreamFormat::UNCOMPRESSED;

    std::cerr << "Unknown UVC_FORMAT=\"" << formatStr << "\", defaulting to uncompressed NV12." << std::endl;
    return StreamFormat::UNCOMPRESSED;
}

/* Necessary for and only used by signal handler. */
static struct events *sigint_events;

// Signal handler
void signalHandler(int signum) {
    quitEvent = true;

	/* Stop the main loop when the user presses CTRL-C */
	events_stop(sigint_events);
}

extern "C" void depthai_uvc_get_buffer(struct video_source *s, struct video_buffer *buf) {
	unsigned int frame_size, size;
    const uint8_t *f;

    if(quitEvent) {
        std::cout << "depthai_uvc_get_buffer(): Stopping capture due to quit event." << std::endl;
        return;
    }      

    if(gStreamFormat == StreamFormat::MJPEG) {
        auto frame = outputQueue->get<dai::Buffer>();
        if(frame == nullptr || frame->getData().empty()) {
            std::cerr << "depthai_uvc_get_buffer(): No MJPEG frame available." << std::endl;
            return;
        }
        f = frame->getData().data();
        frame_size = frame->getData().size();
    } else {
        auto frame = outputQueue->get<dai::ImgFrame>();
        if(frame == nullptr) {
            std::cerr << "depthai_uvc_get_buffer(): No uncompressed frame available." << std::endl;
            return;
        }
        if(frame->getType() != dai::ImgFrame::Type::NV12) {
            std::cerr << "depthai_uvc_get_buffer(): Unexpected frame type for uncompressed mode: " << static_cast<int>(frame->getType()) << std::endl;
            return;
        }

        const auto width = frame->getWidth();
        const auto height = frame->getHeight();
        const auto stride = frame->getStride();
        const auto uvPlaneOffset = frame->getPlaneStride(0);
        const auto compactNv12FrameSize = (width * height * 3) / 2;
        const auto expectedSrcBytes = uvPlaneOffset + (stride * (height / 2));
        const auto& data = frame->getData();

        if(data.size() < expectedSrcBytes) {
            std::cerr << "depthai_uvc_get_buffer(): NV12 frame smaller than expected: have "
                      << data.size() << " need " << expectedSrcBytes << std::endl;
            return;
        }

        gNv12Buffer.resize(compactNv12FrameSize);
        const auto* src = data.data();
        auto* dst = gNv12Buffer.data();

        for(uint32_t y = 0; y < height; ++y) {
            memcpy(dst + (y * width), src + (y * stride), width);
        }

        const auto* uvSrc = src + uvPlaneOffset;
        auto* uvDst = dst + (width * height);
        for(uint32_t y = 0; y < height / 2; ++y) {
            memcpy(uvDst + (y * width), uvSrc + (y * stride), width);
        }

        f = gNv12Buffer.data();
        frame_size = static_cast<unsigned int>(gNv12Buffer.size());
    }

	size = std::min(frame_size, buf->size);
	memcpy(buf->mem, f, size);
	buf->bytesused = size;
}

extern "C" void depthai_control_pipeline_cb(uint32_t arg) {
    // This function can be used to send camera control commands to the device
    // For example, to start or stop streaming, adjust settings, etc.
    auto ctrl = std::make_shared<dai::CameraControl>();

    if (arg) {
        ctrl->setStartStreaming();
        std::cout << "Resuming Depthai pipeline." << std::endl;
    } else {
        ctrl->setStopStreaming();
        std::cout << "Pausing Depthai pipeline." << std::endl;
    }
    inputQueue->send(ctrl); // Commit the command to DAI pipeline
}

int main() {
    struct events events;
    struct uvc_function_config *fc;
    struct video_source* src;
    struct uvc_stream* stream;

    gStreamFormat = parseStreamFormat();

    depthai_uvc_register_get_buffer(depthai_uvc_get_buffer);

    fc = configfs_parse_uvc_function("uvc.0");
    if (!fc) {
        std::cerr << "Failed to parse UVC function configuration." << std::endl;
        return 1;
    }

    events_init(&events);

    /* Capture CTRL+C presses */
    sigint_events = &events;
    signal(SIGTERM, signalHandler);
    signal(SIGINT, signalHandler);

    src = depthai_video_source_create();
    if (!src) {
        std::cerr << "Failed to create video source." << std::endl;
        return 1;
    }

    stream = uvc_stream_new(fc->video);
    if (!stream) {
        std::cerr << "Failed to create UVC stream." << std::endl;
        video_source_destroy(src);
        return 1;
    }

    /* Register the callback to control the pipeline on UVC events:
        * - UVC_EVENT_STREAMON
        * - UVC_EVENT_STREAMOFF
        * - UVC_EVENT_DISCONNECT 
    */
    uvc_events_register_cb(stream, depthai_control_pipeline_cb);

	uvc_stream_set_event_handler(stream, &events);
	uvc_stream_set_video_source(stream, src);

    // Create device
    std::shared_ptr<dai::Device> device = std::make_shared<dai::Device>();

    // Create pipeline
    dai::Pipeline pipeline(device);

    // Detect connected cameras
    auto socket = device->getConnectedCameras()[0];
    std::cout << "Detected camera: " << dai::toString(socket) << std::endl;

    // Create nodes
    auto camRgb = pipeline.create<dai::node::Camera>()->build(socket);
    inputQueue  = camRgb->inputControl.createInputQueue();
    constexpr uint32_t width = 1920;
    constexpr uint32_t height = 1080;
    auto output = camRgb->requestOutput(std::make_pair(width, height), dai::ImgFrame::Type::NV12);

    if(gStreamFormat == StreamFormat::MJPEG) {
        auto encoded = pipeline.create<dai::node::VideoEncoder>();
        encoded->setDefaultProfilePreset(30, dai::VideoEncoderProperties::Profile::MJPEG);
        output->link(encoded->input);
        outputQueue = encoded->bitstream.createOutputQueue(1, false);
        std::cout << "Configured UVC stream format: MJPEG" << std::endl;
    } else {
        outputQueue = output->createOutputQueue(1, false);
        std::cout << "Configured UVC stream format: uncompressed NV12" << std::endl;
    }

    // Start pipeline
    pipeline.start();
    std::cout << "Started the pipeline" << std::endl;
    std::cout << "Press Ctrl+C to stop" << std::endl;
    depthai_control_pipeline_cb(0); // Pause the pipeline until UVC stream is started by the host

    /* Register the UVC events and init it */
    uvc_stream_init_uvc(stream, fc);

	/* Main capture loop */
	events_loop(&events);

    // Cleanup
    pipeline.stop();
    pipeline.wait();

	uvc_stream_delete(stream);
	video_source_destroy(src);
	events_cleanup(&events);
	configfs_free_uvc_function(fc);
    
    std::cout << "Video capture stopped." << std::endl;
    return 0;
}
