# M8 CAN Transmission Example (Button Triggered)

This example demonstrates how to send data over the **CAN bus** from the M8 Controller Box by pressing a physical button.

The application runs inside a container directly on the device and uses `python-can` with the Linux SocketCAN interface.

## Functionality

This example performs the following actions:

- Monitors the button connected to **GPIO pin 19**.
- When the button is pressed, a CAN frame is transmitted over the M8 CAN interface (`can0`).

This provides a minimal, practical reference for sending CAN messages from a containerized application running on the OAK4 device.

## CAN Interface Setup (Required)

Before running the application, the CAN interface must be configured on the target device where CAN messages should be transmitted.

Run the following commands on the device:

```bash
sudo ip link set can0 type can bitrate 500000
sudo ip link set can0 up
```

This:

- Configures the CAN bitrate to **500 kbps**
- Brings the `can0` interface online

The bitrate must match the rest of the CAN network.

## Monitoring CAN Traffic

To verify transmission, you can listen to CAN traffic on a Linux system using:

```bash
candump can0
```

When the button on **pin 19** is pressed, a CAN frame will appear on the bus.

## Use Case

This example serves as a minimal reference implementation for:

- Sending CAN messages from the M8 Controller Box
- Integrating containerized applications with CAN-based systems
- Trigger-based CAN communication using GPIO inputs

It can be extended to transmit structured data, control messages, or sensor outputs over CAN.
