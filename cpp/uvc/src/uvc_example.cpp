/* SPDX-License-Identifier: MIT */
/*
 * Copyright (c) 2026 Luxonis, Inc.
 *
 * Contact: <support@luxonis.com>
 */

#include <atomic>
#include <csignal>
#include <cstring>
#include <fstream>
#include <iostream>

#include "depthai/depthai.hpp"
#include "depthai/pipeline/MessageQueue.hpp"
#include "depthai/pipeline/datatype/ImgFrame.hpp"
#include "depthai/pipeline/datatype/MessageGroup.hpp"
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
std::shared_ptr<dai::MessageQueue> videoBitstreamQueue{nullptr};
std::shared_ptr<dai::MessageQueue> stillBitstreamQueue{nullptr};

/* Necessary for and only used by signal handler. */
static struct events *sigint_events;

// Signal handler
void signalHandler(int signum) {
    quitEvent = true;

	/* Stop the main loop when the user presses CTRL-C */
	events_stop(sigint_events);
}


extern "C" void depthai_uvc_get_buffer(struct video_source *s, struct video_buffer *buf, bool still) {
    unsigned int frame_size, size;
    uint8_t *f;

    if(quitEvent) {
        std::cout << "depthai_uvc_get_buffer(): Stopping capture due to quit event." << std::endl;
        return;
    }

    if(still) {
        std::cout << "depthai_uvc_get_buffer(): Sending latest full-resolution frame as still image." << std::endl;

        auto frame = stillBitstreamQueue->get<dai::ImgFrame>();

        f = frame->getData().data();
        frame_size = frame->getData().size();
        size = std::min(frame_size, buf->size);
        memcpy(buf->mem, f, size);
        buf->bytesused = size;
        return;
    }

    auto frame = videoBitstreamQueue->get<dai::ImgFrame>();
    if(frame == nullptr) {
        std::cerr << "depthai_uvc_get_buffer(): No frame available." << std::endl;
        return;
    }

    f = frame->getData().data();
    frame_size = frame->getData().size();

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

    // Encode the center-cropped HD stream for continuous UVC video.
    auto videoEncoder = pipeline.create<dai::node::VideoEncoder>();
    videoEncoder->setDefaultProfilePreset(30, dai::VideoEncoderProperties::Profile::MJPEG);
    videoSource->link(videoEncoder->input);
    videoBitstreamQueue = videoEncoder->bitstream.createOutputQueue(1, false);

    auto stillSource = camRgb->requestOutput(std::make_pair(3840, 2160), dai::ImgFrame::Type::NV12);
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
