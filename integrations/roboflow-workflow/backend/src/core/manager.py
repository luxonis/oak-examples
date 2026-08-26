import threading
import logging

from core.depthai_pipeline import DepthAIPipeline
from core.roboflow_runner import RoboflowRunner, probe_workflow_schema
from core.visualizer_wrapper import VisualizerWrapper
from config.config import PipelineConfig


class RoboflowManager:
    def __init__(
        self,
        runner: RoboflowRunner,
        depthai_pipeline: DepthAIPipeline,
        visualizer: VisualizerWrapper,
        pipeline_config: PipelineConfig,
    ):
        self._runner = runner
        self._visualizer = visualizer
        self._dai_pipeline = depthai_pipeline
        self._pipeline_config = pipeline_config
        self._lock = threading.Lock()

        self._logger = logging.getLogger(self.__class__.__name__)

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
                return {"status": "ok", "schema_rebuilt": False}

            self._logger.info(
                "Whole workflow changed, Roboflow and DAI pipeline restart needed"
            )
            # Credentials/workflow changed → rebuild everything
            self._runner.stop()
            self._dai_pipeline.stop()
            self._visualizer.clear_topics()

            self._runner.restart(
                api_key=new_api,
                workspace=new_ws,
                workflow_id=new_wf,
                params=new_params,
                auto_start=False,
            )

            workflow_schema = probe_workflow_schema(self._runner)
            self._dai_pipeline = DepthAIPipeline(
                pipeline_config=self._pipeline_config,
                visualizer=self._visualizer,
                workflow_schema=workflow_schema,
            )
            self._runner.set_on_prediction(self._dai_pipeline.annotation.on_prediction)

            self._dai_pipeline.start()
            self._runner.start()

        return {"status": "ok", "schema_rebuilt": True}
