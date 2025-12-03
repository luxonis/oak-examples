import depthai as dai
import logging


class VisualizerWrapper:
    def __init__(self, port=8082):
        self._rc = dai.RemoteConnection(httpPort=port)
        self._topics = []
        self._logger = logging.getLogger(self.__class__.__name__)

    def add_topic(self, name: str, feed):
        self._rc.addTopic(name, feed)
        self._topics.append(name)
        self._logger.info(f"New visualizer topic added: {name}")

    def clear_topics(self):
        for t in self._topics:
            self._rc.removeTopic(t)
        self._topics.clear()
        self._logger.info("All visualizer topics cleared")

    def register_service(self, name, callback):
        self._rc.registerService(name, callback)
        self._logger.info(f"New service registered: {name}")

    def wait_key(self, delay=1):
        return self._rc.waitKey(delay)
