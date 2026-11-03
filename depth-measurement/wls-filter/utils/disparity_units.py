import depthai as dai


def get_disparity_scale(config: dai.StereoDepthConfig, platform: dai.Platform) -> int:
    """Encoded disparity units per pixel, including RVC2 post-processing."""
    subpixel = 2 ** config.getSubpixelFractionalBits() if config.getSubpixel() else 1
    if platform != dai.Platform.RVC2:
        return subpixel
    if config.costMatching.enableCompanding:
        raise ValueError("WLS metric conversion does not support companded disparity")
    if hasattr(config, "getDisparityScale"):
        return int(config.getDisparityScale())

    # DepthAI 3.11 compatibility: RVC2 filters normalize disparity with an
    # integer multiplier. Older getMaxDisparity() reports the 8192 ceiling,
    # so calculate the actual encoding directly (e.g. 760 * 10 = 7600).
    maximum = (
        63
        if config.costMatching.disparityWidth
        == dai.StereoDepthConfig.CostMatching.DisparityWidth.DISPARITY_64
        else 95
    )
    if config.getExtendedDisparity():
        maximum *= 2
    nominal_maximum = maximum * subpixel
    post = config.postProcessing
    filter_type = dai.StereoDepthConfig.PostProcessing.Filter
    enabled = {
        filter_type.SPECKLE: post.speckleFilter.enable,
        filter_type.SPATIAL: post.spatialFilter.enable,
        filter_type.TEMPORAL: post.temporalFilter.enable,
        filter_type.DECIMATION: post.decimationFilter.decimationFactor > 1,
        filter_type.MEDIAN: (
            post.median != dai.StereoDepthConfig.MedianFilter.MEDIAN_OFF
            and nominal_maximum < 1024
        ),
    }
    last_filter = next(
        (f for f in reversed(post.filteringOrder) if enabled.get(f, False)),
        filter_type.NONE,
    )
    normalization = (
        8192 // nominal_maximum
        if last_filter not in (filter_type.NONE, filter_type.MEDIAN)
        else 1
    )
    return subpixel * normalization
