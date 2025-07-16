from transformers import AutoTokenizer
import os
import requests
import onnxruntime
import numpy as np

QUANT_ZERO_POINT = 90.0
QUANT_SCALE = 0.003925696481


def extract_text_embeddings(class_names, max_num_classes=80):
    tokenizer = AutoTokenizer.from_pretrained("openai/clip-vit-base-patch32")
    text = tokenizer(text=class_names, return_tensors="np", padding=True)
    text_onnx = text["input_ids"].astype(np.int64)
    attention_mask = (text_onnx != 0).astype(np.int64)

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

    num_padding = max_num_classes - len(class_names)
    text_features = np.pad(
        textual_output, ((0, num_padding), (0, 0)), mode="constant"
    ).T.reshape(1, 512, max_num_classes)
    text_features = (text_features / QUANT_SCALE) + QUANT_ZERO_POINT
    text_features = text_features.astype("uint8")

    del session_textual

    return text_features


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
