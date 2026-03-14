from tokenizers import Tokenizer
from tqdm import tqdm
import os
import requests
import onnxruntime
import numpy as np
import depthai as dai


QUANT_VALUES = {
    "yoloe": {
        "quant_zero_point": 174.0,
        "quant_scale": 0.003328413470,
    },
}


def pad_and_quantize_features(
    features, max_num_classes=80, model_name="yoloe", precision="int8"
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
    return quantized_features.astype("uint8")


def extract_text_embeddings(class_names, max_num_classes=80, precision="fp16"):
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

    if text_onnx.shape[1] < 77:
        text_onnx = np.pad(
            text_onnx, ((0, 0), (0, 77 - text_onnx.shape[1])), mode="constant"
        )

    textual_onnx_model_path = "mobileclip_textual_hf.onnx"
    download_base_model(
        model_slug="luxonis/yoloe-v8-l:mobileclip-textual-hf",
        local_filename=textual_onnx_model_path,
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
        {session_textual.get_inputs()[0].name: text_onnx},
    )[0]
    del session_textual

    textual_output /= np.linalg.norm(textual_output, ord=2, axis=-1, keepdims=True)

    return pad_and_quantize_features(
        textual_output, max_num_classes, precision=precision
    )


def download_tokenizer(url, save_path):
    if not os.path.exists(save_path):
        print(f"Downloading tokenizer config from {url}...")
        with open(save_path, "wb") as f:
            f.write(requests.get(url).content)
    return save_path


def download_base_model(model_slug: str, local_filename: str):
    if os.path.exists(local_filename):
        print(f"Model already exists at {local_filename}.")
        return

    model_name_slug = model_slug.split("/")[-1].split(":")[0]
    model_variant_slug = model_slug.split("/")[-1].split(":")[1]

    model_res = requests.get(
        "https://easyml.cloud.luxonis.com/models/api/v1/models",
        params={"slug": model_name_slug, "is_public": True},
    )
    model_id = model_res.json()[0]["id"]
    variant_res = requests.get(
        "https://easyml.cloud.luxonis.com/models/api/v1/modelVersions",
        params={
            "model_id": model_id,
            "variant_slug": model_variant_slug,
            "is_public": True,
        },
    )
    model_variant_id = variant_res.json()[0]["id"]
    download_res = requests.get(
        f"https://easyml.cloud.luxonis.com/models/api/v1/modelVersions/{model_variant_id}/download",
    )
    download_link = download_res.json()[0]["download_link"]
    download_file(download_link, local_filename)


def download_file(download_link: str, local_filename: str):
    with requests.get(download_link, stream=True) as r:
        r.raise_for_status()

        total_size = int(r.headers.get("content-length", 0))
        progress_bar = tqdm(
            total=total_size, unit="iB", unit_scale=True, desc=local_filename
        )

        with open(local_filename, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    progress_bar.update(len(chunk))
        progress_bar.close()


def read_intrinsics(device: dai.Device, width: int, height: int) -> tuple:
    calibData = device.readCalibration2()
    M2 = np.array(
        calibData.getCameraIntrinsics(dai.CameraBoardSocket.CAM_A, width, height)
    )
    fx = M2[0, 0]
    fy = M2[1, 1]
    cx = M2[0, 2]
    cy = M2[1, 2]
    return fx, fy, cx, cy
