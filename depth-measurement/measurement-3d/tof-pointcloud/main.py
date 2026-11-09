#!/usr/bin/env python3
"""ToF colorized point cloud streamed to the DepthAI Visualizer.

Open http://localhost:8082 in a browser after starting this script.
"""

import depthai as dai
from utils.mode_menu import ModeMenu

FPS = 30.0
SIZE = (640, 400)

MODES = {
    "close": (dai.ToFConfig.Profile.LOW_RANGE, dai.ImageFiltersPresetMode.TOF_LOW_RANGE),
    "mid": (dai.ToFConfig.Profile.MID_RANGE, dai.ImageFiltersPresetMode.TOF_MID_RANGE),
    "far": (dai.ToFConfig.Profile.HIGH_RANGE, dai.ImageFiltersPresetMode.TOF_HIGH_RANGE),
}


def main():
    menu = None
    try:
        with dai.Pipeline() as p:
            device = p.getDefaultDevice()

            if device.getPlatform() == dai.Platform.RVC2:
                RGB_SOCKET = dai.CameraBoardSocket.CAM_C
            else:
                RGB_SOCKET = dai.CameraBoardSocket.CAM_A

            color = p.create(dai.node.Camera).build(RGB_SOCKET, sensorFps=FPS)
            colorOut = color.requestOutput(SIZE, fps=FPS, type=dai.ImgFrame.Type.RGB888i, enableUndistortion=True)

            tof = p.create(dai.node.ToF)
            tof.build(
                boardSocket=dai.CameraBoardSocket.AUTO,
                presetMode=dai.ImageFiltersPresetMode.TOF_HIGH_RANGE,
                fps=FPS
            )

            align = p.create(dai.node.ImageAlign)
            align.setRunOnHost(True)
            tof.depth.link(align.input)
            colorOut.link(align.inputAlignTo)

            pc = p.create(dai.node.PointCloud)
            pc.initialConfig.setLengthUnit(dai.LengthUnit.MILLIMETER)
            pc.setTargetCoordinateSystem(RGB_SOCKET)
            align.outputAligned.link(pc.inputDepth)
            colorOut.link(pc.inputColor)

            base_config_queue = tof.tofBaseInputConfig.createInputQueue()
            filter_config_queue = (tof.imageFiltersInputConfig.createInputQueue()
                                   if device.getPlatform() == dai.Platform.RVC2 else None)
            remote = dai.RemoteConnection(httpPort=8083)
            remote.addTopic("pcl", pc.outputPointCloud, "3d")

            p.start()
            remote.registerPipeline(p)
            menu = ModeMenu(MODES)
            menu.start()
            print("Visualizer running at http://localhost:8082")

            while p.isRunning():
                requested = menu.requested
                if requested != menu.selected:
                    profile, preset = MODES[requested]
                    config = dai.ToFConfig()
                    config.setProfilePreset(profile)
                    base_config_queue.send(config)
                    if filter_config_queue is not None:
                        image_config = dai.ImageFiltersConfig()
                        image_config.setProfilePreset(preset)
                        filter_config_queue.send(image_config)
                    menu.selected = requested
                    print(f"ToF mode: {requested} range", flush=True)
                key = remote.waitKey(1)
                if key == ord("q"):
                    break
    finally:
        if menu is not None:
            menu.shutdown()
            menu.server_close()


if __name__ == "__main__":
    main()
