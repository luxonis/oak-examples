import os
import argparse
import depthai as dai

parser = argparse.ArgumentParser()
parser.add_argument("--device", default=None, help="Device IP address")
parser.add_argument("--output", default="recordings", help="Output path")
args = parser.parse_args()

# Create output directory
os.makedirs(args.output, exist_ok=True)

# Define visualization
visualizer = dai.RemoteConnection(httpPort=8082)

# Define device (by default, uses first connected)
device = (
    dai.Device(dai.DeviceInfo(args.device)) if args.device is not None else dai.Device()
)
# Save Device calibration details
calib = device.readCalibration()
calib.eepromToJsonFile(os.path.join(args.output, "calib.json"))

# Create pipeline
with dai.Pipeline(device) as pipeline:
    # Define left stream
    camB = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_B)
    camBOut = camB.requestOutput((600, 400))

    # Define right stream
    camC = pipeline.create(dai.node.Camera).build(dai.CameraBoardSocket.CAM_C)
    camCOut = camC.requestOutput((600, 400))

    # Define output
    config = dai.RecordConfig()
    config.outputDir = args.output
    config.videoEncoding.enabled = True
    config.videoEncoding.bitrate = 0  # Automatic
    config.videoEncoding.profile = dai.VideoEncoderProperties.Profile.H264_MAIN

    pipeline.enableHolisticRecord(config)

    # Visualize streams
    visualizer.addTopic("CamB", camBOut)
    visualizer.addTopic("CamC", camCOut)

    # Start pipeline
    pipeline.start()
    visualizer.registerPipeline(pipeline)

    print("Recording: START")

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Recording: END")
            break
