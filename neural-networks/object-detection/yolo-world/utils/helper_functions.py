from tokenizers import Tokenizer
from tqdm import tqdm
import os
import requests
import onnxruntime
import numpy as np

QUANT_ZERO_POINT = 90.0
QUANT_SCALE = 0.003925696481


def extract_text_embeddings(class_names, max_num_classes=80):
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
    attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)

    textual_onnx_model_path = "clip_textual_hf.onnx"
    download_base_model(
        model_slug="luxonis/yolo-world-l:clip-textual-hf",
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
        {
            session_textual.get_inputs()[0].name: text_onnx,
            "attention_mask": attention_mask,
        },
    )[0]

    num_padding = max_num_classes - len(class_names)
    text_features = np.pad(
        textual_output, ((0, num_padding), (0, 0)), mode="constant"
    ).T.reshape(1, 512, max_num_classes)
    text_features = (text_features / QUANT_SCALE) + QUANT_ZERO_POINT
    text_features = text_features.astype("uint8")

    del session_textual

    return text_features


def download_tokenizer(url, save_path):
    if not os.path.exists(save_path):
        print(f"Downloading tokenizer config from {url}...")
        with open(save_path, "wb") as f:
            f.write(requests.get(url).content)
    return save_path


def download_base_model(model_slug: str, local_filename: str):
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
        block_size = 8192  # 8KB chunks
        progress_bar = tqdm(
            total=total_size, unit="iB", unit_scale=True, desc=local_filename
        )

        with open(local_filename, "wb") as f:
            for chunk in r.iter_content(chunk_size=block_size):
                if chunk:
                    f.write(chunk)
                    progress_bar.update(len(chunk))
        progress_bar.close()
