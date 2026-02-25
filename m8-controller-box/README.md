# M8 Controller Box (PR1 Prototype)

The **M8 Controller Box (PR1)** is a versatile USB-connected I/O and communication expansion module designed to simplify integration with CAN devices, sensors, relays, and general-purpose GPIO.

It connects directly to your host device via USB and provides a compact, robust interface for industrial and embedded applications.

## Key Features

### USB ↔ CAN Bus Interface

- Integrated **USB to CAN transceiver**
- Connected internally over an on-board **USB 2.0 hub**
- Powered by **candleLight firmware**
- Compatible with **can-utils** on Linux
- Optional **120Ω termination resistor** (not enabled by default)

**Linux setup example:**

```bash
sudo ip link set can0 type can bitrate 500000
sudo ip link set can0 up
cansend can0 123#1122334455667788
```

Note: Linux is required for CAN functionality.

### USB Audio (Speaker)

- Integrated via USB hub using **PCM2912APJTR**
- No additional drivers required (Linux tested)

### USB 2.0 Expansion

- USB-A ports act as **USB 2.0 extensions**
- Connected via internal USB hub
- Up to **500mA current limit**

### UART1 – RS232

Available via dedicated interface.

Contact us for configuration and usage details.

### FSYNC & Strobe

Hardware support available.

Contact us for integration support and documentation.

### IO Interface (via rp2040_u2if)

General-purpose I/O is handled through the **RP2040 USB-to-interface firmware**:

Repository:
https://github.com/luxonis/rp2040_u2if

**Setup:**

1. Download the repository
2. Install dependencies
3. Flash firmware
4. Refer to pinout diagram for GPIO mapping

## Buttons & LEDs

**Buttons (Top → Bottom):**

- GPIO19
- GPIO20
- GPIO21

**LEDs (Top → Bottom):**

- GPIO17
- GPIO16
- GPIO18

## GPIO Overview

- GPIOs: **0–13, 26, 27**
- GPIO64–71 available
- Configurable as:
  - Outputs
  - Inputs

## Relays

Relays are present in hardware but **not yet supported in firmware**.

Contact us for early access support.

## What’s in the Box

- M8 Controller Box (PR1 Prototype)
- M8 Cable (Male–Female)
- Plug-in screw terminals:
  - 3× 6-pin
  - 1× 4-pin
  - 2× 3-pin

## OS & Prerequisites

- Linux required for CAN functionality
- USB configuration may require:
  - USB muxing
  - Forcing USB Host mode

Setup differs between **OAK-4 S** and **OAK-4 D**.

(Example configuration guide coming soon.)

## Pinout Diagram

![M8 Controller Box Schematics](media/schematics.png)

## Example Application

An example application showcasing currently supported functionality will be available in:

`oak-examples/m8-controller-box`

(TODO – coming soon)

## Support

For integration help, firmware support, or early-access features:

Please contact us.
