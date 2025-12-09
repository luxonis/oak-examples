import depthai as dai

from config.arguments import initialize_argparser
from config.system_configuration import build_configuration

from camera.camera_source import CameraSourceNode

from nn.nn_archive_loader import NNArchiveLoader
from nn.second_stage_nn import SecondStageNNNode

from faces.face_detection import FaceDetectionNode
from faces.cropping.face_crops_node import FaceCropsNode
from faces.features.face_features_node import FaceFeaturesNode

from people.people_tracking import PeopleTrackingNode
from people.joiner.people_faces_join import PeopleJoinNode

from visualization.monitor_node import MonitorFacesNode
from visualization.annotation_node import AnnotationNode


def main():
    _, args = initialize_argparser()
    device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
    visualizer = dai.RemoteConnection(serveFrontend=False)

    platform = device.getPlatform().name
    print(f"Device: {device.getDeviceId()}  Platform: {platform}")

    if platform != "RVC4":
        raise ValueError("This example is supported only on RVC4 platform")

    sys_config = build_configuration(platform, args)
    archive_loader = NNArchiveLoader(platform)

    with dai.Pipeline(device) as pipeline:
        print("Creating pipeline...")

        camera_source = pipeline.create(CameraSourceNode).build(cfg=sys_config.video)
        cam_out = camera_source.preview
        encoded_out = camera_source.encoded

        face_det_node = pipeline.create(FaceDetectionNode).build(
            image_source=cam_out,
            archive=archive_loader.load(sys_config.models.face),
        )

        face_crops_node = pipeline.create(FaceCropsNode).build(
            camera_fps=sys_config.video.fps,
            preview_source=cam_out,
            detections_source=face_det_node.filtered_bridge_output,
            face_reference_detections=face_det_node.filtered_output,
        )

        # Emotions
        emotions_node = pipeline.create(SecondStageNNNode, multi_head_nn=False).build(
            image_source=face_crops_node.out,
            reference_detections=face_det_node.filtered_output,
            archive=archive_loader.load(sys_config.models.emotions),
            camera_fps=sys_config.video.fps,
        )

        # Age/gender
        age_gender_node = pipeline.create(SecondStageNNNode, multi_head_nn=True).build(
            image_source=face_crops_node.out,
            reference_detections=face_det_node.filtered_output,
            archive=archive_loader.load(sys_config.models.age_gender),
            camera_fps=sys_config.video.fps,
        )

        # Re-ID
        reid_node = pipeline.create(SecondStageNNNode, multi_head_nn=False).build(
            image_source=face_crops_node.out,
            reference_detections=face_det_node.filtered_output,
            archive=archive_loader.load(sys_config.models.reid),
            camera_fps=sys_config.video.fps,
        )

        # Object tracker
        tracker = pipeline.create(PeopleTrackingNode).build(
            image_source=cam_out,
            archive=archive_loader.load(sys_config.models.people),
            fps=sys_config.video.fps,
        )

        # Joining
        face_features_node = pipeline.create(FaceFeaturesNode).build(
            age_gender=age_gender_node.synced_out,
            emotions=emotions_node.synced_out,
            reid=reid_node.synced_out,
            crops=face_crops_node.synced_out,
        )

        people_join_node = pipeline.create(PeopleJoinNode).build(
            faces=face_features_node.out,
            tracklets=tracker.out,
        )

        # Visualization
        monitor_node = pipeline.create(MonitorFacesNode).build(people_join_node.out)
        annotation_node = pipeline.create(AnnotationNode).build(people_join_node.out)

        visualizer.registerService("Get Faces", monitor_node.visualizer_get_payload)
        visualizer.addTopic("Video", encoded_out, "images")
        visualizer.addTopic("Annotations", annotation_node.out, "images")

        print("Pipeline created.")
        pipeline.start()
        visualizer.registerPipeline(pipeline)

        while pipeline.isRunning():
            key = visualizer.waitKey(1)
            pipeline.processTasks()
            if key == ord("q"):
                print("Got q key. Exiting...")
                break


if __name__ == "__main__":
    main()
