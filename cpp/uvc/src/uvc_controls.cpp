/* SPDX-License-Identifier: MIT */
/*
 * Copyright (c) 2026 Luxonis, Inc.
 *
 * Contact: <support@luxonis.com>
 */

#include <algorithm>
#include <cerrno>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <memory>

#include "depthai/depthai.hpp"
#include "uvc_controls.hpp"

extern "C" {
#include "uvcgadget/control.h"
#include <linux/usb/video.h>
}

struct uvc_control gExposureModeControl{};
struct uvc_control gExposurePriorityControl{};
struct uvc_control gExposureTimeAbsoluteControl{};
struct uvc_control gBrightnessControl{};
struct uvc_control gGainControl{};
struct uvc_control gExtensionControl{};

std::shared_ptr<dai::InputQueue> gInputQueue{nullptr};

constexpr uint8_t kUvcAeModeManual = 0x01;
constexpr uint8_t kUvcAeModeAuto = 0x02;
constexpr uint8_t kUvcAeModeShutterPriority = 0x04;
constexpr uint8_t kUvcAeModeAperturePriority = 0x08;
constexpr uint32_t kDefaultExposureTimeUs = 20000;
constexpr uint32_t kDefaultSensitivityIso = 800;
constexpr int16_t kDepthaiBrightnessMin = -10;
constexpr int16_t kDepthaiBrightnessMax = 10;
constexpr int16_t kDepthaiGainMin = 1;
constexpr int16_t kDepthaiGainMax = 1600;

uint8_t gAeMode = kUvcAeModeAperturePriority;
uint8_t gAePriority = 0;
uint32_t gExposureTimeUs = kDefaultExposureTimeUs;
uint32_t gSensitivityIso = kDefaultSensitivityIso;

int sendDepthaiControl(const std::shared_ptr<dai::CameraControl>& ctrl, const char* reason) {
    if(gInputQueue == nullptr) {
        std::cerr << "DepthAI control queue is not ready for " << reason << "." << std::endl;
        return -EAGAIN;
    }

    gInputQueue->send(ctrl);
    return 0;
}

template <typename T>
int readControlValue(const uint8_t* data, uint16_t size, T& value) {
    if(size != sizeof(T)) {
        return -EINVAL;
    }

    std::memcpy(&value, data, sizeof(T));
    return 0;
}

int uvcSetAeModeControl(struct uvc_stream*,
                        const struct uvc_control*,
                        const uint8_t* data,
                        uint16_t size,
                        void*) {
    uint8_t aeMode = 0;
    const int ret = readControlValue(data, size, aeMode);
    if(ret < 0) {
        return ret;
    }
    if (gAeMode == aeMode) {
        // No mode change, so no need to send a control to DepthAI
        return 0;
    }

    switch(aeMode) {
        case kUvcAeModeManual: {
            auto ctrl = std::make_shared<dai::CameraControl>();
            gAeMode = aeMode;
            ctrl->setManualExposure(gExposureTimeUs, gSensitivityIso);

            return sendDepthaiControl(ctrl, "manual exposure mode");
        }
        case kUvcAeModeAuto:
        case kUvcAeModeShutterPriority:
        case kUvcAeModeAperturePriority: {
            auto ctrl = std::make_shared<dai::CameraControl>();
            gAeMode = aeMode;
            ctrl->setAutoExposureEnable();

            return sendDepthaiControl(ctrl, "auto exposure mode");
        }
        default:
            return -EOPNOTSUPP;
    }
}

int uvcSetExposureTimeAbsoluteControl(struct uvc_stream*,
                                      const struct uvc_control*,
                                      const uint8_t* data,
                                      uint16_t size,
                                      void*) {
    uint32_t exposureTime100us = 0;
    const int ret = readControlValue(data, size, exposureTime100us);
    if(ret < 0) {
        return ret;
    }

    gExposureTimeUs = std::max<uint32_t>(1u, exposureTime100us * 100u);
    std::cout << "UVC camera terminal: exposure time absolute set to "
              << exposureTime100us << " (100 us units), mapped to "
              << gExposureTimeUs << " us" << std::endl;

    std::cout << "gAeMode = 0x" << std::hex << static_cast<int>(gAeMode) << std::dec << std::endl;
    auto ctrl = std::make_shared<dai::CameraControl>();
    if(gAeMode == kUvcAeModeManual || gAeMode == kUvcAeModeShutterPriority) {
        ctrl->setManualExposure(gExposureTimeUs, gSensitivityIso);
    } else {
        ctrl->setAutoExposureEnable();
    }

    return sendDepthaiControl(ctrl, "absolute exposure time");
}

