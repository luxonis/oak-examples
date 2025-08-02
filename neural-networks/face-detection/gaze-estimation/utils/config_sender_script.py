try:
    while True:
        frame = node.inputs["frame_input"].get()
        configs_message = node.inputs["config_input"].get()

        conf_seq = configs_message.getSequenceNum()
        frame_seq = frame.getSequenceNum()

        for i, cfg in configs_message:
            node.outputs["output_config"].send(cfg)
            node.outputs["output_frame"].send(frame)

except Exception as e:
    node.warn(str(e))
