# Parcel measurement improvements

Operators measure parcels on a calibrated flat surface and see tracked RGB bounding boxes labeled `L`, `W`, and `H` in millimeters. A Measurements tab retains the last 20 measured objects across application restarts. Each saved measurement opens an interactive segmented point cloud with its fitted cuboid and relevant capture metadata.

An operator can replace a saved measurement while its tracking ID is currently visible. An absent object is marked "Object not in frame". Snapshot storage must not block live measurement. Save one object from a sequence, finish that write before scheduling another, and advance through unsaved visible objects fairly. Store one current snapshot per tracking ID.

The RGB view offers optional colorized depth and selected support-plane overlays. The connected OAK4 provides the live test scene. Physical reference dimension comparison is outside this task. Historical records persist after restart, while live tracking starts new IDs and does not infer physical identity across restarts.

Depth aligned into RGB pixels must express Z along the RGB optical axis. Use the public ImageAlignDepthCorrection node after ImageAlign, before generating the point cloud used for calibration and parcel measurement.
