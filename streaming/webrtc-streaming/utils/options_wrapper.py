class OptionsWrapper:
    def __init__(self, raw_options):
        self.raw_options = raw_options

    @property
    def camera_type(self):
        return self.raw_options.get("camera_type", "rgb")

    @property
    def width(self):
        return int(self.raw_options.get("cam_width", 300))

    @property
    def height(self):
        return int(self.raw_options.get("cam_height", 300))

    @property
    def nn(self):
        return self.raw_options.get("nn_model", "")
