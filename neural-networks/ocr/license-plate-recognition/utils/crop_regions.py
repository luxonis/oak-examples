import depthai as dai

from depthai_nodes import GatheredData


class CropRegions(dai.Buffer):
    """Native crop regions plus their source detections and ordered source indexes."""

    def __init__(self, regions: dai.ImgDetections, source: dai.Buffer, indices: list):
        super().__init__()
        self.regions = regions
        self.source = source
        self.indices = indices
        self.setTimestamp(regions.getTimestamp())
        self.setTimestampDevice(regions.getTimestampDevice())
        self.setSequenceNum(regions.getSequenceNum())

    @property
    def detections(self):
        return self.regions.detections


class VehicleRegions(dai.node.HostNode):
    def __init__(self):
        super().__init__()
        self.reference = self.createOutput()

    def build(self, detections: dai.Node.Output) -> "VehicleRegions":
        self.link_args(detections)
        return self

    def process(self, detections: dai.ImgDetections) -> None:
        vehicles = []
        indices = []
        for index, detection in enumerate(detections.detections):
            if detection.label not in (2, 5, 7) or detection.confidence < 0.7:
                continue
            vehicle = dai.ImgDetection()
            vehicle.label = detection.label
            vehicle.confidence = detection.confidence
            vehicle.xmin = max(0, min(1, detection.xmin * 0.9))
            vehicle.ymin = max(0, min(1, detection.ymin * 0.9))
            vehicle.xmax = max(0, min(1, detection.xmax * 1.1))
            vehicle.ymax = max(0, min(1, detection.ymax * 1.1))
            if vehicle.xmax <= vehicle.xmin or vehicle.ymax <= vehicle.ymin:
                continue
            vehicles.append(vehicle)
            indices.append(index)

        regions = dai.ImgDetections()
        regions.detections = vehicles
        regions.setTransformation(detections.getTransformation())
        regions.setTimestamp(detections.getTimestamp())
        regions.setTimestampDevice(detections.getTimestampDevice())
        regions.setSequenceNum(detections.getSequenceNum())
        self.reference.send(CropRegions(regions, detections, indices))
        self.out.send(regions)


class PlateRegions(dai.node.HostNode):
    def __init__(self):
        super().__init__()
        self.reference = self.createOutput()

    def build(
        self, detections: dai.Node.Output, frame_size: tuple[int, int]
    ) -> "PlateRegions":
        self._frame_size = frame_size
        self.link_args(detections)
        return self

    def process(self, detections: dai.Buffer) -> None:
        assert isinstance(detections, GatheredData)
        # Undo the vehicle-detector resize to recover source-frame geometry.
        transformation = detections.reference_data.regions.getTransformation()
        detection_width, detection_height = transformation.getSize()
        frame_width, frame_height = self._frame_size
        transformation.addScale(
            frame_width / detection_width, frame_height / detection_height
        )
        transformation.setSize(frame_width, frame_height)

        plates = []
        indices = []
        for vehicle_index, plate_detections in enumerate(detections.items):
            candidates = plate_detections.detections
            if not candidates:
                continue
            plate_index = max(
                range(len(candidates)), key=lambda i: candidates[i].confidence
            )
            best = candidates[plate_index]
            if best.confidence < 0.5:
                continue

            # Keep the ALPR-specific inset, then map the crop back to source pixels.
            plate = dai.ImgDetection()
            plate.confidence = best.confidence
            plate.label = best.label
            plate.xmin, plate.ymin = best.xmin * 1.02, best.ymin * 1.03
            plate.xmax, plate.ymax = best.xmax * 0.98, best.ymax * 0.97
            if plate.xmax <= plate.xmin or plate.ymax <= plate.ymin:
                continue
            selected = dai.ImgDetections()
            selected.detections = [plate]
            selected.setTransformation(plate_detections.getTransformation())
            mapped = selected.transformTo(transformation).detections[0]
            # Remapping may represent an axis-aligned box with a 90-degree angle.
            plate.setOuterBoundingBox(
                max(0, mapped.xmin),
                max(0, mapped.ymin),
                min(1, mapped.xmax),
                min(1, mapped.ymax),
            )
            if (plate.xmax - plate.xmin) * frame_width <= 40 or (
                plate.ymax - plate.ymin
            ) * frame_height <= 10:
                continue
            plates.append(plate)
            indices.append((vehicle_index, plate_index))

        regions = dai.ImgDetections()
        regions.detections = plates
        regions.setTransformation(transformation)
        regions.setTimestamp(detections.getTimestamp())
        regions.setTimestampDevice(detections.getTimestampDevice())
        regions.setSequenceNum(detections.getSequenceNum())
        # source retains all vehicle/plate outputs; indices identify each selected parent.
        self.reference.send(CropRegions(regions, detections, indices))
        self.out.send(regions)
