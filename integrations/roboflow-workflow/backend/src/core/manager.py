import logging
import threading

from config.config import PipelineConfig
from core.depthai_pipeline import DepthAIPipeline
from core.roboflow_runner import (
    RoboflowRunner,
    WorkflowInterface,
    fetch_workflow_specification,
    parse_workflow_interface,
)
from core.visualizer_wrapper import VisualizerWrapper


class RoboflowManager:
    def __init__(
        self,
        runner: RoboflowRunner,
        depthai_pipeline: DepthAIPipeline,
        visualizer: VisualizerWrapper,
        pipeline_config: PipelineConfig,
        workflow_interface: WorkflowInterface,
    ):
        self._runner = runner
        self._visualizer = visualizer
        self._dai_pipeline = depthai_pipeline
        self._pipeline_config = pipeline_config
        self._interface = workflow_interface
        self._lock = threading.Lock()

        self._logger = logging.getLogger(self.__class__.__name__)

    def describe_workflow(self, payload: dict):
        """Returns the current workflow interface for the frontend to build its form"""
        # The frontend polls this service to monitor pipeline health - keep
        # those requests out of the info-level logs
        log = self._logger.debug if (payload or {}).get("quiet") else self._logger.info
        log(f"New `Describe Workflow` request: {payload}")
        with self._lock:
            return {"status": "ok", **self._describe_locked()}

    def refresh_workflow(self, payload: dict):
        """
        Re-fetches the definition of the active workflow from the Roboflow API
        and restarts the inference pipeline so that edits made in the Roboflow
        builder (new parameters, changed outputs, ...) take effect.
        """
        self._logger.info(f"New `Refresh Workflow` request: {payload}")
        with self._lock:
            specification = fetch_workflow_specification(
                api_key=self._runner.api_key,
                workspace=self._runner.workspace,
                workflow_id=self._runner.workflow_id,
            )
            interface = parse_workflow_interface(specification)

            # Drop overrides for parameters that no longer exist
            valid_names = {param["name"] for param in interface.parameters}
            params = {
                name: value
                for name, value in (self._runner.workflow_params or {}).items()
                if name in valid_names
            }

            rebuilt = self._apply_workflow(
                interface=interface,
                specification=specification,
                api_key=self._runner.api_key,
                workspace=self._runner.workspace,
                workflow_id=self._runner.workflow_id,
                params=params,
            )
            return {
                "status": "ok",
                "schema_rebuilt": rebuilt,
                **self._describe_locked(),
            }

    def update_parameters(self, payload: dict):
        self._logger.info(f"New `Update Parameter` request: {payload}")
        with self._lock:
            current_api = self._runner.api_key
            current_ws = self._runner.workspace
            current_wf = self._runner.workflow_id
            current_params = self._runner.workflow_params

            new_api = payload.get("api_key") or current_api
            new_ws = payload.get("workspace_name") or current_ws
            new_wf = payload.get("workflow_id") or current_wf
            new_params = payload.get("workflow_parameters") or current_params

            identity_changed = (
                new_api != current_api or new_ws != current_ws or new_wf != current_wf
            )

            # Only workflow params changed → restart runner is enough
            if not identity_changed:
                self._logger.info(
                    "Workflow parameters changed, Roboflow pipeline restart needed"
                )
                self._runner.restart(
                    api_key=new_api,
                    workspace=new_ws,
                    workflow_id=new_wf,
                    params=new_params,
                )
                return {
                    "status": "ok",
                    "schema_rebuilt": False,
                    **self._describe_locked(),
                }

            self._logger.info(
                "Whole workflow changed, Roboflow and DAI pipeline restart needed"
            )
            # Credentials/workflow changed → fetch the new workflow's definition
            specification = fetch_workflow_specification(
                api_key=new_api, workspace=new_ws, workflow_id=new_wf
            )
            interface = parse_workflow_interface(specification)

            # Parameters of the previous workflow are meaningless for the new one
            if new_wf != current_wf and payload.get("workflow_parameters") is None:
                new_params = {}

            rebuilt = self._apply_workflow(
                interface=interface,
                specification=specification,
                api_key=new_api,
                workspace=new_ws,
                workflow_id=new_wf,
                params=new_params,
            )
            return {
                "status": "ok",
                "schema_rebuilt": rebuilt,
                **self._describe_locked(),
            }

    def _apply_workflow(
        self,
        interface: WorkflowInterface,
        specification: dict,
        api_key: str,
        workspace: str,
        workflow_id: str,
        params: dict,
    ) -> bool:
        """
        Restarts the Roboflow runner with the given workflow. Rebuilds the
        DepthAI pipeline and visualizer topics only when the workflow outputs
        changed. Returns True if the topics were rebuilt. Call with self._lock
        held.
        """
        outputs_changed = interface.output_names != self._interface.output_names

        if not outputs_changed:
            self._runner.restart(
                api_key=api_key,
                workspace=workspace,
                workflow_id=workflow_id,
                params=params,
                specification=specification,
            )
            self._interface = interface
            return False

        self._runner.restart(
            api_key=api_key,
            workspace=workspace,
            workflow_id=workflow_id,
            params=params,
            specification=specification,
            auto_start=False,
        )
        self._dai_pipeline.stop()
        self._visualizer.clear_topics()

        self._dai_pipeline = DepthAIPipeline(
            pipeline_config=self._pipeline_config,
            visualizer=self._visualizer,
            workflow_output_names=interface.output_names,
        )
        self._runner.set_video_reference(self._dai_pipeline.create_frame_producer)
        self._runner.set_on_prediction(self._dai_pipeline.annotation.on_prediction)

        self._dai_pipeline.start()
        self._runner.start()

        self._interface = interface
        return True

    def _describe_locked(self) -> dict:
        """Interface description with current values; call with self._lock held"""
        overrides = self._runner.workflow_params or {}
        parameters = []
        for param in self._interface.parameters:
            name = param["name"]
            parameters.append(
                {
                    **param,
                    "current_value": overrides.get(name, param["default_value"]),
                }
            )
        return {
            "workspace_name": self._runner.workspace,
            "workflow_id": self._runner.workflow_id,
            "outputs": self._interface.output_names,
            "parameters": parameters,
            # One bad frame kills the inference thread for good (the camera
            # stream keeps running) - report it so the UI can tell the user
            "pipeline": self._runner.get_status(),
        }
