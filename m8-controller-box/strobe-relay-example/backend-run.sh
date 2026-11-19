#!/bin/sh
# run as root inside container
echo "Starting Backend"
# echo "Setting GPIO 32 to 0"
# gpioset 0 32=0
# echo "Switching USB role"
# echo "host" > /sys/class/usb_role/a600000.ssusb-role-switch/role
# # start main app
# echo "Starting main.py"
exec python3 -u /app/main.py