# Object Volume Measurement 3D

This example demonstrates a practical approach for measuring objects in 3D using DepthAI.\
On the DepthAI backend, it runs **YOLOE** model on-device, with configurable class labels and confidence threshold - both controllable via the frontend.
The custom frontend lets you click a detected object in the Video stream, the backend then segments that instance, builds a segmented point cloud, and computes dimensions and volume in real time. Users can switch between two measurement methods: Object-Oriented Bounding Box and Ground-plane Height Grid.\
The frontend is built with `@luxonis/depthai-viewer-common` package, and combined with the [default oakapp docker image](https://hub.docker.com/r/luxonis/oakapp-base), enabling remote access via WebRTC.

> **Note:** This example works only on RVC4 in standalone mode.

## Demo

![extended-3d-measurement](media/demo.gif)

## Usage

Running this example requires a **Luxonis device** connected to your computer. Refer to the [documentation](https://docs.luxonis.com/software-v3/) to setup your device if you haven't done it already.

### Model Options

This example currently uses **YOLOE** - a fast and efficient object detection model, that outputs bounding boxes and segmentation masks.

### Measurement methods

The app provides two ways to measure objects from the segmented point clouds:

#### 1. Object-Oriented Bounding Box (OBB)

This method uses Open3D's `get_minimal_oriented_bounding_box()`, which computes the minimal 3D box that encloses the segmented point cloud.\
The resulting box provides the object's dimensions (L, W, H) and the volume is computed as: V = L x W x H\
Temporal smoothing is applied to keep the box stable and prevents sudden flips. It combines a low pass filter (EMA) for center and size, and spherical linear interpolation (SLERP) for rotations.\
This method is fast but may overestimate volume for objects with irregular shapes.

#### 2. Ground-plane Height Grid (HG)

For this method the objects are required to rest on a flat surface (e.g desk or floor). It uses the flat surface as a reference support plane, then estimates the footprint and the height by
grid-based slicing of the objects top surface.

**How it works:**

1. Plane capture: we run RANSAC on the scene point cloud and validate with the IMU that the plane is ground-like (plane normal parallel to gravity).
   The app shows Calculating / OK / Failed status in the overlay of the Video Stream and re-requests capture if the camera has been moved or plane becomes invalid.
2. Transform the object point cloud into the ground/table frame.
3. Compute a minimum-area rectangle for the footprint of the object. From here we get the L, W and yaw (rotation along the z axis).
4. Volume calculation: the footprint polygon is divided into a 2D grid of square cells (default 5 mm each). For every cell inside the footprint, the algorithm estimates a height value by looking at the object points that fall into that cell. The base area of each cell = (cell size)² and height = cell height above the ground plane.\
   The total object volume is obtained by summing the volumes of each cell across the grid. The object's height H is computed from this height grid also.
5. Temporal smoothing is applied to the footprint, yaw, height, and dimensions (EMA-based), with rejection of sudden jumps.

This grid-integration method makes the volume estimation more robust to irregular and uneven object surfaces compared to just taking the bounding box. However, it is sensitive to plane fitting errors.

> **Note:** the object dimensions are still represented as a box, even for irregular objects.

### Outputs

The backend publishes:

- Video Stream
- Detections Overlay with segmentation masks and bounding boxes
- Pointclouds Stream (whole scene and segmented when measuring an object)
- Measurements Overlay (OBB / HG wireframe from the object dimensions on the Video Stream)
- Plane status (HG only)
- Dimensions and volume measurements with the Detections Overlay

## Standalone Mode (RVC4 only)

Running the example in the standalone mode, app runs entirely on the device.
To run the example in this mode, first install the `oakctl` tool using the installation instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

The app can then be run with:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

Once the app is built and running you can access the DepthAI Viewer locally by opening `https://<OAK4_IP>:9000/` in your browser (the exact URL will be shown in the terminal output).

### Remote access

1. You can upload oakapp to Luxonis Hub via oakctl
2. And then you can just remotely open App UI via App detail page
