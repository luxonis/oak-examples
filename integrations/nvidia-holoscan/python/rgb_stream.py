#!/usr/bin/env python3

import argparse

import cv2
import depthai as dai
import numpy as np

try:
    from hololink import emulation
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("hololink.emulation._"):
        raise ModuleNotFoundError(
            "hololink emulation native modules are missing. Build holoscan-sensor-bridge "
            "with:\n"
            "  cmake -S src/hololink/emulation -B build\n"
            "  cmake --build build -j\n"
            "Then run this script with build/env/bin/python."
        ) from exc
    raise

# Hololink register constants used by the emulator transport metadata setup.
# These values match hololink/core headers.
DP_PACKET_SIZE = 0x04
DP_PACKET_UDP_PORT = 0x08
DP_QP = 0x00
DP_RKEY = 0x04
DP_ADDRESS_0 = 0x08
DP_BUFFER_LENGTH = 0x18
DP_BUFFER_MASK = 0x1C
DATA_SOURCE_UDP_PORT = 12288


def main() -> None:
    parser = argparse.ArgumentParser(description="DepthAI -> Hololink emulator bridge")
    parser.add_argument("--ip", default="10.12.101.183", help="Local source IP configured on this host")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--data-plane-id", type=int, default=0)
    parser.add_argument("--sensor-id", type=int, default=0)
    args = parser.parse_args()

    data_plane_id = int(args.data_plane_id)
    sensor_id = int(args.sensor_id)

    emulator_ip = emulation.IPAddress(args.ip)
    emulator = emulation.HSBEmulator()

    k_hif_address_base = 0x02000300
    k_hif_address_step = 0x00010000
    k_vp_address_base = 0x00001000
    k_vp_address_step = 0x00000040
    k_default_packet_pages = 1
    k_default_qp = 1
    k_default_rkey = 1

    hif_address = k_hif_address_base + k_hif_address_step * data_plane_id
    sif0_index = int(sensor_id * emulation.HSB_EMULATOR_CONFIG.sifs_per_sensor)
    vp_address = k_vp_address_base + k_vp_address_step * sif0_index

    # Program default transport metadata expected by LinuxDataPlane.
    emulator.write(hif_address + DP_PACKET_SIZE, k_default_packet_pages)
    emulator.write(hif_address + DP_PACKET_UDP_PORT, DATA_SOURCE_UDP_PORT)
    emulator.write(vp_address + DP_QP, k_default_qp)
    emulator.write(vp_address + DP_RKEY, k_default_rkey)
    emulator.write(vp_address + DP_BUFFER_MASK, 0x1)
    emulator.write(vp_address + DP_ADDRESS_0, 0)

    linux_data_plane = emulation.LinuxDataPlane(
        hsb_emulator=emulator,
        source_ip=emulator_ip,
        data_plane_id=data_plane_id,
        sensor_id=sensor_id,
    )

    device = dai.Device()
    with dai.Pipeline(device) as pipeline:
        camera_node = pipeline.create(dai.node.Camera)
        camera_node.build()
        camera_out = camera_node.requestOutput((args.width, args.height))
        q_rgb = camera_out.createOutputQueue()

        pipeline.start()
        emulator.start()

        try:
            while pipeline.isRunning():
                in_rgb = q_rgb.get()
                if in_rgb is None:
                    continue

                bgr_frame = in_rgb.getCvFrame()
                if bgr_frame is None or bgr_frame.size == 0:
                    continue

                rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
                payload = np.ascontiguousarray(rgb_frame).reshape(-1)

                emulator.write(vp_address + DP_BUFFER_LENGTH, int(payload.nbytes))
                sent_bytes = linux_data_plane.send(payload)

                if sent_bytes <= 0:
                    print("Frame not sent yet (waiting for destination configuration).")
                else:
                    print(f"Sent {sent_bytes} bytes.")

                cv2.imshow("RGB Frame", bgr_frame)
                if cv2.waitKey(1) == ord("q"):
                    break
        finally:
            emulator.stop()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
