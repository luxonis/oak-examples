# AGENTS.md

## Summary

This is the repository reference for short-audio Whisper transcription on OAK4 with LED and stream feedback. Use it when you need the repo’s speech-recognition example rather than a vision pipeline.

## Use This Example When

- You need Whisper Tiny EN on OAK4.
- You want audio-driven text output integrated with a live camera stream.
- You need the LED/color feedback workflow described in the README.

## Do Not Use This Example When

- You need RVC2 support.
- You need continuous streaming ASR.
- You need a fully host-side speech model rather than device-assisted inference.

## Quick Facts

- `Category:` `neural-networks/speech-recognition/whisper-tiny-en`
- `Shape:` `script+standalone`
- `Primary task:` short audio capture or audio-file transcription with LED/color feedback
- `Entrypoint:` [main.py](main.py)
- `Standalone path:` [oakapp.toml](oakapp.toml)
- `Frontend:` none
- `Runs on:` RVC4 only
- `Requires:` OAK4, Whisper encoder/decoder model assets, and host audio prerequisites for recording mode
- `Input:` host-recorded audio triggered by keypress or `--audio_file`, plus a live camera stream for visual feedback
- `Output:` `Camera` and `Decoded Audio Message`
- `Models:` Whisper encoder/decoder YAMLs in [depthai_models/](depthai_models/)
- `Visualizer / UI:` DepthAI Visualizer via `dai.RemoteConnection`

## Read First

- [README.md](README.md)
- [main.py](main.py)
- [utils/audio_encoder.py](utils/audio_encoder.py)
- [utils/whisper_encoder.py](utils/whisper_encoder.py)
- [utils/whisper_decoder.py](utils/whisper_decoder.py)
- [utils/led_changer_script.py](utils/led_changer_script.py)
- [utils/arguments.py](utils/arguments.py)

## Architecture

- Host audio is converted into a spectrogram by [utils/audio_encoder.py](utils/audio_encoder.py).
- A device `NeuralNetwork` runs the Whisper encoder stage.
- Host/device helper nodes prepare the recursive decoder loop and feed token sequences back into the decoder network.
- [utils/annotation_node.py](utils/annotation_node.py) maps decoded tokens to text and color commands, and [utils/led_changer_script.py](utils/led_changer_script.py) updates the device LED.
- The live camera stream is tinted/annotated to match the decoded color word.

## Constraints

- [main.py](main.py) explicitly raises on non-RVC4 platforms.
- The README notes that host recording crashes in standalone mode; standalone is effectively for pre-recorded audio only.
- The current CLI uses `-d/--device`, not `--device_ip` as the README examples say.
- In the current repo state, [main.py](main.py) loads `whisper_tiny_en_decoder` YAML for both the encoder and decoder model description variables, which is suspicious and should be treated carefully before reusing the model-loading path.

## Related Examples

- [../../generic-example](../../generic-example/): use this when you need the simplest single-model scaffold instead of speech-specific recursion
- [../../../apps/default-app](../../../apps/default-app/): use this when you need a packaged baseline app without speech logic
- [../../../integrations/rerun](../../../integrations/rerun/): use this when your goal is external visualization rather than speech-driven UI feedback

## Validation

- `Run:` `python3 main.py`
- `File mode:` `python3 main.py --audio_file <FILE>`
- `Success looks like:` the Visualizer shows `Camera` and `Decoded Audio Message`, pressing `r` records a short clip in peripheral mode, and recognized color words drive the LED/tint output
- `Common failure meaning:` the device is not RVC4, host audio dependencies are missing, standalone recording was attempted, or the current encoder/decoder model-loading path was assumed to be correct without verification
