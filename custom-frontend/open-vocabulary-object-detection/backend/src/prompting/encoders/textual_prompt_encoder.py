from box import Box
from tokenizers import Tokenizer
import numpy as np

from .base_prompt_encoder import BasePromptEncoder


class TextualPromptEncoder(BasePromptEncoder):
    """
    Handles text tokenization and embedding extraction (CLIP-compatible).
    Supports both YOLOE and YOLO-World text encoders.
    """

    def __init__(self, config: Box, model_name: str, precision: str):
        super().__init__(
            config,
            config.paths.text_encoder.slug,
            config.paths.text_encoder.path,
            model_name,
            precision,
            quant_key=model_name,
        )
        self._offset: int = config.text_offset
        self.tokenizer_url: str = config.paths.tokenizer.url
        self.tokenizer_path: str = config.paths.tokenizer.path
        self.tokenizer: Tokenizer = None

    def _load_tokenizer(self):
        path = self._download_file(self.tokenizer_url, self.tokenizer_path)
        self.tokenizer = Tokenizer.from_file(str(path))
        self.tokenizer.enable_padding(
            pad_id=self.tokenizer.token_to_id("<|endoftext|>"),
            pad_token="<|endoftext|>",
        )

    def extract_embeddings(self, class_names: list[str]) -> np.ndarray:
        """Extract text embeddings for the given class names."""
        self._load_tokenizer()
        self._load_model()

        if self._model_name == "yolo-world":
            embeddings = self._extract_yolo_world(class_names)
        else:
            embeddings = self._extract_yoloe(class_names)

        quantized = self._pad_and_quantize_features(embeddings)
        del self._session
        return quantized

    def _extract_yoloe(self, class_names: list[str]) -> np.ndarray:
        """YOLOE text encoding: MobileCLIP encoder."""
        encodings = self.tokenizer.encode_batch(class_names)
        text_ids = np.array([e.ids for e in encodings], dtype=np.int64)
        if text_ids.shape[1] < 77:
            text_ids = np.pad(
                text_ids, ((0, 0), (0, 77 - text_ids.shape[1])), mode="constant"
            )

        outputs = self._session.run(
            None, {self._session.get_inputs()[0].name: text_ids}
        )
        embeddings = outputs[0]
        embeddings /= np.linalg.norm(embeddings, ord=2, axis=-1, keepdims=True)

        return embeddings

    def _extract_yolo_world(self, class_names: list[str]) -> np.ndarray:
        """YOLO-World text encoding: CLIP encoder."""
        encodings = self.tokenizer.encode_batch(class_names)
        text_ids = np.array([e.ids for e in encodings], dtype=np.int64)
        attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)

        if text_ids.shape[1] < 77:
            pad = 77 - text_ids.shape[1]
            text_ids = np.pad(text_ids, ((0, 0), (0, pad)), mode="constant")
            attention_mask = np.pad(attention_mask, ((0, 0), (0, pad)), mode="constant")

        outputs = self._session.run(
            None,
            {
                self._session.get_inputs()[0].name: text_ids,
                "attention_mask": attention_mask,
            },
        )
        embeddings = outputs[0]
        return embeddings
