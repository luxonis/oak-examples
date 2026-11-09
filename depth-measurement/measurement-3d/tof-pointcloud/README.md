# ToF point cloud in the Viewer

This example starts from `depthai-core/examples/python/ToF/tof_pointcloud.py`. It aligns ToF depth to a color camera and displays a colorized point cloud in the DepthAI Viewer.

## Run

```bash
pip install -r requirements.txt
DEPTHAI_DEVICE_NAME_LIST=10.11.0.180 python3 main.py
```

Open **http://localhost:8082** and select the `pcl` topic in the 3D view. Press `q` in the Viewer or Ctrl+C in the terminal to stop.

Use the **ToF mode** selector above the Viewer to switch between **Close range**, **Mid range**, and **Far range** while streaming. These apply the low-, mid-, and high-range ToF presets; Far range is the default. Port 8082 serves the selector page and embeds the Viewer from port 8083.

The pipeline selects the ToF socket automatically and uses `CAM_A` for color on RVC4, or `CAM_C` on RVC2. The device needs both ToF and a color camera. The default depth profile is high range, with 30 FPS requested and 640×400 color output.

This is a host-side example. All display is in the Viewer; there are no desktop display or filter-control windows.
