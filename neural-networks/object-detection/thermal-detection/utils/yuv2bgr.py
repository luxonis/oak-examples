import cv2
import depthai as dai


def convert_thermal_color(src: dai.ImgFrame, frame_type, width: int, height: int) -> dai.ImgFrame:
    """Turn one Thermal.color frame into the detector's BGR frame.

    ``getCvFrame`` decodes YUV422i as YUYV, which matches the thermal sensor
    packing. The output keeps that pixel conversion. Timestamps, sequence,
    camera identity, and the source transformation are copied. A size change is
    a stretch and is recorded with ``addScale``.
    """
    bgr = src.getCvFrame()
    src_h, src_w = bgr.shape[:2]
    resized = src_w != width or src_h != height
    if resized:
        bgr = cv2.resize(bgr, (width, height), interpolation=cv2.INTER_LINEAR)

    out = dai.ImgFrame()
    out.setCvFrame(bgr, frame_type)
    out.setBufferMetadataFrom(src)
    out.setInstanceNum(src.getInstanceNum())
    out.setCategory(src.getCategory())
    out.sourceFb = src.sourceFb
    out.cam = src.cam
    out.event = src.event
    out.setTransformation(src.getTransformation())
    if resized:
        transform = out.getTransformation()
        tw, th = transform.getSize()
        if tw == src_w and th == src_h and tw > 0 and th > 0:
            transform.addScale(width / float(tw), height / float(th))
            out.setTransformation(transform)
    return out


class YUV2BGR(dai.node.ThreadedHostNode):
    """Host converter for ``Thermal.color``.

    This converter is added to the pipeline so the detector
    receives planar or interleaved BGR at the model size.
    """

    def __init__(self):
        super().__init__()
        self.input = self.createInput()
        self.out = self.createOutput()
        self.frame_type = dai.ImgFrame.Type.BGR888p
        self.width = 0
        self.height = 0

    def build(self, thermal_color: dai.Node.Output, frame_type, width: int, height: int):
        thermal_color.link(self.input)
        self.frame_type = frame_type
        self.width = int(width)
        self.height = int(height)
        return self

    def run(self):
        while self.isRunning():
            src = self.input.get()
            self.out.send(convert_thermal_color(src, self.frame_type, self.width, self.height))
