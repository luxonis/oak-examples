# Hand Pose Example with M8 Controller LED Trigger

This project is based on the official Luxonis hand pose example:

https://github.com/luxonis/oak-examples/tree/main/neural-networks/pose-estimation/hand-pose

It demonstrates hand detection and hand landmark estimation using DepthAI.

> **Note:** This example works only on OAK4 in standalone mode. It is not supported in host-driven peripheral mode because the M8 Controller Box is connected directly to the OAK4 device.

## Added Functionality

In addition to the original example, this version integrates an **M8 Controller Box**.

When a hand is detected:

- **LED 1** on the M8 controller will turn on.

This allows simple hardware feedback triggered directly from hand detection events.

## Usage

Running this example requires an OAK4 device with the M8 Controller Box attached.

## Standalone Mode (RVC4 only)

Install `oakctl` by following the instructions [here](https://docs.luxonis.com/software-v3/oak-apps/oakctl).

Then run the example from this directory:

```bash
oakctl connect <DEVICE_IP>
oakctl app run .
```

This builds the app from the local `oakapp.toml`, deploys it to the OAK4 device, and starts it in standalone mode.

## Peripheral Mode

This mode is not supported for this example. The M8 Controller Box must be attached directly to the OAK4 device running the app.
