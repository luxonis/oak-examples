import numpy as np
import depthai as dai

from depthai_nodes import ImgDetectionsExtended


class IdentificationNode(dai.node.HostNode):
    """A host node that re-identifies objects based on their embeddings similarity to a database of embeddings.

    Attributes
    ----------
    csim : float
        The cosine similarity threshold used for merging.
    label_basename : str
        The basename of the labels (e.g., "person"). The labels will be in the format "basename_0", "basename_1", etc.
    """

    def __init__(self) -> None:
        super().__init__()
        self._cos_sim_threshold = None
        self._label_basename = None
        self._embeddings_dict = {}

    def setCosSimThreshold(self, csim: float) -> None:
        """Sets the cosine similarity threshold.

        @param csim: The cosine similarity threshold.
        @type csim: float
        """
        if not isinstance(csim, float):
            raise TypeError("Cosine similarity threshold must be a float.")
        if csim < 0 or csim > 1:
            raise ValueError("Cosine similarity threshold must be between 0 and 1.")
        self._cos_sim_threshold = csim

    def setLabelBasename(self, label_basename: str) -> None:
        """Sets the basename of the labels.

        @param label_basename: The basename of the labels.
        @type label_basename: str
        """
        if not isinstance(label_basename, str):
            raise TypeError("Label basename must be a string.")
        self._label_basename = label_basename

    def build(
        self, gather_data_msg, csim: float = 0.5, label_basename: str = "person"
    ) -> "IdentificationNode":
        self.link_args(gather_data_msg)
        self.setCosSimThreshold(csim)
        self.setLabelBasename(label_basename)
        return self

    def process(self, gather_data_msg) -> None:
        dets_msg: ImgDetectionsExtended = gather_data_msg.reference_data
        assert isinstance(dets_msg, ImgDetectionsExtended)

        rec_msg_list = gather_data_msg.gathered
        assert isinstance(rec_msg_list, list)
        assert all(isinstance(msg, dai.NNData) for msg in rec_msg_list)

        for detection, rec in zip(dets_msg.detections, rec_msg_list):
            detection.label_name = self._get_label_name(rec, self._label_basename)

        self.out.send(dets_msg)

    def _get_label_name(self, rec, basename) -> str:
        embedding = rec.getTensor("output", dequantize=True)
        sim = [
            self._cos_sim(embedding, self._embeddings_dict[key])
            for key in self._embeddings_dict
        ]

        if sim:
            if max(sim) >= self._cos_sim_threshold:
                idx = sim.index(max(sim))
                label = list(self._embeddings_dict.keys())[idx]
            else:
                label = f"{basename}_{len(self._embeddings_dict)}"
        else:
            label = f"{basename}_0"

        self._embeddings_dict[label] = embedding
        return label

    def _cos_sim(self, X: np.ndarray, Y: np.ndarray) -> float:
        Y = Y.T
        result = np.dot(X, Y) / (np.linalg.norm(X) * np.linalg.norm(Y, axis=0))
        return result.item()
