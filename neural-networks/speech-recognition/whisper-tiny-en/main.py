import logging
import sys
import depthai as dai
from pathlib import Path

from utils.constants import Config
from utils.arguments import initialize_argparser
from utils import AudioEncoder, AnnotationNode, WhisperEncoder, WhisperDecoder


# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger()
logger.addHandler(logging.StreamHandler(sys.stdout))


_, args = initialize_argparser()

visualizer = dai.RemoteConnection(httpPort=8082)
device = dai.Device(dai.DeviceInfo(args.device)) if args.device else dai.Device()
platform = device.getPlatform().name
print(f"Platform: {platform}")

if platform != "RVC4":
    raise ValueError("This example is only supported for RVC4 platform.")

encoder_model_description = dai.NNModelDescription.fromYamlFile(
    f"whisper_tiny_en_decoder.{platform}.yaml"
)
encoder_archive_path = dai.getModelFromZoo(encoder_model_description)

decoder_model_description = dai.NNModelDescription.fromYamlFile(
    f"whisper_tiny_en_decoder.{platform}.yaml"
)
decoder_archive_path = dai.getModelFromZoo(decoder_model_description)


with dai.Pipeline(device) as pipeline:
    print("Creating pipeline...")
    # Encoder setup

    camera = pipeline.create(dai.node.Camera).build()
    camera_out = camera.requestOutput((1080, 720), dai.ImgFrame.Type.NV12, fps=30)

    audio_encoder = pipeline.create(AudioEncoder, args.audio_file)

    encoder_nn = pipeline.create(dai.node.NeuralNetwork)
    encoder_nn.setNNArchive(dai.NNArchive(archivePath=encoder_archive_path))
    audio_encoder.output.link(encoder_nn.input)

    encoder_postprocess = pipeline.create(WhisperEncoder)

    decoder_nn = pipeline.create(dai.node.NeuralNetwork)
    decoder_nn.setNNArchive(dai.NNArchive(archivePath=decoder_archive_path))
    encoder_postprocess.decoder_initialization.link(decoder_nn.input)

    recursive_decoder_process = pipeline.create(WhisperDecoder, Config.MEAN_DECODE_LEN)
    encoder_postprocess.passthrough.link(recursive_decoder_process.encoder_input)
    decoder_nn.out.link(recursive_decoder_process.decoder_input)

    # recursive link
    recursive_decoder_process.out.link(decoder_nn.input)
    encoder_postprocess = encoder_postprocess.build(
        encoder_nn.out, recursive_decoder_process.token_sequence
    )

    text_process = pipeline.create(AnnotationNode)
    camera_out.link(text_process.frame_intput)
    recursive_decoder_process.token_sequence.link(text_process.token_input)

    # Script node for LED
    led_changer = pipeline.create(dai.node.Script)
    led_changer.setScriptPath(Path(__file__).parent / "utils/led_changer_script.py")
    text_process.color_output.link(led_changer.inputs["color_in"])

    visualizer.addTopic("Camera", text_process.frame_out)

    # Add visualizer topic
    visualizer.addTopic("Decoded Audio Message", text_process.annotaion_out)

    print("Pipeline created.")

    pipeline.start()
    visualizer.registerPipeline(pipeline)

    while pipeline.isRunning():
        key = visualizer.waitKey(1)
        if key == ord("q"):
            print("Got q key. Exiting...")
            break
        else:
            audio_encoder.handle_key_press(key)
