
First build the example with (adjust for yourself):
```
cmake -S . -B build \
  -DHSB_SOURCE_DIR=/home/aljaz/work-luxonis/holoscan-sensor-bridge \
  -DHSB_BUILD_RGB_STREAM=ON \
  -Ddepthai_DIR=/home/aljaz/work-luxonis/depthai-core/build \
  -DXLink_DIR=/home/aljaz/work-luxonis/depthai-core/build/_deps/xlink-build \
  -Dlibnop_DIR=/home/aljaz/work-luxonis/depthai-core/build/_deps/libnop-build/lib/cmake/libnop \
  -Dnlohmann_json_DIR=/home/aljaz/work-luxonis/depthai-core/build/_deps/nlohmann_json-build \
  -Dxtensor_DIR=/home/aljaz/work-luxonis/depthai-core/build/_deps/xtensor-build \
  -Dxtl_DIR=/home/aljaz/work-luxonis/depthai-core/build/_deps/xtl-build

cmake --build build -j
./build/rgb_stream

```


Tested on Nvidia jetson orin nano, with JetPack 6.2.1 and cuda 12.6. To install the containers follow the guide:
1) (host) j[etson setup](https://docs.nvidia.com/holoscan/sensor-bridge/2.0.0/setup.html#sd-tab-item-1): one change is here `sudo nmcli con add con-name hololink-eth0 ifname eth0 type ethernet ip4 192.168.0.101/24` where you set to the IP you have (might have to add a default path aswell). Other change is in `docker/Dockerfile` where you change the version to: `    echo "deb https://repo.download.nvidia.com/jetson/common r36.4 main" > /etc/apt/sources.list.d/nvidia-l4t-apt-source.list && \
    echo "deb https://repo.download.nvidia.com/jetson/t234 r36.4 main" >> /etc/apt/sources.list.d/nvidia-l4t-apt-source.list && \`
2) then the [demo containers](https://docs.nvidia.com/holoscan/sensor-bridge/2.0.0/build.html): run with `--igpu`. 

Copy the python script from `../jetson/linux_rgb_body_pose.py` to your jetson into the examples. The only difference with the default linux_body_pose_estimation.py example is input is 640 x 640 and the data input is RGB888i instead of IMX sensor data in Bayer format.

to run `examples/linux_rgb_body_pose.py`:
- get an onnx of the yolov8l model
- adjust path name in the script
- change the `examples/linux_rgb_body_pose.yaml` line   `is_engine_path` to `false`

Once setup run the container:
```
xhost +
sh docker/demo.sh
```

and run the demo with:
- first run (with sudo for socket access) on your computer / camera: `sudo ./build/rgb_stream`
- then: `python examples/linux_rgb_body_pose.py --hololink <ip of sender camera>' in the container on jetson, it should auto pickup the UDP packets.



Some tests:
- running 640 x 640 uncompressed stream
- YOLO v8l pose model (converted to tensorRT) and  **not** quantized
- Nvidia Jetson orin Nano


Latency hovers around 700ms and the stream has low FPS (5 - 10 FPS). We attribute this to the Orin Nano device being underpowered and the demo example being unoptimized and the model being unquantized.