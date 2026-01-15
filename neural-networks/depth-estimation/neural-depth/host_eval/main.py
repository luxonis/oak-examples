import cv2
import depthai as dai
import numpy as np
from pathlib import Path

from utils import StereoDataSample
from utils.arguments import initialize_argparser


MODEL_VARIANT_MAP = {
    "NANO": (dai.DeviceModelZoo.NEURAL_DEPTH_NANO, (240, 384)),
    "SMALL": (dai.DeviceModelZoo.NEURAL_DEPTH_SMALL, (300, 480)),
    "MEDIUM": (dai.DeviceModelZoo.NEURAL_DEPTH_MEDIUM, (360, 576)),
    "LARGE": (dai.DeviceModelZoo.NEURAL_DEPTH_LARGE, (480, 768)),
}


def parse_scenes(base_folder):
    scenes = []
    base_path = Path(base_folder)
    scene_dirs = sorted(
        [scene for scene in base_path.iterdir() if scene.is_dir()],
        key=lambda scene: scene.name,
    )
    for scene_dir in scene_dirs:
        left_path = scene_dir / "im0.png"
        right_path = scene_dir / "im1.png"
        gt_path = scene_dir / "disp0.pfm"
        if left_path.exists() and right_path.exists():
            scenes.append(
                {
                    "name": scene_dir.name,
                    "left": str(left_path),
                    "right": str(right_path),
                    "gt": str(gt_path) if gt_path.exists() else None,
                }
            )
    return scenes


def create_img_frame(img, sequence_num=0):
    img_frame = dai.ImgFrame()
    img_frame.setCvFrame(img, dai.ImgFrame.Type.GRAY8)
    img_frame.setSequenceNum(sequence_num)
    img_frame.setTimestamp(dai.Clock.now())
    return img_frame


def visualize_disparity(disp, max_disparity, metrics=None):
    disp_colored = cv2.applyColorMap(
        (np.clip(disp, 0, max_disparity) / max_disparity * 255).astype(np.uint8),
        cv2.COLORMAP_JET,
    )
    if metrics:
        text_bg = np.zeros((80, disp_colored.shape[1], 3), dtype=np.uint8)
        cv2.putText(
            text_bg,
            f"EPE: {metrics['EPE']:.2f}",
            (10, 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )
        cv2.putText(
            text_bg,
            f"Bad2: {metrics['bad2']:.1f}%  Bad4: {metrics['bad4']:.1f}%",
            (10, 45),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )
        cv2.putText(
            text_bg,
            f"Density: {metrics['density']:.2f}",
            (10, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2,
        )
        disp_colored = np.vstack([text_bg, disp_colored])
    return disp_colored


if __name__ == "__main__":
    _, args = initialize_argparser()

    eval_size = (800, 1280)  # fixed at sensor max resolution
    model_zoo_id, inference_size = MODEL_VARIANT_MAP[args.model]
    max_disparity = 192.0
    border_erase_pixels = 10  # clean pointcloud border regions
    conf_threshold = 0.55
    edge_threshold = 6.0

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    scenes = parse_scenes(args.dataset)
    print(f"Found {len(scenes)} scenes")

    device = dai.Device(dai.DeviceInfo(args.device_ip))
    all_metrics = []

    with dai.Pipeline(device) as pipeline:
        print("Creating pipeline...")
        neural_depth = pipeline.create(dai.node.NeuralNetwork)
        neural_depth.setModelFromDeviceZoo(model_zoo_id)

        left_queue = neural_depth.inputs["left"].createInputQueue(maxSize=1)
        right_queue = neural_depth.inputs["right"].createInputQueue(maxSize=1)
        out_queue = neural_depth.out.createOutputQueue(maxSize=1)
        print("Pipeline created.")

        pipeline.start()

        for idx, scene in enumerate(scenes):
            print(f"\n[{idx + 1}/{len(scenes)}] {scene['name']}")

            sample = StereoDataSample(
                left_path=scene["left"],
                right_path=scene["right"],
                eval_size=eval_size,
                inference_size=inference_size,
                gt_path=scene["gt"],
                to_gray=True,
                max_disparity=max_disparity,
                padding_mode="center",
                border_erase_pixels=border_erase_pixels,
            )

            left_img, right_img = sample.get_inference_inputs()
            left_uint8 = left_img.astype(np.uint8).squeeze()
            right_uint8 = right_img.astype(np.uint8).squeeze()

            left_frame = create_img_frame(left_uint8, sequence_num=idx)
            right_frame = create_img_frame(right_uint8, sequence_num=idx)

            left_queue.send(left_frame)
            right_queue.send(right_frame)

            frame = out_queue.get()

            disp = np.array(
                frame.getTensor("disparity", dequantize=True), dtype=np.float32
            )
            disp_bchw = disp.reshape(1, 1, disp.shape[1], disp.shape[2])

            conf = np.array(
                frame.getTensor("confidence", dequantize=True), dtype=np.float32
            )
            conf_bchw = conf.reshape(1, 1, conf.shape[1], conf.shape[2])

            edge = np.array(frame.getTensor("edge", dequantize=True), dtype=np.float32)
            edge_bchw = edge.reshape(1, 1, edge.shape[1], edge.shape[2])

            sample.set_predictions(
                disp_bchw, conf_bchw, edge_bchw, conf_threshold, edge_threshold
            )

            disp_vis, _, _ = sample.get_predictions(target="eval", strip_padding=True)

            metrics = None
            if scene["gt"]:
                metrics = sample.compute_metrics(target="eval", strip_padding=True)
                all_metrics.append(metrics)
                print(
                    "  EPE={:.3f}, bad2={:.1f}%, bad4={:.1f}%, density={:.2f}".format(
                        metrics["EPE"],
                        metrics["bad2"],
                        metrics["bad4"],
                        metrics["density"],
                    )
                )

            scene_dir = output_dir / scene["name"]
            scene_dir.mkdir(exist_ok=True)

            vis = visualize_disparity(disp_vis, max_disparity, metrics)
            cv2.imwrite(str(scene_dir / "disparity.png"), vis)

        pipeline.stop()

    if all_metrics:
        print(f"\n{'=' * 60}")
        print("AVERAGE METRICS")
        print(f"{'=' * 60}")
        avg = {k: np.mean([m[k] for m in all_metrics]) for k in all_metrics[0].keys()}
        print(f"EPE: {avg['EPE']:.3f}")
        print(f"Bad1: {avg['bad1']:.2f}%")
        print(f"Bad2: {avg['bad2']:.2f}%")
        print(f"Bad3: {avg['bad3']:.2f}%")
        print(f"Bad4: {avg['bad4']:.2f}%")
        print(f"Density: {avg['density']:.2f}")
        print(f"{'=' * 60}")

    print(f"\nResults saved to: {output_dir}")
