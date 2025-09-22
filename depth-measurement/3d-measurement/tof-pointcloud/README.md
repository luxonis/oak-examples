# ToF pointcloud example

This example shows how to use `depthai`'s ToF node and visualize some of its outputs, including `depth` and `depthRaw`.
Moreover, this demo also turns the `depth` images into pointclouds which are then visualized, side-by-side with the `depth` frames, using Open3D.
Finally, through an interactive GUI, one can adjust the ToF's underlying filters, allowing one to get intution of the filtering techniques used or to tune the settings for one's specific needs.

![output](https://github.com/user-attachments/assets/ab978162-cb00-4f95-89b1-f7b06c60fe7c)

**NOTE**: This example requires a ToF camera. You can get one from the official [Luxonis store](https://shop.luxonis.com/products/oak-d-sr-poe).

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

## Peripheral Mode

### Installation

You need to first prepare a **Python 3.10** environment (python versions 3.8 - 3.13 should work too) with the following packages installed:

- [DepthAI](https://pypi.org/project/depthai/),
- [Open3D](https://pypi.org/project/open3d/)

You can install these dependencies and others with:

```bash
pip install -r requirements.txt
```

Running in peripheral mode requires a host computer.

### Examples

```bash
python3 main.py
```

## Standalone Mode (RVC4 only)

> ⚠️ Luxonis ToF cameras are of the RVC2 variant only, standalone mode is not supported.
