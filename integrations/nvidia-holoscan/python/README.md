For full support you need to clone and build the HSB emulator from
[holoscan-sensor-bridge](https://github.com/nvidia-holoscan/holoscan-sensor-bridge.git):

```bash
git clone https://github.com/nvidia-holoscan/holoscan-sensor-bridge.git
cd holoscan-sensor-bridge
cmake -S src/hololink/emulation -B build
cmake --build build -j
```

This build creates a Python virtual environment at `build/env` with the compiled
`hololink.emulation` extension (`_emulation*.so`) installed.

Install this integration's runtime requirements into that environment and run examples
with the same Python interpreter:

```bash
# activate your env first
# conda activate hololink-test

cd /home/aljaz/work-luxonis/oak-examples/integrations/nvidia-holoscan/holoscan-sensor-bridge

# install the lightweight emulation Python package structure
python -m pip install src/hololink/emulation/python/

# build native emulation modules
cmake -S src/hololink/emulation -B build
cmake --build build -j

# resolve site-packages for current python
PKG_DIR="$(python - <<'PY'
import site
print(next(p for p in site.getsitepackages() if p.endswith('site-packages')))
PY
)"

# copy built module(s) into installed package
mkdir -p "$PKG_DIR/hololink/emulation/sensors"
cp build/_emulation*.so "$PKG_DIR/hololink/emulation/"

SENS_SO="$(find build -name '_emulation_sensors*.so' -print -quit)"
if [ -n "$SENS_SO" ]; then
  cp "$SENS_SO" "$PKG_DIR/hololink/emulation/sensors/"
fi

# verify + run
python -c "from hololink import emulation; print('OK:', emulation.HSBEmulator)"
python /home/aljaz/work-luxonis/oak-examples/integrations/nvidia-holoscan/rgb_stream.py

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