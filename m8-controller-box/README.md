# M8 Controller Box (PR1)

The **M8 Controller Box (PR1)** is a M8-connected expansion module designed for integrating CAN devices, GPIO, relays, and peripheral interfaces into OAK-based systems.

This document serves as the **primary usage reference** for the M8 Controller Box within `oak-examples`.


## Key Features

### CAN Interface

* Supports **CAN 2.0A and 2.0B**
* Baud rates up to **1 Mbps**
* Native **Linux SocketCAN** interface

> CAN setup is handled within example applications. Refer to the `can-example` for usage.



### USB Audio

* Integrated **buzzer / 3.5mm audio output**
* Available via internal USB connection



### USB Expansion

* **2× USB-A ports**
* USB 2.0 speeds
* Up to **500mA current limit (shared)**



### Serial Interface

* **1× RS232 interface**



### Isolated Strobe Driver

* Supports **5–24V strobe lights**
* Electrically isolated output



### GPIO

* **16× GPIO pins**
* 3.3V logic level
* Reverse voltage protection and ESD protection
* Configurable as input or output

**Electrical limits:**

* Total combined current must not exceed **50mA**



### Power Relays

* **4× SPDT latching relays**
* Up to **16A current**
* Maximum **400VAC switching voltage**



### User Interface

* **3× physical buttons**
* **3× status LEDs**



## Pinout

Device-level pinout is shown below:

![M8 Controller Box Schematics](media/schematics.png)



## Example Applications

The repository includes reference applications demonstrating typical usage.

### simple-example

* Blinks LED on GPIO18
* Button on GPIO19 toggles LED on GPIO17



### depthai-example

* Based on Luxonis hand pose detection
* Turns on LED (GPIO17) when a hand is detected



### can-example

* Monitors button on GPIO19
* Sends CAN frame on press via `can0`
* Uses Linux SocketCAN (`python-can`)



## Notes

* GPIO and peripheral control is exposed via the **u2if (USB-to-interfaces) protocol**
* Example applications demonstrate recommended interaction patterns



## Support

For integration support or early access features, contact Luxonis.
