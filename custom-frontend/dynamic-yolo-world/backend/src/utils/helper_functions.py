from tokenizers import Tokenizer
import os
import requests
import onnxruntime
import numpy as np
import cv2
import base64

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
    }
} 


def pad_and_quantize_features(features, max_num_classes=80, model_name="yolo-world"):
    """
    Apply padding and quantization to feature embeddings.

    Args:
        features: Input feature array to be padded and quantized
        max_num_classes: Maximum number of classes for padding

    Returns:
        Padded and quantized features as uint8 array
    """
    quant_scale = QUANT_VALUES[model_name]["quant_scale"]
    quant_zero_point = QUANT_VALUES[model_name]["quant_zero_point"]
    num_padding = max_num_classes - features.shape[0]
    padded_features = np.pad(
        features, ((0, num_padding), (0, 0)), mode="constant"
    ).T.reshape(1, 512, max_num_classes)
    quantized_features = (padded_features / quant_scale) + quant_zero_point
    quantized_features = quantized_features.astype("uint8")
    return quantized_features


def extract_text_embeddings(class_names, max_num_classes=80, model_name="yolo-world"):
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


    text_features = pad_and_quantize_features(textual_output, max_num_classes, model_name)

    del session_textual

    return text_features


def extract_image_prompt_embeddings(image, max_num_classes=80):
    input_tensor = preprocess_image(image)

    onnx_model_path = download_model(
        "https://huggingface.co/sokovninn/clip-visual-with-projector/resolve/main/clip_visual_with_projector.onnx",
        "clip_visual_with_projector.onnx",
    )

    session = onnxruntime.InferenceSession(
        onnx_model_path,
        providers=[
            "TensorrtExecutionProvider",
            "CUDAExecutionProvider",
            "CPUExecutionProvider",
        ],
    )

    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: input_tensor})
    image_embeddings = outputs[0]  # Shape: (1, 512)

    image_embeddings = image_embeddings.squeeze(0).reshape(1, -1)  # Shape: (1, 512)

    image_features = pad_and_quantize_features(image_embeddings, max_num_classes)

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

    # Convert to numpy array and normalize
    image_array = np.array(image).astype(np.float32) / 255.0

    # CLIP normalization values
    mean = np.array([0.48145466, 0.4578275, 0.40821073])
    std = np.array([0.26862954, 0.26130258, 0.27577711])

    # Normalize
    image_array = (image_array - mean) / std

    # Convert to CHW format and add batch dimension
    image_array = np.transpose(image_array, (2, 0, 1))  # HWC to CHW
    image_array = np.expand_dims(image_array, axis=0)  # Add batch dimension

    return image_array.astype(np.float32)


def base64_to_cv2_image(base64_data_uri: str):
    if "," in base64_data_uri:
        header, base64_data = base64_data_uri.split(",", 1)
    else:
        base64_data = base64_data_uri  # In case frontend strips header

    binary_data = base64.b64decode(base64_data)
    np_arr = np.frombuffer(binary_data, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    return img
