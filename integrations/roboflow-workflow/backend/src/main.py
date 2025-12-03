import time
import logging

from config.config import load_config
from core.depthai_pipeline import DepthAIPipeline
from core.roboflow_runner import RoboflowRunner, probe_workflow_schema
from core.manager import RoboflowManager
from core.visualizer_wrapper import VisualizerWrapper


logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)


def main():
    config = load_config()
    logger.info(f"Init config: {config}")

    # Roboflow runner
    rf_runner = RoboflowRunner(
        api_key=config.roboflow.api_key,
        workspace=config.roboflow.workspace,
        workflow_id=config.roboflow.workflow_id,
        workflow_params=config.roboflow.workflow_parameters,
        on_prediction=None,
    )

    workflow_schema = probe_workflow_schema(rf_runner)

    # Create visualizer
    visualizer = VisualizerWrapper(port=8082)

    # Create DepthAI pipeline
    dai_pipeline = DepthAIPipeline(
        pipeline_config=config.pipeline,
        visualizer=visualizer,
        workflow_schema=workflow_schema,
    )

    # Set correct callback output processing
    rf_runner._on_prediction = dai_pipeline.annotation.on_prediction

    # Manager for parameter update service
    manager = RoboflowManager(
        rf_runner, dai_pipeline, visualizer, pipeline_config=config.pipeline
    )

    visualizer.register_service(
        "Roboflow Parameter Update Service", manager.update_parameters
    )

    # Start subsystems
    dai_pipeline.start()
    rf_runner.start()

    logger.info("System running... press 'q' inside visualizer to quit")

    try:
        while True:
            key = visualizer.wait_key(1)
            if key == ord("q"):
                logger.info("Visualizer requested shutdown")
                break

            time.sleep(0.01)

    except KeyboardInterrupt:
        logger.info("Keyboard shutdown")

    # Clean shutdown
    rf_runner.stop()
    dai_pipeline.stop()


if __name__ == "__main__":
    main()
