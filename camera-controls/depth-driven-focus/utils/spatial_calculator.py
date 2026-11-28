import depthai as dai

_DEPTH_LOWER_THRESHOLD_MM = 200
_DEPTH_UPPER_THRESHOLD_MM = 30000
_KEYPOINT_RADIUS_PX = 5
_BOX_SCALE = 1.0


def create_spatial_calculator(
    pipeline: dai.Pipeline,
) -> dai.node.SpatialLocationCalculator:
    """Give each face detection a depth from inside its box."""
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
    calculator.inputDetections.setMaxSize(2)
    calculator.inputDepth.setBlocking(True)
    calculator.inputDepth.setMaxSize(1)
    calculator.setRunOnHost(False)
    return calculator
