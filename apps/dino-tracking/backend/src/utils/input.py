import depthai as dai
from pathlib import Path


def create_input_node(pipeline, platform, media_path=None, media_loop=True):
    """Adds a ReplayVideo or a Camera node to the pipeline."""

    def _create_media_node(pipeline, media_path, platform, loop):
        """Add a ReplayVideo node."""

        replay = pipeline.create(dai.node.ReplayVideo)
        replay.setReplayVideoFile(Path(media_path))
        if platform == "RVC2":
            replay.setOutFrameType(dai.ImgFrame.Type.BGR888p)
        elif platform == "RVC4":
            replay.setOutFrameType(dai.ImgFrame.Type.BGR888i)
        else:
            raise ValueError(f"ReplayVideo node not supported for {platform}.")
        replay.setLoop(loop)
        return replay

    def _create_camera_node(pipeline):
        """Add a Camera node."""

        cam = pipeline.create(dai.node.Camera)
        return cam.build()

    if media_path:
        return _create_media_node(pipeline, media_path, platform, media_loop)
    else:
        return _create_camera_node(pipeline)
