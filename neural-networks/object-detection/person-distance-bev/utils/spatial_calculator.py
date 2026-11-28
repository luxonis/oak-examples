import depthai as dai

_DEPTH_LOWER_THRESHOLD_MM = 200
_DEPTH_UPPER_THRESHOLD_MM = 30000
_KEYPOINT_RADIUS_PX = 5
# Inset the sample so it stays on the person instead of the box edge.
_BOX_SCALE = 0.8


def create_spatial_calculator(
    pipeline: dai.Pipeline,
) -> dai.node.SpatialLocationCalculator:
    """Give each person detection a depth from inside its box."""
    calculator = pipeline.create(dai.node.SpatialLocationCalculator)
    calculator.initialConfig.setDepthThresholds(
        _DEPTH_LOWER_THRESHOLD_MM, _DEPTH_UPPER_THRESHOLD_MM
    )
    calculator.initialConfig.setCalculationAlgorithm(
        dai.SpatialLocationCalculatorAlgorithm.AVERAGE
    )
    calculator.initialConfig.setStepSize(1)
    calculator.initialConfig.setBoundingBoxScaleFactor(_BOX_SCALE)
    calculator.initialConfig.setCalculateSpatialKeypoints(True)
    calculator.initialConfig.setKeypointRadius(_KEYPOINT_RADIUS_PX)
    calculator.initialConfig.setUseSegmentation(False)
    # Set to blocking to avoid dropping and mismatching frames
    calculator.inputDetections.setBlocking(True)
    calculator.inputDetections.setMaxSize(1)
    calculator.inputDepth.setBlocking(True)
    calculator.inputDepth.setMaxSize(1)
    calculator.setRunOnHost(False)
    return calculator
