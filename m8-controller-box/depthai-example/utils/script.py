try:
    while True:
        frame = node.inputs["frame_input"].get()
        # node.warn(f"{frame.getType()}")
        # node.warn(f"[ConfigSender {frame.getSequenceNum()}] Got frame {frame.getTimestamp()}")
        num_configs_message = node.inputs["num_configs_input"].get()
        conf_seq = num_configs_message.getSequenceNum()
        frame_seq = frame.getSequenceNum()
        num_configs = len(bytearray(num_configs_message.getData()))

        while conf_seq > frame_seq:
            # node.warn(f"[ConfigSender {conf_seq}] Configs {conf_seq} mismatch with frame {frame_seq}")
            frame = node.inputs["frame_input"].get()

        for i in range(num_configs):
            cfg = node.inputs["config_input"].get()
            # node.warn(f"[ConfigSender {conf_seq}] Got config {i}")
            node.outputs["output_config"].send(cfg)
            node.outputs["output_frame"].send(frame)
            # node.warn(f"[ConfigSender {conf_seq}] sent {i}")

except Exception as e:
    node.warn(str(e))
