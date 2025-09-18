import depthai as dai
import numpy as np
from typing import Tuple
from scipy import special as scipy_special
from tqdm import tqdm
from whisper.decoding import get_tokenizer
from utils.constants import Config


class WhisperDecoder(dai.node.ThreadedHostNode):
    """Processes decoded outputs into readable text."""

    def __init__(self, sample_len):
        super().__init__()
        self.tokenizer = get_tokenizer(
            multilingual=False, language="en", task="transcribe"
        )
        self.encoder_input = self.createInput("encoder_input")
        self.decoder_input = self.createInput()

        self.out = self.createOutput()
        self.token_sequence = self.createOutput()

        self.sample_len = sample_len
        self.decoded_tokens = [Config.TOKENS["TOKEN_SOT"]]

    def apply_timestamp_rules(self, logits: np.ndarray) -> Tuple[np.ndarray, float]:
        """Apply timestamp-related post-processing rules to logits."""

        # Require producing timestamp
        logits[Config.TOKENS.TOKEN_NO_TIMESTAMP] = -np.inf

        # timestamps have to appear in pairs, except directly before EOT
        seq = self.decoded_tokens[Config.SAMPLE_BEGIN :]
        last_was_timestamp = (
            len(seq) >= 1 and seq[-1] >= Config.TOKENS.TOKEN_TIMESTAMP_BEGIN
        )
        penultimate_was_timestamp = (
            len(seq) < 2 or seq[-2] >= Config.TOKENS.TOKEN_TIMESTAMP_BEGIN
        )
        if last_was_timestamp:
            if penultimate_was_timestamp:  # has to be non-timestamp
                logits[Config.TOKENS.TOKEN_TIMESTAMP_BEGIN :] = -np.inf
            else:  # cannot be normal text tokens
                logits[: Config.TOKENS.TOKEN_EOT] = -np.inf

        timestamps = [
            t for t in self.decoded_tokens if t >= Config.TOKENS.TOKEN_TIMESTAMP_BEGIN
        ]
        if len(timestamps) > 0:
            # timestamps shouldn't decrease; forbid timestamp tokens smaller than the last
            # also force each segment to have a nonzero length, to   prevent infinite looping
            if last_was_timestamp and not penultimate_was_timestamp:
                timestamp_last = timestamps[-1]
            else:
                timestamp_last = timestamps[-1] + 1
            logits[Config.TOKENS.TOKEN_TIMESTAMP_BEGIN : timestamp_last] = -np.inf

        if len(self.decoded_tokens) == Config.SAMPLE_BEGIN:
            # suppress generating non-timestamp tokens at the beginning
            logits[: Config.TOKENS.TOKEN_TIMESTAMP_BEGIN] = -np.inf

            # apply the `max_initial_timestamp` option
            last_allowed = (
                Config.TOKENS.TOKEN_TIMESTAMP_BEGIN + Config.MAX_INITIAL_TIMESTAMP_INDEX
            )
            logits[(last_allowed + 1) :] = -np.inf

        # if sum of probability over timestamps is above any other token, sample timestamp
        logprobs = scipy_special.log_softmax(logits)
        timestamp_logprob = scipy_special.logsumexp(
            logprobs[Config.TOKENS.TOKEN_TIMESTAMP_BEGIN :]
        )
        max_text_token_logprob = logprobs[: Config.TOKENS.TOKEN_TIMESTAMP_BEGIN].max()
        if timestamp_logprob > max_text_token_logprob:
            # Mask out all but timestamp tokens
            logits[: Config.TOKENS.TOKEN_TIMESTAMP_BEGIN] = -np.inf

        return logits, logprobs

    def onStart(self):
        token_message = dai.NNData()
        token_message.addTensor(
            "tokens",
            np.array([], dtype=np.int32),
            dataType=dai.TensorInfo.DataType.INT,
        )
        self.token_sequence.send(token_message)

    def get_tokens(self, index, logits=None):
        """Get the next tokens based on current logits."""
        logits = logits[0, -1]  # Process the last token's logits

        # Filters
        # SuppressBlank
        if index == 1:
            logits[[Config.TOKENS.TOKEN_EOT, Config.TOKENS.TOKEN_BLANK]] = -np.inf
        # SuppressTokens
        logits[Config.NON_SPEECH_TOKENS] = -np.inf

        logits, logprobs = self.apply_timestamp_rules(logits)

        if index == 1:
            # detect no_speech
            no_speech_prob = np.exp(logprobs[Config.TOKENS.TOKEN_NO_SPEECH])
            if no_speech_prob > Config.NO_SPEECH_THR:
                return None

        # temperature = 0
        next_token = np.argmax(logits)
        if next_token == Config.TOKENS.TOKEN_EOT:
            return None

        x = np.array([[next_token]], dtype=np.int32)
        self.decoded_tokens.append(int(next_token))
        return x

    def run(self) -> None:
        """Run the decoder and process encoder outputs."""

        while self.isRunning():
            raw_encoder_outputs = self.encoder_input.get()
            k_cache_cross = raw_encoder_outputs.getTensor("k_cache_cross")
            v_cache_cross = raw_encoder_outputs.getTensor("v_cache_cross")
            ts = raw_encoder_outputs.getTimestamp()
            seq_num = raw_encoder_outputs.getSequenceNum()

            for i in tqdm(range(1, self.sample_len), total=self.sample_len):
                decoder_out: dai.NNData = self.decoder_input.get()

                logits = decoder_out.getTensor("logits")
                tokens = self.get_tokens(i, logits)

                if tokens is None:
                    token_message = dai.NNData()
                    token_message.setSequenceNum(seq_num)
                    token_message.setTimestamp(ts)
                    token_message.addTensor(
                        "tokens",
                        np.array(self.decoded_tokens[1:], dtype=np.int32),
                        dataType=dai.TensorInfo.DataType.INT,
                    )
                    self.token_sequence.send(token_message)
                    self.decoded_tokens = [Config.TOKENS["TOKEN_SOT"]]
                    break

                decoder_recursive_input = dai.NNData()
                decoder_recursive_input.setSequenceNum(seq_num)
                decoder_recursive_input.setTimestamp(ts)

                decoder_recursive_input.addTensor(
                    "k_cache_cross",
                    k_cache_cross,
                    dataType=dai.TensorInfo.DataType.FP16,
                )
                decoder_recursive_input.addTensor(
                    "v_cache_cross",
                    v_cache_cross,
                    dataType=dai.TensorInfo.DataType.FP16,
                )
                decoder_recursive_input.addTensor(
                    "k_cache_self",
                    decoder_out.getTensor("k_cache"),
                    dataType=dai.TensorInfo.DataType.FP16,
                )
                decoder_recursive_input.addTensor(
                    "v_cache_self",
                    decoder_out.getTensor("v_cache"),
                    dataType=dai.TensorInfo.DataType.FP16,
                )
                decoder_recursive_input.addTensor(
                    "x", tokens, dataType=dai.TensorInfo.DataType.INT
                )
                decoder_recursive_input.addTensor(
                    "index", np.array([[i]]), dataType=dai.TensorInfo.DataType.INT
                )

                self.out.send(decoder_recursive_input)
