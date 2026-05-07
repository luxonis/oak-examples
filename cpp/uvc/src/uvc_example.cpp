/* SPDX-License-Identifier: MIT */
/*
 * Copyright (c) 2026 Luxonis, Inc.
 *
 * Contact: <support@luxonis.com>
 */

#include <algorithm>
#include <atomic>
#include <cerrno>
#include <chrono>
#include <csignal>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iostream>
#include <mutex>
#include <thread>

#include "depthai/depthai.hpp"
#include "depthai/pipeline/MessageQueue.hpp"
#include "depthai/pipeline/datatype/ImgFrame.hpp"
#include "depthai/pipeline/datatype/MessageGroup.hpp"
#include "uvc_example.hpp"

extern "C" {
#include "video-buffers.h"
#include "control.h"
#include "configfs.h"
#include "events.h"
#include "stream.h"
#include "uvc.h"
#include <linux/usb/video.h>
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
std::shared_ptr<dai::MessageQueue> videoBitstreamQueue{nullptr};
std::shared_ptr<dai::MessageQueue> stillBitstreamQueue{nullptr};
std::mutex queueMutex;

/* Necessary for and only used by signal handler. */
static struct events *sigint_events;

// Signal handler
void signalHandler(int signum) {
    quitEvent = true;

	/* Stop the main loop when the user presses CTRL-C */
	events_stop(sigint_events);
}


std::shared_ptr<dai::ImgFrame> waitForEncodedFrame(const std::shared_ptr<dai::MessageQueue>& queue,
                                                       std::chrono::milliseconds timeout,
                                                       bool flushQueue = false) {
    if(queue == nullptr) {
        return nullptr;
    }

    if(flushQueue) {
        while(queue->tryGet<dai::ImgFrame>() != nullptr) {
        }
    }
    const auto deadline = std::chrono::steady_clock::now() + timeout;
    while(!quitEvent && std::chrono::steady_clock::now() < deadline) {
        auto frame = queue->tryGet<dai::ImgFrame>();
        if(frame != nullptr) {
            return frame;
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    return nullptr;
}

void flushEncodedFrames(const std::shared_ptr<dai::MessageQueue>& queue) {
    if(queue == nullptr) {
        return;
    }

    while(queue->tryGet<dai::ImgFrame>() != nullptr) {
    }
}

void copyEncodedFrameToBuffer(const std::shared_ptr<dai::ImgFrame>& frame,
                              struct video_buffer* buf,
                              const char* streamLabel) {
    if(frame == nullptr || buf == nullptr) {
        if(buf != nullptr) {
            buf->bytesused = 0;
        }
        return;
    }

    const auto& data = frame->getData();
    const auto size = std::min(data.size(), static_cast<size_t>(buf->size));
    std::memcpy(buf->mem, data.data(), size);
    buf->bytesused = size;

    if(size < data.size()) {
        std::cerr << streamLabel << ": encoded frame truncated from " << data.size() << " to " << size << " bytes." << std::endl;
    }
}


extern "C" void depthai_uvc_get_buffer(struct video_source *s, struct video_buffer *buf, bool still) {
    if(quitEvent) {
        std::cout << "depthai_uvc_get_buffer(): Stopping capture due to quit event." << std::endl;
        buf->bytesused = 0;
        return;
    }

    std::lock_guard<std::mutex> lock(queueMutex);

    if(still) {
        std::cout << "depthai_uvc_get_buffer(): Sending latest full-resolution frame as still image." << std::endl;

        // Drain any backlog so the still response uses the most recent full-frame image.
        flushEncodedFrames(stillBitstreamQueue);

        auto stillFrame = waitForEncodedFrame(stillBitstreamQueue, std::chrono::milliseconds(500));
        if(stillFrame == nullptr) {
            std::cerr << "depthai_uvc_get_buffer(): Timed out waiting for still frame." << std::endl;
            buf->bytesused = 0;
            return;
        }

        copyEncodedFrameToBuffer(stillFrame, buf, "depthai_uvc_get_buffer(still)");
        return;
    }

    auto frame = waitForEncodedFrame(videoBitstreamQueue, std::chrono::milliseconds(500));
    if(frame == nullptr) {
        std::cerr << "depthai_uvc_get_buffer(): Timed out waiting for video frame." << std::endl;
        buf->bytesused = 0;
        return;
    }

    copyEncodedFrameToBuffer(frame, buf, "depthai_uvc_get_buffer(video)");
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

const int MODEL_WIDTH = 640;
const int MODEL_HEIGHT = 480;

int main() {
    struct events events;
    struct uvc_function_config *fc;
    struct video_source* src;
    struct uvc_stream* stream;

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
    auto videoSource = camRgb->requestOutput(std::make_pair(1920, 1080), dai::ImgFrame::Type::NV12);
    auto stillSource = camRgb->requestOutput(std::make_pair(3840, 2160), dai::ImgFrame::Type::NV12);

    auto image_manip = pipeline.create<dai::node::ImageManip>();
    image_manip->setMaxOutputFrameSize(1920 * 1080 * 3);
    image_manip->initialConfig->addCrop(320, 180, 1280, 720); // Crop region: x=50, y=50, width=150, height=200
    image_manip->initialConfig->setOutputSize(1920, 1080, dai::ImageManipConfig::ResizeMode::CENTER_CROP);
    image_manip->initialConfig->setFrameType(dai::ImgFrame::Type::NV12);
    videoSource->link(image_manip->inputImage);

    // Encode the center-cropped HD stream for continuous UVC video.
    auto videoEncoder = pipeline.create<dai::node::VideoEncoder>();
    videoEncoder->setDefaultProfilePreset(30, dai::VideoEncoderProperties::Profile::MJPEG);
    image_manip->out.link(videoEncoder->input);
    videoBitstreamQueue = videoEncoder->bitstream.createOutputQueue(1, false);

    // Encode full-resolution frames for UVC still-image requests.
    auto stillEncoder = pipeline.create<dai::node::VideoEncoder>();
    stillEncoder->setDefaultProfilePreset(4, dai::VideoEncoderProperties::Profile::MJPEG);
    stillSource->link(stillEncoder->input);
    stillBitstreamQueue = stillEncoder->bitstream.createOutputQueue(1, false);

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
