# ToF pointcloud demo

This example shows how to use `depthai`'s ToF node and visualize some of its outputs, including `depth` and `depthRaw`.
Moreover, this demo also turns the `depth` images into pointclouds which are then visualized, side-by-side with the `depth` frames, using Open3D.
Finally, through an interactive GUI, one can adjust the ToF's underlying filters, allowing one to get intution of the filtering techniques used or to tune the settings for one's specific needs.

**NOTE**: This example requires a ToF camera. You can get one from the official [Luxonis store](https://shop.luxonis.com/products/oak-d-sr-poe).

## Demo
![output](https://github.com/user-attachments/assets/ab978162-cb00-4f95-89b1-f7b06c60fe7c)

## Usage

### Installation

The demo was tested with **Python 3.12** and several external dependencies installed.
You can install them by running:

```bash
python3 -m pip install -r requirements.txt
```

### Examples

Run the examples as follows:

```bash
python3 tof.py
```
