import cv2


class GeneratorCapture:
    def __init__(self, generator):
        self.generator = generator
        self.last_frame = None
        self.frame_width = 0
        self.frame_height = 0
        self.opened = True

    def isOpened(self):
        return self.opened

    def grab(self):
        """Fetch next frame from generator."""
        try:
            frame = next(self.generator)
            self.last_frame = frame
            self.frame_height, self.frame_width = frame.shape[:2]
            return True
        except StopIteration:
            self.opened = False
            return False

    def retrieve(self):
        """Return the most recently grabbed frame."""
        if self.last_frame is None:
            return False, None
        return True, self.last_frame

    def get(self, prop):
        """Handle requested capture properties."""
        if prop == cv2.CAP_PROP_FRAME_WIDTH:
            return self.frame_width
        elif prop == cv2.CAP_PROP_FRAME_HEIGHT:
            return self.frame_height
        return 0.0

    def release(self):
        self.opened = False