int uvcSetBrightnessControl(struct uvc_stream*,
                            const struct uvc_control*,
                            const uint8_t* data,
                            uint16_t size,
                            void*) {
    int16_t brightness = 0;
    const int ret = readControlValue(data, size, brightness);
    if(ret < 0) {
        return ret;
    }

    brightness = std::clamp(brightness, kDepthaiBrightnessMin, kDepthaiBrightnessMax);
    std::cout << "UVC processing unit: brightness set to " << brightness << std::endl;

    auto ctrl = std::make_shared<dai::CameraControl>();
    ctrl->setBrightness(static_cast<int>(brightness));
    return sendDepthaiControl(ctrl, "brightness");                            
}

int uvcSetGainControl(struct uvc_stream*,
                      const struct uvc_control*,
                      const uint8_t* data,
                      uint16_t size,
                      void*) {
    int16_t gain = 0;
    const int ret = readControlValue(data, size, gain);
    if(ret < 0) {
        return ret;
    }

    gSensitivityIso = std::clamp(gain, kDepthaiGainMin, kDepthaiGainMax);
    std::cout << "UVC processing unit: gain set to " << gain << std::endl;

    auto ctrl = std::make_shared<dai::CameraControl>();
    ctrl->setManualExposure(gExposureTimeUs, gSensitivityIso);
    return sendDepthaiControl(ctrl, "gain");                            
}

int uvcSetExtensionControl(struct uvc_stream*,
                           const struct uvc_control*,
                           const uint8_t* data,
                           uint16_t size,
                           void*) {
    uint32_t value = 0;
    const int ret = readControlValue(data, size, value);
    if(ret < 0) {
        return ret;
    }

    auto ctrl = std::make_shared<dai::CameraControl>();
    ctrl->setAutoExposureMaxISO(value);
    sendDepthaiControl(ctrl, "max-iso");

    std::cout << "UVC extension unit: value set to 0x"
              << std::hex << static_cast<int>(value) << std::dec << std::endl;
    return 0;
}

void cleanupExampleControls() {
    uvc_control_deinit(&gExposureModeControl);
    uvc_control_deinit(&gExposurePriorityControl);
    uvc_control_deinit(&gExposureTimeAbsoluteControl);
    uvc_control_deinit(&gBrightnessControl);
    uvc_control_deinit(&gExtensionControl);
    gInputQueue.reset();
}

int registerExampleControls(struct uvc_stream* stream, std::shared_ptr<dai::InputQueue> inputQueue) {
    static const struct uvc_control_ops aeModeOps{nullptr, uvcSetAeModeControl};
    static const struct uvc_control_ops exposureTimeAbsoluteOps{nullptr, uvcSetExposureTimeAbsoluteControl};
    static const struct uvc_control_ops brightnessOps{nullptr, uvcSetBrightnessControl};
    static const struct uvc_control_ops gainOps{nullptr, uvcSetGainControl};
    static const struct uvc_control_ops extensionOps{nullptr, uvcSetExtensionControl};

    gInputQueue  = inputQueue;

    int ret = uvc_stream_register_control_uint8(
        stream, 
        &gExposureModeControl,
        UVC_CONTROL_SECTION_CAMERA_TERMINAL,
        UVC_CT_AE_MODE_CONTROL,
        kUvcAeModeAuto, 0x00, 0x00, kUvcAeModeManual | kUvcAeModeAuto, kUvcAeModeAuto,
        &aeModeOps
    );
    ret |= uvc_stream_register_control_uint32(
        stream,
        &gExposureTimeAbsoluteControl,
        UVC_CONTROL_SECTION_CAMERA_TERMINAL,
        UVC_CT_EXPOSURE_TIME_ABSOLUTE_CONTROL,
        20000, 1, 20000, 1, 20000,
        &exposureTimeAbsoluteOps
    );
    ret |= uvc_stream_register_control_int16(
        stream,
        &gBrightnessControl,
        UVC_CONTROL_SECTION_PROCESSING_UNIT,
        UVC_PU_BRIGHTNESS_CONTROL,
        0, kDepthaiBrightnessMin, kDepthaiBrightnessMax, 1, 0,
        &brightnessOps
    );
    ret |= uvc_stream_register_control_int16(
        stream,
        &gGainControl,
        UVC_CONTROL_SECTION_PROCESSING_UNIT,
        UVC_PU_GAIN_CONTROL,
        kDefaultSensitivityIso, kDepthaiGainMin, kDepthaiGainMax, 1, kDefaultSensitivityIso,
        &gainOps
    );
    ret |= uvc_stream_register_control_uint32(
        stream,
        &gExtensionControl,
        UVC_CONTROL_SECTION_EXTENSION_UNIT,
        1,
        6000, 50, 6000, 50, 6000,
        &extensionOps
    );

    if(ret == -ENOENT) {
        std::cout << "No extension unit ID found in configfs. Skipping extension control." << std::endl;
    } else if(ret < 0) {
        return ret;
    }

    return 0;
}
