import depthai as dai
import numpy as np
import cv2
import argparse
from pathlib import Path
from utils import StereoDataSample


MODEL_VARIANT_MAP = {
    'NANO':   [dai.DeviceModelZoo.NEURAL_DEPTH_NANO, (240, 384)],
    'SMALL':  [dai.DeviceModelZoo.NEURAL_DEPTH_SMALL, (300, 480)],
    'MEDIUM': [dai.DeviceModelZoo.NEURAL_DEPTH_MEDIUM, (360, 576)],
    'LARGE':  [dai.DeviceModelZoo.NEURAL_DEPTH_LARGE, (480, 768)]
}


def parse_scenes(base_folder):
    scenes = []
    base_path = Path(base_folder)
    scene_dirs = sorted([d for d in base_path.iterdir() if d.is_dir()], key=lambda x: x.name)
    for scene_dir in scene_dirs:
        left_path = scene_dir / "im0.png"
        right_path = scene_dir / "im1.png"
        gt_path = scene_dir / "disp0.pfm"
        if left_path.exists() and right_path.exists():
            scenes.append({
                'name': scene_dir.name,
                'left': str(left_path),
                'right': str(right_path),
                'gt': str(gt_path) if gt_path.exists() else None
            })
    return scenes


def create_pipeline(device_ip, model_variant):
    
    device_info = dai.DeviceInfo(device_ip)
    device = dai.Device(device_info)
    pipeline = dai.Pipeline(device)
    
    neural_depth_node = pipeline.create(dai.node.NeuralNetwork)
    neural_depth_node.setModelFromDeviceZoo(MODEL_VARIANT_MAP[model_variant][0])
    
    return pipeline, neural_depth_node


def create_img_frame(img, sequence_num=0):
    img_frame = dai.ImgFrame()
    img_frame.setCvFrame(img, dai.ImgFrame.Type.GRAY8)
    img_frame.setSequenceNum(sequence_num)
    img_frame.setTimestamp(dai.Clock.now())
    return img_frame


def visualize_disparity(disp, max_disparity, metrics=None):
    disp_colored = cv2.applyColorMap(
        (np.clip(disp, 0, max_disparity) / max_disparity * 255).astype(np.uint8),
        cv2.COLORMAP_JET
    )
    if metrics:
        text_bg = np.zeros((80, disp_colored.shape[1], 3), dtype=np.uint8)
        cv2.putText(text_bg, f"EPE: {metrics['EPE']:.2f}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(text_bg, f"Bad2: {metrics['bad2']:.1f}%  Bad4: {metrics['bad4']:.1f}%", (10, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(text_bg, f"Density: {metrics['density']:.2f}", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        disp_colored = np.vstack([text_bg, disp_colored])
    return disp_colored


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=str, default='LARGE', choices=['NANO', 'SMALL', 'MEDIUM', 'LARGE'])
    parser.add_argument('--dataset', type=str, default='data/imperfect')
    parser.add_argument('--output', type=str, default='outputs_neural_depth_eval')
    parser.add_argument('--device_ip', type=str, required=True)
    args = parser.parse_args()
    
    dataset_folder = args.dataset
    output_path = args.output
    device_ip = args.device_ip
    model_variant = args.model
    
    eval_size = (800, 1280) # fixed at sensor max resolution
    inference_size = MODEL_VARIANT_MAP[model_variant][1]
    max_disparity = 192.0
    border_erase_pixels = 10 # used in legacy eval pipelines to clean pointcloud border regions
    conf_threshold = 0.55
    edge_threshold = 6.0
    
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    scenes = parse_scenes(dataset_folder)
    print(f"Found {len(scenes)} scenes")
    
    pipeline, nn_node = create_pipeline(device_ip, model_variant)
    
    left_queue = nn_node.inputs["left"].createInputQueue(maxSize=1)
    right_queue = nn_node.inputs["right"].createInputQueue(maxSize=1)
    out_queue = nn_node.out.createOutputQueue(maxSize=1)
    
    pipeline.start()
    
    all_metrics = []
    
    for idx, scene in enumerate(scenes):
        print(f"\n[{idx+1}/{len(scenes)}] {scene['name']}")
        
        sample = StereoDataSample(
            left_path=scene['left'],
            right_path=scene['right'],
            eval_size=eval_size,
            inference_size=inference_size,
            gt_path=scene['gt'],
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
        
        disp_tensor = frame.getTensor("disparity", dequantize=True)
        disp = np.array(disp_tensor).astype(np.float32)
        disp_bchw = disp.reshape(1, 1, disp.shape[1], disp.shape[2])
        
        conf_tensor = frame.getTensor("confidence", dequantize=True)
        conf = np.array(conf_tensor).astype(np.float32)
        conf_bchw = conf.reshape(1, 1, conf.shape[1], conf.shape[2])
        
        edge_tensor = frame.getTensor("edge", dequantize=True)
        edge = np.array(edge_tensor).astype(np.float32)
        edge_bchw = edge.reshape(1, 1, edge.shape[1], edge.shape[2])
        
        sample.set_predictions(disp_bchw, conf_bchw, edge_bchw, conf_threshold, edge_threshold)
        
        disp_vis, _, _ = sample.get_predictions(target='eval', strip_padding=True)
        
        metrics = None
        if scene['gt']:
            metrics = sample.compute_metrics(target='eval', strip_padding=True)
            all_metrics.append(metrics)
            print(f"  EPE={metrics['EPE']:.3f}, bad2={metrics['bad2']:.1f}%, bad4={metrics['bad4']:.1f}%, density={metrics['density']:.2f}")
        
        scene_dir = output_dir / scene['name']
        scene_dir.mkdir(exist_ok=True)
        
        vis = visualize_disparity(disp_vis, max_disparity, metrics)
        cv2.imwrite(str(scene_dir / "disparity.png"), vis)
    
    pipeline.stop()
    
    if all_metrics:
        print(f"\n{'='*60}")
        print("AVERAGE METRICS")
        print(f"{'='*60}")
        avg = {k: np.mean([m[k] for m in all_metrics]) for k in all_metrics[0].keys()}
        print(f"EPE: {avg['EPE']:.3f}")
        print(f"Bad1: {avg['bad1']:.2f}%")
        print(f"Bad2: {avg['bad2']:.2f}%")
        print(f"Bad3: {avg['bad3']:.2f}%")
        print(f"Bad4: {avg['bad4']:.2f}%")
        print(f"Density: {avg['density']:.2f}")
        print(f"{'='*60}")
    
    print(f"\nResults saved to: {output_dir}")


if __name__ == "__main__":
    main()
