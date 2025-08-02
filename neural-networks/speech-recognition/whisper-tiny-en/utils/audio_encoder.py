import depthai as dai
import sounddevice as sd
import numpy as np
from whisper.audio import load_audio, log_mel_spectrogram, pad_or_trim


class AudioEncoder(dai.node.ThreadedHostNode):
    def __init__(self, audio_file: str = None) -> None:
        super().__init__()
        self.output = self.createOutput()
        self.audio_file = audio_file

    def run(self) -> None:
        if self.audio_file:
            print(f"Processing audio file: {self.audio_file}")
            audio = load_audio(self.audio_file)
            mel_spectrogram = self._process_audio_array(audio)

            nn_data = dai.NNData()
            nn_data.addTensor(
                "audio", mel_spectrogram, dataType=dai.TensorInfo.DataType.FP16
            )
            self.output.send(nn_data)

    def _process_audio_array(self, audio_array: np.ndarray) -> np.ndarray:
        audio_array = pad_or_trim(audio_array)
        mel_spectrogram = log_mel_spectrogram(audio_array)
        mel_spectrogram = mel_spectrogram.unsqueeze(0).numpy().astype(np.float16)
        assert mel_spectrogram.shape == (
            1,
            80,
            3000,
        ), f"Expected shape (1, 80, 3000), got {mel_spectrogram.shape}"

        return mel_spectrogram

    def _record_audio_array(self, duration=5, samplerate=16000, channels=1):
        audio = sd.rec(
            int(duration * samplerate),
            samplerate=samplerate,
            channels=channels,
            dtype="float32",
        )
        sd.wait()
        print("Audio recording complete.")
        return np.squeeze(audio)

    def handle_key_press(self, key: str) -> None:
        if key == -1:
            return

        key = chr(key)

        if key == "r":
            print("Recording audio...")
            audio = self._record_audio_array()

            mel_spectrogram = self._process_audio_array(audio)

            nn_data = dai.NNData()
            nn_data.addTensor(
                "audio", mel_spectrogram, dataType=dai.TensorInfo.DataType.FP16
            )
            self.output.send(nn_data)
