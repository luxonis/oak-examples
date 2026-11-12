"""Fake ``dai.RemoteConnection`` that records registered services by name."""


class RemoteServices:
    def __init__(self, **kwargs):
        self.services = {}

    def registerService(self, name, handler):
        self.services[name] = handler
