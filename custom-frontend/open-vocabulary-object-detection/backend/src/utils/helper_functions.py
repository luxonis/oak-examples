from tokenizers import Tokenizer
import os
import requests
import onnxruntime
import numpy as np
import cv2
import base64
import random


QUANT_ZERO_POINT = 90.0
QUANT_SCALE = 0.003925696481

QUANT_VALUES = {
    "yolo-world": {
        "quant_zero_point": 90.0,
        "quant_scale": 0.003925696481,
    },
    "yoloe": {
        "quant_zero_point": 174.0,
        "quant_scale": 0.003328413470,
    },
    "yoloe-image": {
        "quant_zero_point": 137.0,
        "quant_scale": 0.002327915514,
    },
}


def pad_and_quantize_features(
    features, max_num_classes=80, model_name="yolo-world", precision="int8"
):
    """
    Pad features to (1, 512, max_num_classes) and quantize if precision is int8.
    For FP16, return padded float16 features (no quantization).
    """
    num_padding = max_num_classes - features.shape[0]
    padded_features = np.pad(
        features, ((0, num_padding), (0, 0)), mode="constant"
    ).T.reshape(1, 512, max_num_classes)

    if precision == "fp16":
        return padded_features.astype(np.float16)

    quant_scale = QUANT_VALUES[model_name]["quant_scale"]
    quant_zero_point = QUANT_VALUES[model_name]["quant_zero_point"]
    quantized_features = (padded_features / quant_scale) + quant_zero_point
    quantized_features = quantized_features.astype("uint8")
    return quantized_features


def extract_text_embeddings(
    class_names, max_num_classes=80, model_name="yolo-world", precision="int8"
):
    tokenizer_json_path = download_tokenizer(
        url="https://huggingface.co/openai/clip-vit-base-patch32/resolve/main/tokenizer.json",
        save_path="tokenizer.json",
    )
    tokenizer = Tokenizer.from_file(tokenizer_json_path)
    tokenizer.enable_padding(
        pad_id=tokenizer.token_to_id("<|endoftext|>"), pad_token="<|endoftext|>"
    )
    encodings = tokenizer.encode_batch(class_names)

    text_onnx = np.array([e.ids for e in encodings], dtype=np.int64)

    if model_name == "yolo-world":
        attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)

        textual_onnx_model_path = download_model(
            "https://huggingface.co/jmzzomg/clip-vit-base-patch32-text-onnx/resolve/main/model.onnx",
            "clip_textual_hf.onnx",
        )

        session_textual = onnxruntime.InferenceSession(
            textual_onnx_model_path,
            providers=[
                "TensorrtExecutionProvider",
                "CUDAExecutionProvider",
                "CPUExecutionProvider",
            ],
        )
        textual_output = session_textual.run(
            None,
            {
                session_textual.get_inputs()[0].name: text_onnx,
                "attention_mask": attention_mask,
            },
        )[0]
    elif model_name == "yoloe":
        if text_onnx.shape[1] < 77:
            text_onnx = np.pad(
                text_onnx, ((0, 0), (0, 77 - text_onnx.shape[1])), mode="constant"
            )

        textual_onnx_model_path = download_model(
            "https://huggingface.co/Xenova/mobileclip_blt/resolve/main/onnx/text_model.onnx",
            "mobileclip_textual_hf.onnx",
        )

        session_textual = onnxruntime.InferenceSession(
            textual_onnx_model_path,
            providers=[
                "TensorrtExecutionProvider",
                "CUDAExecutionProvider",
                "CPUExecutionProvider",
            ],
        )
        textual_output = session_textual.run(
            None,
            {
                session_textual.get_inputs()[0].name: text_onnx,
            },
        )[0]

        textual_output /= np.linalg.norm(
            textual_output, ord=2, axis=-1, keepdims=True
        )  # Normalize the output

    text_features = pad_and_quantize_features(
        textual_output, max_num_classes, model_name, precision
    )

    del session_textual

    return text_features


