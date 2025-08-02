import logging
import depthai as dai
import numpy as np
from utils.constants import Config

logger = logging.getLogger()


class WhisperEncoder(dai.node.HostNode):
    """Processes the encoder outputs for the Whisper model.
    Encoder outputs are used to initialize the decoder with necessary tensors.
    These tensors include:
    - k_cache_self: Key cache for self-attention
    - v_cache_self: Value cache for self-attention
    - x: Input token, initialized with the start of text token (SOT)
    - index: Index tensor, initialized to zero

    """

    def __init__(self) -> None:
        super().__init__()

        self.decoder_initialization = self.createOutput()
        self.passthrough = self.createOutput(
            name="passthrough",
        )

    def build(
        self,
        input_enc: dai.Node.Input,
        decoder_tokens: dai.Node.Input,
    ) -> "WhisperEncoder":
        self.link_args(input_enc, decoder_tokens)

        return self

    def process(self, encoder_out: dai.Buffer, decoder_tokens: dai.Buffer) -> None:
        k_cache_cross = encoder_out.getTensor("k_cache_cross")
        v_cache_cross = encoder_out.getTensor("v_cache_cross")
        self.passthrough.send(encoder_out)

        initialized_encoder_out = dai.NNData()
        initialized_encoder_out.addTensor(
            "k_cache_cross", k_cache_cross, dataType=dai.TensorInfo.DataType.FP16
        )
        initialized_encoder_out.addTensor(
            "v_cache_cross", v_cache_cross, dataType=dai.TensorInfo.DataType.FP16
        )
        initialized_encoder_out.addTensor(
            "k_cache_self",
            np.zeros((4, 6, 64, Config.MEAN_DECODE_LEN), dtype=np.float16),
        )

        initialized_encoder_out.addTensor(
            "v_cache_self",
            np.zeros((4, 6, Config.MEAN_DECODE_LEN, 64), dtype=np.float16),
        )

        initialized_encoder_out.addTensor(
            "x",
            np.array([[Config.TOKENS.TOKEN_SOT]], dtype=np.int32),
            dataType=dai.TensorInfo.DataType.INT,
        )
        initialized_encoder_out.addTensor(
            "index",
            np.zeros([1, 1], dtype=np.int32),
            dataType=dai.TensorInfo.DataType.INT,
        )
        self.decoder_initialization.send(initialized_encoder_out)
