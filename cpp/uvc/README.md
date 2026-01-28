# UVC Example

## Overveiw

This project provides a minimal C++ example demonstrating how to run a USB Video Class (UVC) camera as a standalone Linux application on RVC4.

The application configures the device to expose itself over USB as a standard UVC-compliant camera, allowing it to be recognized by host systems (Linux, Windows, macOS) without requiring custom drivers. Video frames are produced by the application and streamed to the host using the UVC gadget framework.

The application uses a modified UVC library from https://gitlab.freedesktop.org/camera/uvc-gadget.

## Standalone Mode (RVC4 only)

Running the example in standalone mode builds and deploys it as an OAK app so that it runs completely on the device.

1. Make sure git submodules are up to date:

   ```bash
   git submodule update --init --recursive
   ```

2. Install `oakctl` by following the instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

3. Connect to your device:

   ```bash
   oakctl connect <DEVICE_IP>
   ```

4. From the `cpp/uvc` directory, run the packaged app:

   ```bash
   oakctl app run .
   ```

`oakctl` uses the provided `oakapp.toml` to build the C++ project inside the Luxonis base container and deploy it to the device. Configuration tweaks such as changing the camera resolution or registering more topics should be done in `src/uvc_example.cpp`, then re-run `oakctl app run ./cpp/uvc`.
