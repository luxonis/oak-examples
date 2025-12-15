import depthai as dai
from typing import Optional

from depthai_nodes.node import GatherData

from .face_cropper import FaceCropper


class FaceCropsStage:
    """
    Builds the face-cropping part of the pipeline:

      image preview + face detections
        -> FaceCropper (Script + ImageManip)
        -> GatherData (sync crops with detections)

    Exposes:
      - out: cropped faces for second-stage NNs
      - synced_out: crops aligned with face detections (for PeopleFacesJoin)
    """

    def __init__(
        self,
        pipeline: dai.Pipeline,
        preview_source: dai.Node.Output,
        detections_source: dai.Node.Output,  # ImgDetections
        face_reference_detections: dai.Node.Output,  # ImgDetectionsExtended
        camera_fps: int,
    ):
        self._pipeline = pipeline

        self._preview_source = preview_source
        self._detections_source = detections_source
        self._face_reference_detections = face_reference_detections
        self._camera_fps = camera_fps

        self._cropper: Optional[FaceCropper] = None
        self._gather: Optional[GatherData] = None

    def build(self) -> "FaceCropsStage":
        self._cropper = FaceCropper(
            pipeline=self._pipeline,
            preview_source=self._preview_source,
            detections_source=self._detections_source,
        ).build()

        self._gather = self._create_gather_data(
            img_source=self._cropper.crops_out,
            face_reference_detections=self._face_reference_detections,
        )

        return self

    def _create_gather_data(
        self, img_source: dai.Node.Output, face_reference_detections: dai.Node.Output
    ) -> GatherData:
        gather = self._pipeline.create(GatherData).build(camera_fps=self._camera_fps)
        img_source.link(gather.input_data)
        face_reference_detections.link(gather.input_reference)
        return gather

    # --------- public outputs ---------

    @property
    def out(self) -> dai.Node.Output:
        """
        Cropped faces frames. Use this as img_source for second-stage NNs
        (emotions, age/gender, reid).
        """
        if self._cropper is None:
            raise RuntimeError(
                "FaceCropsStage.build() must be called before accessing out."
            )
        return self._cropper.crops_out

    @property
    def synced_out(self) -> dai.Node.Output:
        """
        GatherData: Crops aligned with face detections. Use this for fusion (PeopleFacesJoin).
        """
        if self._gather is None:
            raise RuntimeError(
                "FaceCropsStage.build() must be called before accessing synced_out."
            )
        return self._gather.out
