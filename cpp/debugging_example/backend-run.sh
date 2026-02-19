#!/bin/sh
echo "Starting Backend"
gdbserver 0.0.0.0:5678 /app/build/main
