from box import Box
from tokenizers import Tokenizer
import numpy as np

from .base_prompt_encoder import BasePromptEncoder


class TextualPromptEncoder(BasePromptEncoder):
    """
    Handles text tokenization and embedding extraction (CLIP-compatible).
    """

    def __init__(self, config: Box, model_name: str, precision: str):
        super().__init__(
            config,
            config.paths.text_encoder.slug,
            config.paths.text_encoder.path,
            model_name,
            precision,
        )
        self._offset: int = config.text_offset
        self.tokenizer_url: str = config.paths.tokenizer.url
        self.tokenizer_path: str = config.paths.tokenizer.path
        self.tokenizer: Tokenizer = None

    def _npu_input_shape(self) -> tuple:
        """Static shape per batch bucket: batch padded to the bucket picked in
        extract_embeddings, sequence padded to CLIP's 77 (already done below)."""
        return (self._batch_bucket or self._config.max_num_classes, 77)

    def _load_tokenizer(self):
        path = self._download_file(self.tokenizer_url, self.tokenizer_path)
        self.tokenizer = Tokenizer.from_file(str(path))

    def extract_embeddings(self, class_names: list[str]) -> np.ndarray:
        self._batch_bucket = self._pick_bucket(len(class_names))
        self._load_tokenizer()
        self._load_model()

        self.tokenizer.enable_padding(
            pad_id=self.tokenizer.token_to_id("<|endoftext|>"),
            pad_token="<|endoftext|>",
        )

        encodings = self.tokenizer.encode_batch(class_names)
        text_ids = np.array([e.ids for e in encodings], dtype=np.int64)
        if text_ids.shape[1] < 77:
            text_ids = np.pad(
                text_ids, ((0, 0), (0, 77 - text_ids.shape[1])), mode="constant"
            )
        text_ids, n_classes = self._pad_batch(text_ids)

        outputs = self._session.run(
            None, {self._session.get_inputs()[0].name: text_ids}
        )
        embeddings = outputs[0][:n_classes]
        embeddings /= np.linalg.norm(embeddings, ord=2, axis=-1, keepdims=True)

        quantized = self._pad_and_quantize_features(embeddings)

        del self._session

        return quantized
