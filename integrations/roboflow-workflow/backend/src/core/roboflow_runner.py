import copy
import json
import logging
import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Union

import requests
from inference import InferencePipeline
from inference.core.env import API_BASE_URL
from inference.core.interfaces.camera.entities import (
    StatusUpdate,
    UpdateSeverity,
    VideoFrameProducer,
)
from inference.core.interfaces.stream.inference_pipeline import (
    INFERENCE_THREAD_FINISHED_EVENT,
    INFERENCE_THREAD_STARTED_EVENT,
)


@dataclass
class WorkflowInterface:
    """Workflow outputs and tunable parameters discovered from its definition"""

    output_names: List[str] = field(default_factory=list)
    # each entry: {"name": str, "default_value": Any, "kind": Optional[List[str]]}
    parameters: List[Dict] = field(default_factory=list)


def parse_workflow_interface(specification: Dict) -> WorkflowInterface:
    """Extracts output names and `WorkflowParameter` inputs from a workflow definition"""
    output_names = [output["name"] for output in specification.get("outputs", [])]
    parameters = []
    for wf_input in specification.get("inputs", []):
        if wf_input.get("type") != "WorkflowParameter":
            continue  # image / video-metadata inputs are fed by the pipeline itself
        parameters.append(
            {
                "name": wf_input["name"],
                "default_value": wf_input.get("default_value"),
                "kind": wf_input.get("kind"),
            }
        )
    return WorkflowInterface(output_names=output_names, parameters=parameters)


def fetch_workflow_specification(
    api_key: str, workspace: str, workflow_id: str
) -> Dict:
    """
    Fetches the workflow definition from the Roboflow API.

    Unlike `inference.core.roboflow_api.get_workflow_specification`, this
    prefers the latest saved definition (`lastVersionConfig`) over the
    published one (`config`), so edits made in the Roboflow builder take
    effect without publishing a new workflow version.
    """
    response = requests.get(
        f"{API_BASE_URL}/{workspace}/workflows/{workflow_id}",
        params={"api_key": api_key},
        timeout=10,
    )
    response.raise_for_status()
    workflow = response.json()["workflow"]
    config = workflow.get("lastVersionConfig") or workflow["config"]
    if isinstance(config, str):
        config = json.loads(config)
    return config["specification"]


