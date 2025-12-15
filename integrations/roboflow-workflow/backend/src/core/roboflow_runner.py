import threading
import time
import copy
import cv2
import numpy as np
import logging
from inference import InferencePipeline
from typing import Dict, Callable, Union, Optional

from core.generator_capture import GeneratorCapture


class RoboflowRunner:
    """
    Runs a Roboflow InferencePipeline on frames coming from cv2.VideoCapture('generator').
    Thread-safe, supports start(), stop(), restart().
    """

    def __init__(
        self,
        api_key: str,
        workspace: str,
        workflow_id: str,
        workflow_params: Dict,
        on_prediction: Union[Callable, None],
    ):
        self._api_key = api_key
        self._workspace = workspace
        self._workflow_id = workflow_id
        self._params = copy.deepcopy(workflow_params)
        self._on_prediction = on_prediction

        self._pipeline_update_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None
        self._pipeline = None

        self._logger = logging.getLogger(self.__class__.__name__)

    @property
    def api_key(self):
        return self._api_key

    @property
    def workspace(self):
        return self._workspace

    @property
    def workflow_id(self):
        return self._workflow_id

    @property
    def workflow_params(self):
        return self._params

    def set_on_prediction(self, callback: Union[Callable, None]):
        with self._pipeline_update_lock:
            self._on_prediction = callback

    def run_once_and_get_prediction(self):
        """Runs synchronous dummy inference until the first prediction is returned. Returns whole prediction dict"""
        self._logger.info("Running Roboflow pipeline once to get prediction dict")
        result_event = threading.Event()
        result_holder = {"value": None}

        def probe_callback(pred, frame):
            if pred is not None and not result_event.is_set():
                result_holder["value"] = pred
                result_event.set()

        def dummy_generator():
            while not result_event.is_set():
                yield np.zeros((640, 640, 3), dtype=np.uint8)

        # Patch VideoCapture temporarily
        orig_vc = cv2.VideoCapture
        cv2.VideoCapture = lambda _: GeneratorCapture(dummy_generator())

        pipeline = self._create_pipeline(prediction_callback=probe_callback)

        thread = threading.Thread(target=pipeline.start, daemon=True)
        thread.start()

        result_event.wait()

        try:
            pipeline.terminate()
        except Exception:
            pass

        cv2.VideoCapture = orig_vc

        return result_holder["value"]

    def start(self):
        """Creates new InferencePipeline and starts it in a new thread"""
        self._logger.info("RoboflowPipeline start requested...")
        with self._pipeline_update_lock:
            self._pipeline = self._create_pipeline()
            self._stop_event.clear()

            self._thread = threading.Thread(
                target=self._run, name="RoboflowPipelineThread", daemon=False
            )
            self._thread.start()
        self._logger.info("RoboflowPipeline started")

    def stop(self):
        """Stops InferencePipeline and takes care of cleaning up the threads"""
        self._logger.info("RoboflowPipeline stop requested...")
        with self._pipeline_update_lock:
            self._stop_event.set()
            if self._pipeline:
                try:
                    self._pipeline.terminate()
                except Exception:
                    pass

        if self._thread and self._thread.is_alive():
            self._thread.join()
        self._logger.info("RoboflowPipeline stopped")

    def restart(
        self,
        api_key: Optional[str] = None,
        workspace: Optional[str] = None,
        workflow_id: Optional[str] = None,
        params: Optional[Dict] = None,
        auto_start: Optional[bool] = True,
    ):
        """Stops any old InferencePipeline and optionally starts a new one"""
        self._logger.info("RoboflowPipeline restart requested...")
        with self._pipeline_update_lock:
            # Update config if provided
            if api_key is not None:
                self._api_key = api_key
            if workspace is not None:
                self._workspace = workspace
            if workflow_id is not None:
                self._workflow_id = workflow_id
            if params is not None:
                self._params = copy.deepcopy(params)

        self.stop()

        # Start new one
        if auto_start:
            self.start()

    def _create_pipeline(
        self, prediction_callback: Optional[Union[Callable, None]] = None
    ):
        """Creates new InferencePipeline instance"""
        return InferencePipeline.init_with_workflow(
            api_key=self._api_key,
            workspace_name=self._workspace,
            workflow_id=self._workflow_id,
            workflows_parameters=copy.deepcopy(self._params),
            video_reference="generator",
            on_prediction=prediction_callback or self._on_prediction,
        )

    def _run(self):
        try:
            self._pipeline.start()
            while not self._stop_event.is_set():
                time.sleep(0.1)
            self._pipeline.terminate()
        except Exception as e:
            print("[RoboflowRunner] Pipeline error:", e)


def probe_workflow_schema(runner: RoboflowRunner):
    """
    Runs the provided RoboflowRunner once to obtain the workflow schema.
    """
    sample = runner.run_once_and_get_prediction()
    return sample
