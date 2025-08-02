import numpy as np
import depthai as dai
import re
from typing import Tuple
from utils.constants import Config
from depthai_nodes.utils import AnnotationHelper
from whisper.decoding import get_tokenizer


class AnnotationNode(dai.node.ThreadedHostNode):
    def __init__(self) -> None:
        super().__init__()
        self.frame_intput = self.createInput("frame_input")
        self.token_input = self.createInput("token_input")

        self.frame_out = self.createOutput()
        self.annotaion_out = self.createOutput()
        self.color_output = self.createOutput()

        self.tokenizer = get_tokenizer(
            multilingual=False, language="en", task="transcribe"
        )

        self.annotations = AnnotationHelper()
        self.annotations.draw_text(
            "Press 'r' to record audio",
            (
                0.002,
                0.05,
            ),
            size=24,
            color=dai.Color(1, 1, 1, 1),
            background_color=dai.Color(0, 0, 0, 0.5),
        )

    def parser_text(self, text: str) -> Tuple[str, str]:
        """Parses text into tuples of (str, color) and returns the new color of LED (None if not detected or multiple detected)."""
        words = text.split()
        words = [re.sub(r"[^\w]", "", word.lower()) for word in words]

        word_colors = [
            (
                word,
                Config.LED_COLORS.get(word, (255, 255, 255)),
            )
            for word in words
        ]
        # keep only words valid colors
        word_colors = [
            (word, color)
            for word, color in word_colors
            if word in Config.LED_COLORS.keys()
        ]

        if len(word_colors) == 0:
            return "", []
        word_color = word_colors[0]

        color = word_color[1][::-1]
        word = word_color[0]

        return word, color

    def run(self) -> None:
        while self.isRunning():
            frame_msg = self.frame_intput.get()
            token_msg = self.token_input.tryGet()

            if token_msg:
                tokens = token_msg.getTensor("tokens")
                text = self.tokenizer.decode(tokens)
                print(f"Decoded text: {text}")
                word, color = self.parser_text(text)

                if len(color) == 3:
                    color_msg = dai.NNData()
                    color_msg.addTensor(
                        "color",
                        np.array(color, dtype=np.uint8),
                        dataType=dai.TensorInfo.DataType.INT,
                    )
                    self.color_output.send(color_msg)

                    self.annotations = AnnotationHelper()
                    self.annotations.draw_text(
                        "Press 'r' to record audio",
                        (
                            0.002,
                            0.05,
                        ),
                        size=24,
                        color=dai.Color(1, 1, 1, 1),
                        background_color=dai.Color(0, 0, 0, 0.5),
                    )
                    color = np.array(color) / 255.0
                    dai_text_color = dai.Color(color[0], color[1], color[2], 1.0)
                    dai_frame_color = dai.Color(color[0], color[1], color[2], 0.2)

                    self.annotations.draw_text(
                        "Recognized the color: " + word,
                        (0.02, 0.15),
                        size=34,
                        color=dai_text_color,
                        background_color=dai.Color(1, 1, 1, 1),
                    )
                    self.annotations.draw_rectangle(
                        (0.0, 0.0),
                        (1.0, 1.0),
                        fill_color=dai_frame_color,
                        thickness=0.0,
                    )

            annotations_msg = self.annotations.build(
                timestamp=frame_msg.getTimestamp(),
                sequence_num=frame_msg.getSequenceNum(),
            )

            self.annotaion_out.send(annotations_msg)
            self.frame_out.send(frame_msg)
