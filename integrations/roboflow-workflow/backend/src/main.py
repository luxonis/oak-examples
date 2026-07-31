import logging
import time

from config.config import load_config
from core.depthai_pipeline import DepthAIPipeline
from core.manager import RoboflowManager
from core.roboflow_runner import (
    RoboflowRunner,
    fetch_workflow_specification,
    parse_workflow_interface,
)
from core.visualizer_wrapper import VisualizerWrapper

logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)


def main():
    config = load_config()
    logger.info(f"Init config: {config}")

    # Discover workflow outputs and tunable parameters through the Roboflow API
    specification = fetch_workflow_specification(
        api_key=config.roboflow.api_key,
        workspace=config.roboflow.workspace,
        workflow_id=config.roboflow.workflow_id,
    )
    interface = parse_workflow_interface(specification)
    logger.info(
        f"Workflow outputs: {interface.output_names}, "
        f"parameters: {[p['name'] for p in interface.parameters]}"
    )

    # Create visualizer
    visualizer = VisualizerWrapper(port=8082)

    # Create DepthAI pipeline
    dai_pipeline = DepthAIPipeline(
        pipeline_config=config.pipeline,
        visualizer=visualizer,
        workflow_output_names=interface.output_names,
    )

    # Roboflow runner consuming DepthAI frames
    rf_runner = RoboflowRunner(
        api_key=config.roboflow.api_key,
        workspace=config.roboflow.workspace,
        workflow_id=config.roboflow.workflow_id,
        workflow_params=config.roboflow.workflow_parameters,
        workflow_specification=specification,
        video_reference=dai_pipeline.create_frame_producer,
        on_prediction=dai_pipeline.annotation.on_prediction,
    )

    # Manager for the frontend services
    manager = RoboflowManager(
        rf_runner,
        dai_pipeline,
        visualizer,
        pipeline_config=config.pipeline,
        workflow_interface=interface,
    )

    visualizer.register_service(
        "Roboflow Parameter Update Service", manager.update_parameters
    )
    visualizer.register_service(
        "Roboflow Workflow Interface Service", manager.describe_workflow
    )
    visualizer.register_service(
        "Roboflow Workflow Refresh Service", manager.refresh_workflow
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
