import argparse
import os
import shutil
import subprocess
from pathlib import Path

import depthai as dai
import onnx
import torch
from luxonis_ml.nn_archive.archive_generator import ArchiveGenerator
from onnxsim import simplify
from torch import nn


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "platform",
        type=str,
        choices=["rvc2", "rvc3", "rvc4"],
        help="Platform to generate NN archive for.",
    )

    return parser.parse_args()


def generate_nn_archive(
    cfg_dict: dict, path_to_onnx: str, out_path: str, platform: dai.Platform
):
    script_dir = Path(os.path.realpath(__file__)).parent
    work_dir = script_dir / "out"
    work_dir.mkdir(exist_ok=True)

    # Create NN archive with ONNX model
    generator = ArchiveGenerator(
        archive_name=cfg_dict["model"]["metadata"]["name"],
        save_path=str(work_dir),
        cfg_dict=cfg_dict,
        executables_paths=[path_to_onnx],
    )
    archive_path = generator.make_archive()
    # Convert NN archive to RVC format using modelconverter
    subprocess.run(
        [
            "modelconverter",
            "convert",
            platform.name.lower(),
            "--path",
            str(archive_path),
            "--to",
            "nn_archive",
            "--output-dir",
            "nn_archive_out",
        ],
        cwd=work_dir,
        check=True,
    )
    final_model_path = (
        work_dir
        / f"output/nn_archive_out/{cfg_dict['model']['metadata']['name']}.{platform.name.lower()}.tar.xz"
    )
    shutil.copy(
        final_model_path,
        out_path,
    )


def generate_model(
    model: nn.Module,
    cfg_dict: dict,
    output_path: str,
    simplify_model: bool,
    platform: dai.Platform,
):
    onnx_path = cfg_dict["model"]["metadata"]["path"]

    input_tensors = []
    input_names = []
    output_names = []
    for inp in cfg_dict["model"]["inputs"]:
        inp_tensor = torch.ones(inp["shape"], dtype=getattr(torch, inp["dtype"]))
        input_tensors.append(inp_tensor)
        input_names.append(inp["name"])
    for out in cfg_dict["model"]["outputs"]:
        output_names.append(out["name"])

    if len(input_tensors) == 1:
        input_tensors = input_tensors[0]
    else:
        input_tensors = tuple(input_tensors)
    torch.onnx.export(
        model,
        input_tensors,
        onnx_path,
        opset_version=12,
        dynamo=False,
        do_constant_folding=True,
        input_names=input_names,
        output_names=output_names,
    )

    if simplify_model:
        # Use onnx-simplifier to simplify the onnx model
        onnx_model = onnx.load(onnx_path)
        model_simp, check = simplify(onnx_model)
        onnx.save(model_simp, onnx_path)

    generate_nn_archive(cfg_dict, onnx_path, output_path, platform)
    try:
        os.remove(onnx_path)
    except Exception:
        pass
