/* SPDX-License-Identifier: MIT */
/*
 * Copyright (c) 2026 Luxonis, Inc.
 *
 * Contact: <support@luxonis.com>
 */

#pragma once

#include <memory>

#include "depthai/depthai.hpp"

extern "C" {
#include "uvcgadget/stream.h"
}

int registerExampleControls(struct uvc_stream* stream, std::shared_ptr<dai::InputQueue> inputQueue);
void cleanupExampleControls();