def extract_image_prompt_embeddings(
    image,
    max_num_classes=80,
    model_name="yolo-world",
    mask_prompt=None,
    precision="int8",
):
    # Select model and preprocess accordingly
    if model_name == "yoloe":
        image_resized = cv2.resize(image, (640, 640))
        image_array = image_resized.astype(np.float32) / 255.0
        image_array = np.transpose(image_array, (2, 0, 1))
        input_tensor = np.expand_dims(image_array, axis=0).astype(np.float32)
        model_url = (
            "https://huggingface.co/sokovninn/yoloe-v8l-seg-visual-encoder/resolve/main/"
            "yoloe-v8l-seg_visual_encoder.onnx"
        )
        model_path = "yoloe-v8l-seg_visual_encoder.onnx"
    else:
        input_tensor = preprocess_image(image)
        model_url = (
            "https://huggingface.co/sokovninn/clip-visual-with-projector/resolve/main/"
            "clip_visual_with_projector.onnx"
        )
        model_path = "clip_visual_with_projector.onnx"

    onnx_model_path = download_model(model_url, model_path)

    session = onnxruntime.InferenceSession(
        onnx_model_path,
        providers=[
            "TensorrtExecutionProvider",
            "CUDAExecutionProvider",
            "CPUExecutionProvider",
        ],
    )

    if model_name == "yoloe":
        if mask_prompt is None:
            prompts = np.zeros((1, 1, 80, 80), dtype=np.float32)
            prompts[0, 0, 5:75, 5:75] = 1.0
        else:
            prompts = np.asarray(mask_prompt, dtype=np.float32)
            if prompts.ndim == 2:
                if prompts.shape != (80, 80):
                    prompts = cv2.resize(
                        prompts, (80, 80), interpolation=cv2.INTER_NEAREST
                    )
                prompts = prompts[None, None, :, :]
            elif prompts.shape == (1, 1, 80, 80):
                pass
            else:
                raise ValueError("mask_prompt must have shape (80,80) or (1,1,80,80)")
        outputs = session.run(None, {"images": input_tensor, "prompts": prompts})
    else:
        input_name = session.get_inputs()[0].name
        outputs = session.run(None, {input_name: input_tensor})

    image_embeddings = outputs[0].squeeze(0).reshape(1, -1)
    image_features = pad_and_quantize_features(
        image_embeddings, max_num_classes, model_name, precision
    )

    del session

    return image_features


def download_tokenizer(url, save_path):
    if not os.path.exists(save_path):
        print(f"Downloading tokenizer config from {url}...")
        with open(save_path, "wb") as f:
            f.write(requests.get(url).content)
    return save_path


def download_model(url, save_path):
    if not os.path.exists(save_path):
        print(f"Downloading model from {url}...")
        response = requests.get(url)
        if response.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(response.content)
            print(f"Model saved to {save_path}.")
        else:
            raise Exception(
                f"Failed to download model. Status code: {response.status_code}"
            )
    else:
        print(f"Model already exists at {save_path}.")

    return save_path


def preprocess_image(image):
    """Preprocess image for CLIP vision model input"""
    image = cv2.resize(image, (224, 224))

    image_array = np.array(image).astype(np.float32) / 255.0

    mean = np.array([0.48145466, 0.4578275, 0.40821073])
    std = np.array([0.26862954, 0.26130258, 0.27577711])

    image_array = (image_array - mean) / std

    image_array = np.transpose(image_array, (2, 0, 1))
    image_array = np.expand_dims(image_array, axis=0)

    return image_array.astype(np.float32)


def base64_to_cv2_image(base64_data_uri: str):
    if "," in base64_data_uri:
        header, base64_data = base64_data_uri.split(",", 1)
    else:
        base64_data = base64_data_uri

    binary_data = base64.b64decode(base64_data)
    np_arr = np.frombuffer(binary_data, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    return img


def generate_high_contrast_colormap(
    size=256, min_hue_jump=20, min_sv_jump=100, seed=42
):
    """
    Creates a highly randomized OpenCV colormap where:
      - index 0 is black
      - hue/saturation/value vary randomly
      - neighboring colors stay strongly different
      - output is (256,1,3) uint8 for cv2.applyColorMap
    """
    assert size >= 2
    random.seed(seed)

    n = size - 1  # excluding black at index 0

    # Random H, S, V
    hues = np.random.randint(0, 180, n)
    sats = np.random.randint(240, 256, n)
    vals = np.random.randint(200, 256, n)

    # Shuffle initial order
    order = list(range(n))
    random.shuffle(order)

    hues = hues[order]
    sats = sats[order]
    vals = vals[order]

    # Enforce minimum contrast between neighbors
    for i in range(1, n):
        if abs(int(hues[i]) - int(hues[i - 1])) < min_hue_jump:
            hues[i] = (hues[i] + 90) % 180  # push hue away

        if abs(int(sats[i]) - int(sats[i - 1])) < min_sv_jump:
            sats[i] = 255 - sats[i]

        if abs(int(vals[i]) - int(vals[i - 1])) < min_sv_jump:
            vals[i] = 255 - vals[i]

    hsv = np.zeros((size, 1, 3), dtype=np.uint8)
    # 0 = black
    hsv[0, 0] = [0, 0, 0]
    # fill 1..255
    hsv[1:, 0, 0] = hues
    hsv[1:, 0, 1] = sats
    hsv[1:, 0, 2] = vals

    # Convert HSV → BGR for OpenCV
    bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    return bgr
