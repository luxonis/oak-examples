import os
import logging
import time
from pathlib import Path

from arguments import initialize_argparser
from config.config import load_config

# Must be imported before any module that imports `inference` (it sets the
# ONNX Runtime provider env default the router relies on).
from core import qnn_patch
from core.depthai_pipeline import DepthAIPipeline
from core.manager import RoboflowManager
from core.roboflow_runner import (
    RoboflowRunner,
    fetch_workflow_specification,
    parse_workflow_interface,
)
from core.visualizer_wrapper import VisualizerWrapper
from depthai_nodes.runtime import serve_frontend

logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)


def main(args):
    # Route the ONNX sessions `inference` creates to the DSP (QNN EP) when
    # available; a no-op on non-RVC4 hosts or with EP=cpu.
    qnn_patch.install()

    config = load_config()
    if args.device:
        config.pipeline.device = args.device

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
    visualizer = VisualizerWrapper()

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
    _, args = initialize_argparser()
    with serve_frontend(
        args.frontend_dir or Path(__file__).resolve().parents[2] / "frontend" / "dist",
        enabled=not args.no_frontend
        and not os.environ.get("OAKAPP_STATIC_FRONTEND_PORT"),
    ):
        main(args)
