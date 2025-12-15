from box import Box
from tokenizers import Tokenizer
import numpy as np

from core.neural_network.prompts.encoders.base_prompt_encoder import BasePromptEncoder


class TextualPromptEncoder(BasePromptEncoder):
    """
    Handles text tokenization and embedding extraction (CLIP-compatible).
    """

    def __init__(self, config: Box):
        super().__init__(
            config,
            config.paths.text_encoder.url,
            config.paths.text_encoder.path,
        )
        self._offset: str = config.text_offset
        self.tokenizer_url: str = config.paths.tokenizer.url
        self.tokenizer_path: str = config.paths.tokenizer.path
        self.tokenizer: Tokenizer = None

    def _load_tokenizer(self):
        path = self._download_file(self.tokenizer_url, self.tokenizer_path)
        self.tokenizer = Tokenizer.from_file(str(path))

    def extract_embeddings(self, class_names: list[str]) -> np.ndarray:
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

        outputs = self._session.run(
            None, {self._session.get_inputs()[0].name: text_ids}
        )
        embeddings = outputs[0]
        embeddings /= np.linalg.norm(embeddings, ord=2, axis=-1, keepdims=True)

        quantized = self._pad_and_quantize_features(embeddings)

        del self._session

        return quantized
