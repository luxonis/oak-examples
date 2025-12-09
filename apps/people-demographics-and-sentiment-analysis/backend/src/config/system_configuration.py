from dataclasses import dataclass
from argparse import Namespace
import depthai as dai

from .config_data_classes import VideoConfig, ModelNames


@dataclass
class SystemConfig:
    video: VideoConfig
    models: ModelNames


def build_configuration(platform: str, args: Namespace) -> SystemConfig:
    if args.fps_limit is None:
        args.fps_limit = 15
        print(f"FPS limit set to {args.fps_limit} for {platform}...")

    video_cfg = VideoConfig(
        fps=args.fps_limit,
        frame_type=dai.ImgFrame.Type.BGR888i,
        width=1280,
        height=720,
    )

    model_names = ModelNames(
        face="luxonis/yunet:640x360",
        emotions="luxonis/emotion-recognition:260x260",
        age_gender="luxonis/age-gender-recognition:62x62",
        people="luxonis/yolov6-nano:r2-coco-512x288",
        reid="luxonis/arcface:lfw-112x112",
    )

    return SystemConfig(video=video_cfg, models=model_names)
