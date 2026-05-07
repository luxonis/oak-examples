#!/bin/bash

# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Luxonis, Inc.
# 
# Contact: <support@luxonis.com>

# Log function for unified messages
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [UVC] $1"
}

CONFIGFS="/sys/kernel/config"
GADGET="$CONFIGFS/usb_gadget"
VID="0x05c6"
PID="0x90cb" 

# find serialno from cmdline
SERIAL=$(grep -o "androidboot.serialno=[A-Za-z0-9]*" /proc/cmdline | cut -d "=" -f2)
if [ -z "$SERIAL" ]; then
    log "Serial number not found in cmdline, using default"
    SERIAL="12345678"
fi

MANUF="Fast"
PRODUCT="Fast Station Camera"
UDC=$(ls /sys/class/udc | head -n1) # will identify the 'first' UDC
STILL_WIDTH="3840"
STILL_HEIGHT="2160"

log "=== Detecting platform:"
log "    product : $PRODUCT"
log "    udc     : $UDC"
log "    serial  : $SERIAL"
log "    still   : ${STILL_WIDTH}x${STILL_HEIGHT}"

remove_uvc_gadget() {
    if [ ! -d /sys/kernel/config/usb_gadget/g1/functions/uvc.0 ]; then
        log "    No uvc gadget found, nothing to remove"
        return 0
    fi

    pushd /sys/kernel/config/usb_gadget/g1 >/dev/null

    rm configs/c.1/uvc.0 2>/dev/null

    rm functions/uvc.0/streaming/header/h/* 2>/dev/null
    rm functions/uvc.0/streaming/header/h1/* 2>/dev/null
    rm functions/uvc.0/streaming/header/h/m 2>/dev/null
    rmdir functions/uvc.0/streaming/h264/h/* 2>/dev/null
    rmdir functions/uvc.0/streaming/h264/h 2>/dev/null
    rmdir functions/uvc.0/streaming/mjpeg/m/* 2>/dev/null
    rmdir functions/uvc.0/streaming/mjpeg/m1/* 2>/dev/null
    rmdir functions/uvc.0/streaming/mjpeg/m 2>/dev/null
    rmdir functions/uvc.0/streaming/mjpeg/m1 2>/dev/null
    rmdir functions/uvc.0/streaming/uncompressed/u/* 2>/dev/null
    rmdir functions/uvc.0/streaming/uncompressed/u1/* 2>/dev/null
    rmdir functions/uvc.0/streaming/uncompressed/u 2>/dev/null
    rmdir functions/uvc.0/streaming/uncompressed/u1 2>/dev/null

    rm functions/uvc.0/streaming/class/fs/* 2>/dev/null
    rm functions/uvc.0/streaming/class/hs/* 2>/dev/null
    rm functions/uvc.0/streaming/class/ss/* 2>/dev/null

    rmdir functions/uvc.0/streaming/header/h 2>/dev/null
    rmdir functions/uvc.0/streaming/header/h1 2>/dev/null

    rm functions/uvc.0/control/class/fs/* 2>/dev/null
    rm functions/uvc.0/control/class/ss/* 2>/dev/null
    rmdir functions/uvc.0/control/header/* 2>/dev/null

    rmdir functions/uvc.0/control/extensions/* 2>/dev/null

    rmdir functions/uvc.0 2>/dev/null

    popd >/dev/null

    if [ ! -d /sys/kernel/config/usb_gadget/g1/functions/uvc.0 ]; then
        log "    UVC gadget successfully removed!"
    else
        log "    Failed to remove UVC gadget!"
        exit 1
    fi

    return 0
}

create_frame() {
    # Example usage:
    # create_frame <function name> <width> <height> <format> <name>

    FUNCTION=$1
    WIDTH=$2
    HEIGHT=$3
    FORMAT=$4
    NAME=$5

    wdir=functions/$FUNCTION/streaming/$FORMAT/$NAME/${HEIGHT}p

    mkdir -p "$wdir"
    echo "$WIDTH" > "$wdir/wWidth"
    echo "$HEIGHT" > "$wdir/wHeight"
    echo $(( STILL_WIDTH * STILL_HEIGHT * 2 )) > "$wdir/dwMaxVideoFrameBufferSize"
    cat <<EOF > "$wdir/dwFrameInterval"
333333
EOF
}

create_uvc() {
    # Example usage:
    #   create_uvc <target config> <function name>
    #   create_uvc config/c.1 uvc.0
    CONFIG=$1
    FUNCTION=$2

    log "    Creating UVC gadget functionality: $FUNCTION"

    pushd "$GADGET/g1" >/dev/null
    mkdir "functions/$FUNCTION"

    # write to fule function_name PRODUCT var
    echo "Fast Station Camera" > "functions/$FUNCTION/function_name"

    # create_frame "$FUNCTION" 640 360 uncompressed u
    # create_frame "$FUNCTION" 1280 720 uncompressed u
    # create_frame "$FUNCTION" 320 180 uncompressed u
    create_frame "$FUNCTION" 1920 1080 mjpeg m
    # create_frame "$FUNCTION" 640 480 mjpeg m
    # create_frame "$FUNCTION" 640 360 mjpeg m

    mkdir "functions/$FUNCTION/streaming/header/h"
    if [ -w "functions/$FUNCTION/streaming/header/h/still_width" ] && \
       [ -w "functions/$FUNCTION/streaming/header/h/still_height" ]; then
        echo "$STILL_WIDTH" > "functions/$FUNCTION/streaming/header/h/still_width"
        echo "$STILL_HEIGHT" > "functions/$FUNCTION/streaming/header/h/still_height"
    else
        log "    Still frame configfs attributes not present, using kernel defaults"
    fi

    cd "functions/$FUNCTION/streaming/header/h"
    # ln -s ../../uncompressed/u
    ln -s ../../mjpeg/m
    cd ../../class/fs
    ln -s ../../header/h
    cd ../../class/hs
    ln -s ../../header/h
    cd ../../class/ss
    ln -s ../../header/h
    cd ../../../control
    mkdir header/h
    ln -s header/h class/fs
    ln -s header/h class/ss
    cd ../../../

    if [ -w "functions/$FUNCTION/control/terminal/camera/default/bmControls" ]; then
        # Advertise Auto-Exposure Mode only.
        echo 0x02 > "functions/$FUNCTION/control/terminal/camera/default/bmControls"
    else
        log "    Camera terminal bmControls attribute not present, using kernel defaults"
    fi

    if [ -w "functions/$FUNCTION/control/processing/default/bmControls" ]; then
        # Advertise Brightness only to match the example control registration.
        echo 0x01 > "functions/$FUNCTION/control/processing/default/bmControls"
    else
        log "    Processing unit bmControls attribute not present, using kernel defaults"
    fi

	# Include an Extension Unit if the kernel supports that
	if [ -d functions/$FUNCTION/control/extensions ]; then
		mkdir functions/$FUNCTION/control/extensions/xu.0
		pushd functions/$FUNCTION/control/extensions/xu.0

		# Set the bUnitID of the Processing Unit as the XU's source
		echo 2 > baSourceID

		# Set this XU as the source for the default output terminal
		cat bUnitID > ../../terminal/output/default/bSourceID

		# Flag some arbitrary controls. This sets alternating bits of the
		# first byte of bmControls active.
		echo 0x55 > bmControls

		# Set the GUID
		echo -e -n "\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f\x10" > guidExtensionCode

		popd
	fi

    echo 3072 > "functions/$FUNCTION/streaming_maxpacket"

    ln -s "functions/$FUNCTION" configs/c.1

    popd >/dev/null
}

do_uvc_configure() {
    log "=== Configuring USB gadget"

    if [ ! -d "$CONFIGFS" ]; then
        log "Configfs not mounted, please mount it first"
        exit 1
    fi

    log "    Removing old uvc gadget if it exists"
    remove_uvc_gadget

    log "    Creating a fresh USB gadget"
    create_uvc configs/c.1 uvc.0
    echo "super-speed" > "$GADGET/g1/max_speed"
    echo "$MANUF" > "$GADGET/g1/strings/0x409/manufacturer"
    echo "$PRODUCT" > "$GADGET/g1/strings/0x409/product"

    sleep 0.1
}

uvc_bind() {
    log "    Rebinding USB Device Controller..."
    # Hacky: retry binding until it is bound. Some other process is trying to interfere here but not yet sure which
    max_retries=10
    retries=0
    while true; do
        echo $UDC > $GADGET/g1/UDC 2>/dev/null
        if [[ "$(cat "$GADGET/g1/UDC" 2>/dev/null)" == "$UDC" ]]; then
            log "    Successfully bound UDC controller $UDC"
            break
        fi
        retries=$((retries + 1))
        if [ $retries -eq $max_retries ]; then
            log "    Failed to bind UDC controller $UDC after $max_retries attempts, exiting!"
            exit 1
        fi
        sleep 0.1
    done
    sleep 2
}

uvc_unbind() {
    log "    Unbinding USB Device Controller..."
    # Hacky: retry unbinding until it is unbound. Some other process is trying to interfere here but not yet sure which
    max_retries=10
    retries=0
    while [ $retries -lt $max_retries ]; do
        echo "" > $GADGET/g1/UDC 2>/dev/null
        if [ -z "$(cat $GADGET/g1/UDC 2>/dev/null)" ]; then
            sleep 0.1
            if [ -z "$(cat $GADGET/g1/UDC 2>/dev/null)" ]; then
                log "    Successfully unbound UDC controller $UDC"
                break
            fi
        fi
        retries=$((retries + 1))
    done
    # Check if UDC is empty
    if [ ! -z "$(cat $GADGET/g1/UDC 2>/dev/null)" ]; then
        log "    UDC is not empty after $max_retries unbind attempts, exiting!"
        exit 1
    fi
}

do_uvc_stop() {
    log "=== Stopping the USB gadget"
    uvc_unbind
    remove_uvc_gadget
    uvc_bind
    log "    OK"

}

terminate() {
    if [ "$child_pid" -gt 0 ] 2>/dev/null && kill -0 "$child_pid" 2>/dev/null; then
    kill -TERM "$child_pid"
    wait "$child_pid" || true
    fi
    do_uvc_stop
    exit 143
}
trap terminate INT TERM

case "$1" in
    start)
    sleep 1 # Allow USB to setup

    retries=0
    max_retries=1000
    backoff=5
    child_pid=0

    while [ $retries -lt $max_retries ]; do
        uvc_unbind
        do_uvc_configure
        uvc_bind

        log "=== Starting UVC APP"
        /app/uvc_example &
        child_pid=$!
        wait "$child_pid"
        status=$?
        do_uvc_stop

        if [ $status -eq 0 ]; then
        log "    uvc_example exited normally."
        exit 0
        fi

        retries=$((retries + 1))
        log "    uvc_example exited with status $status. Restarting ($retries/$max_retries)..."
        sleep "$backoff"
    done

    log "    uvc_example failed $max_retries times. Not restarting anymore."
    exit 1
    ;;

    stop)
    do_uvc_stop
    ;;
    *)
    log "Usage: $0 {start|stop}"
    ;;
esac
