import requests
import os
from typing import Tuple
from tqdm import tqdm


def download_model(input_shape: Tuple[int, int]) -> str:
    """Downloads ONNX model from Zoo if not already present locally"""
    base_path = "./models"
    if input_shape == (640, 416):
        model = "luxonis/foundation-stereo:640x416"

    elif input_shape == (1280, 800):
        model = "luxonis/foundation-stereo:1280x800"
    else:
        ValueError(f"No known model for input shape `{input_shape}`")

    local_filename = model.replace("/", "_").replace(":", "_")  # sanitization
    local_filename = os.path.join(base_path, local_filename + ".onnx")
    if os.path.exists(local_filename):
        print(f"Using cached model `{local_filename}`")
    else:
        print(f"Downloading model `{model}` from Zoo...")
        os.makedirs(base_path, exist_ok=True)
        download_base_model(model_slug=model, local_filename=local_filename)

    return local_filename


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
