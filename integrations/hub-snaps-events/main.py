import os
from pathlib import Path
from functools import partial
from typing import Dict
from dotenv import load_dotenv

import depthai as dai
from depthai_nodes.node import (
    ParsingNeuralNetwork,
    ImgDetectionsFilter,
    SnapsProducer,
)
from utils.arguments import initialize_argparser

load_dotenv(override=True)

_, args = initialize_argparser()

if args.fps_limit and args.media_path:
    args.fps_limit = None
    print(
        "WARNING: FPS limit is set but media path is provided. FPS limit will be ignored."
    )

if args.api_key:
    os.environ["DEPTHAI_HUB_API_KEY"] = args.api_key

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()


def custom_snap_process(
    producer: SnapsProducer,
    frame: dai.ImgFrame,
    det_data: dai.ImgDetections,
    label_map: Dict[str, int],
    model: str,
):
    detections = det_data.detections
    if len(detections) == 0:
        return

    dets_xyxy = [(det.xmin, det.ymin, det.xmax, det.ymax) for det in detections]
    dets_labels = [det.label for det in detections]
    dets_labels_str = [label_map[det.label] for det in detections]
    dets_confs = [det.confidence for det in detections]

    extra_data = {
        "model": model,
        "detection_xyxy": str(dets_xyxy),
        "detection_label": str(dets_labels),
        "detection_label_str": str(dets_labels_str),
        "detection_confidence": str(dets_confs),
    }
    if producer.sendSnap(
        name="rgb", frame=frame, data=[], tags=["demo"], extra_data=extra_data
    ):
        print("Snap sent!")


with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")

    platform = device.getPlatform()
    model_description = dai.NNModelDescription.fromYamlFile(
        f"yolov6_nano_r2_coco.{platform.name}.yaml"
    )
    nn_archive = dai.NNArchive(dai.getModelFromZoo(model_description))
    all_classes = nn_archive.getConfigV1().model.heads[0].metadata.classes

    if args.media_path:
        replay = pipeline.create(dai.node.ReplayVideo)
        replay.setReplayVideoFile(Path(args.media_path))
        replay.setOutFrameType(
            dai.ImgFrame.Type.BGR888i
            if platform == dai.Platform.RVC4
            else dai.ImgFrame.Type.BGR888p
        )
        replay.setLoop(True)
        if args.fps_limit:
            replay.setFps(args.fps_limit)
            args.fps_limit = None  # only want to set it once
        replay.setSize(nn_archive.getInputWidth(), nn_archive.getInputHeight())

    input_node = replay if args.media_path else pipeline.create(dai.node.Camera).build()

    nn_with_parser = pipeline.create(ParsingNeuralNetwork).build(
        input_node, nn_archive, fps=args.fps_limit
    )

    # filter and rename detection labels
    labels_to_keep = []
    label_map = {}
    for curr_class in args.class_names:
        try:
            curr_index = all_classes.index(curr_class)
            labels_to_keep.append(curr_index)
            label_map[curr_index] = curr_class
        except ValueError:
            print(f"Class `{curr_class}` not predicted by the model, skipping.")

    det_process_filter = pipeline.create(ImgDetectionsFilter).build(
        nn_with_parser.out,
        labels_to_keep=labels_to_keep,
        confidence_threshold=args.confidence_threshold,
    )

    snaps_producer = pipeline.create(SnapsProducer).build(
        nn_with_parser.passthrough,
        det_process_filter.out,
        time_interval=args.time_interval,
        process_fn=partial(
            custom_snap_process,
            label_map=label_map,
            model=nn_archive.getConfigV1().model.metadata.name,
        ),
    )

    visualizer.addTopic("Video", nn_with_parser.passthrough, "images")
    visualizer.addTopic("Visualizations", det_process_filter.out, "images")

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key from the remote connection!")
            break