class RoboflowRunner:
    """
    Thin wrapper around Roboflow's `InferencePipeline` consuming frames from a
    `VideoFrameProducer` factory. Thread-safe, supports start(), stop(), restart().
    """

    def __init__(
        self,
        api_key: str,
        workspace: str,
        workflow_id: str,
        workflow_params: Dict,
        workflow_specification: Optional[Dict] = None,
        video_reference: Optional[Callable[[], VideoFrameProducer]] = None,
        on_prediction: Union[Callable, None] = None,
    ):
        self._api_key = api_key
        self._workspace = workspace
        self._workflow_id = workflow_id
        self._params = copy.deepcopy(workflow_params)
        self._specification = workflow_specification
        self._video_reference = video_reference
        self._on_prediction = on_prediction

        self._lock = threading.Lock()
        self._pipeline: Optional[InferencePipeline] = None

        # Pipeline health, fed by InferencePipeline status updates. One error
        # in the inference thread kills it permanently (predictions silently
        # stop while the camera stream keeps running), so it must be surfaced.
        self._status_lock = threading.Lock()
        self._last_error: Optional[Dict] = None
        self._inference_thread_alive = False

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

    @property
    def workflow_specification(self):
        return self._specification

    def get_status(self) -> Dict:
        """Health of the inference pipeline: running flag and last error"""
        with self._status_lock:
            return {
                "running": self._inference_thread_alive,
                "error": copy.deepcopy(self._last_error),
            }

    def _on_status_update(self, update: StatusUpdate):
        """Called by InferencePipeline threads - must never raise"""
        try:
            error = None
            if update.severity.value >= UpdateSeverity.ERROR.value:
                payload = update.payload or {}
                error = {
                    "event_type": update.event_type,
                    "error_type": payload.get("error_type"),
                    "message": payload.get("error_message") or str(payload),
                    "context": payload.get("error_context"),
                }
            with self._status_lock:
                if update.event_type == INFERENCE_THREAD_STARTED_EVENT:
                    self._inference_thread_alive = True
                elif update.event_type == INFERENCE_THREAD_FINISHED_EVENT:
                    self._inference_thread_alive = False
                if error is not None:
                    self._last_error = error
            if error is not None:
                self._logger.error(
                    "Roboflow pipeline error (%s): %s",
                    update.event_type,
                    error["message"],
                )
        except Exception:
            self._logger.exception("Failed to process pipeline status update")

    def set_video_reference(self, video_reference: Callable[[], VideoFrameProducer]):
        with self._lock:
            self._video_reference = video_reference

    def set_on_prediction(self, callback: Union[Callable, None]):
        with self._lock:
            self._on_prediction = callback

    def start(self):
        """Creates a new InferencePipeline and starts it on background threads"""
        self._logger.info("RoboflowPipeline start requested...")
        with self._status_lock:
            self._last_error = None
            self._inference_thread_alive = False
        with self._lock:
            if self._video_reference is None:
                raise RuntimeError("video_reference must be set before start()")
            if self._specification is not None:
                # Run the exact definition we discovered (latest saved draft),
                # keeping the DAI topics and the parameter form in sync with it
                self._pipeline = InferencePipeline.init_with_workflow(
                    api_key=self.api_key,
                    workflow_specification=self._specification,
                    video_reference=self._video_reference,
                    on_prediction=self._on_prediction,
                    workflows_parameters=copy.deepcopy(self.workflow_params),
                    status_update_handlers=[self._on_status_update],
                )
            else:
                self._pipeline = InferencePipeline.init_with_workflow(
                    api_key=self.api_key,
                    workspace_name=self.workspace,
                    workflow_id=self.workflow_id,
                    video_reference=self._video_reference,
                    on_prediction=self._on_prediction,
                    workflows_parameters=copy.deepcopy(self.workflow_params),
                    status_update_handlers=[self._on_status_update],
                    # the definition cache has a 15 min TTL - bypass it so that
                    # restarts always pick up the latest workflow edits
                    use_workflow_definition_cache=False,
                )
            self._pipeline.start(use_main_thread=False)
        self._logger.info("RoboflowPipeline started")

    def stop(self):
        """Stops the InferencePipeline and waits for its threads to finish"""
        self._logger.info("RoboflowPipeline stop requested...")
        with self._lock:
            if self._pipeline is None:
                return
            try:
                self._pipeline.terminate()
                self._pipeline.join()
            except Exception:
                self._logger.exception("Error while stopping Roboflow pipeline")
            self._pipeline = None
        self._logger.info("RoboflowPipeline stopped")

    def restart(
        self,
        api_key: Optional[str] = None,
        workspace: Optional[str] = None,
        workflow_id: Optional[str] = None,
        params: Optional[Dict] = None,
        specification: Optional[Dict] = None,
        auto_start: Optional[bool] = True,
    ):
        """Stops any old InferencePipeline and optionally starts a new one"""
        self._logger.info("RoboflowPipeline restart requested...")
        with self._lock:
            # Update config if provided
            if api_key is not None:
                self._api_key = api_key
            if workspace is not None:
                self._workspace = workspace
            if workflow_id is not None:
                self._workflow_id = workflow_id
            if params is not None:
                self._params = copy.deepcopy(params)
            if specification is not None:
                self._specification = specification

        self.stop()

        # Start new one
        if auto_start:
            self.start()

    def _handle_prediction(self, result, frame):
        """Forwards predictions to the currently registered callback"""
        callback = self._on_prediction
        if callback is not None:
            callback(result, frame)
