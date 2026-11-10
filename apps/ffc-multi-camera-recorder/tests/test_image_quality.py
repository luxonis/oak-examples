"""Hardware-free tests. From the example directory: python3 -m unittest discover -v -s tests"""

from datetime import timedelta
import unittest
from unittest.mock import Mock

import depthai as dai
import numpy as np

from utils.image_quality import BrightnessReference, RawImageProcessor, unpack_raw10


def raw_frame(pixels, *, exposure_us=10000, timestamp=1, padding=0):
    pixels = np.asarray(pixels, dtype=np.uint16)
    height, width = pixels.shape
    groups = pixels.reshape(height, width // 4, 4)
    packed = np.zeros((height, width // 4, 5), dtype=np.uint8)
    packed[:, :, :4] = groups >> 2
    for index in range(4):
        packed[:, :, 4] |= ((groups[:, :, index] & 3) << (2 * index)).astype(np.uint8)
    rows = np.pad(
        packed.reshape(height, -1), ((0, 0), (0, padding)), constant_values=255
    )
    frame = Mock(spec=dai.ImgFrame)
    frame.getType.return_value = dai.ImgFrame.Type.RAW10
    frame.getWidth.return_value = width
    frame.getHeight.return_value = height
    frame.getStride.return_value = rows.shape[1]
    frame.getData.return_value = rows.ravel()
    frame.getExposureTime.return_value = timedelta(microseconds=exposure_us)
    frame.getTimestampDevice.return_value = timedelta(seconds=timestamp)
    frame.getTimestamp.return_value = timedelta(seconds=timestamp + 100)
    frame.getSequenceNum.return_value = 42
    return frame


class RawConversionTests(unittest.TestCase):
    def test_known_mipi_bytes_and_padding(self):
        raw = raw_frame(np.zeros((2, 8)), padding=3)
        raw.getData.return_value = np.array(
            [
                0,
                0,
                0,
                0,
                228,
                255,
                255,
                255,
                255,
                228,
                99,
                99,
                99,
                16,
                16,
                16,
                16,
                228,
                64,
                64,
                64,
                64,
                228,
                99,
                99,
                99,
            ],
            dtype=np.uint8,
        )
        np.testing.assert_array_equal(
            unpack_raw10(raw),
            [
                [0, 1, 2, 3, 1020, 1021, 1022, 1023],
                [64, 65, 66, 67, 256, 257, 258, 259],
            ],
        )

    def test_bad_frames_fail_explicitly(self):
        for method, value in [
            ("getStride", 2),
            ("getWidth", 6),
            ("getHeight", 3),
            ("getType", dai.ImgFrame.Type.NV12),
            ("getData", np.zeros(2, dtype=np.uint8)),
        ]:
            with self.subTest(method=method):
                raw = raw_frame(np.full((2, 8), 100))
                getattr(raw, method).return_value = value
                with self.assertRaises(ValueError):
                    unpack_raw10(raw)

    def test_black_gamma_range_chroma_and_timestamps(self):
        raw = raw_frame(np.tile([0, 64, 65, 66, 67, 256, 512, 1023], (2, 1)))
        processor = RawImageProcessor(20, auto_exposure=False)
        frame, control = processor.convert(raw)
        data = frame.getData().reshape(3, 8)
        self.assertIsNone(control)
        self.assertEqual(frame.getType(), dai.ImgFrame.Type.NV12)
        self.assertEqual((frame.getWidth(), frame.getHeight()), (8, 2))
        self.assertEqual(data[0, 0], 16)
        self.assertEqual(data[0, 1], 16)
        self.assertEqual(data[0, -1], 235)
        self.assertGreater(data[0, 3], data[0, 2])  # Low bits survive tone mapping.
        self.assertGreater(data[0, 5], 100)  # Midtones are no longer linear RAW.
        self.assertTrue(np.all(data[2] == 128))
        self.assertEqual(frame.getTimestamp(), raw.getTimestamp())
        self.assertEqual(frame.getTimestampDevice(), raw.getTimestampDevice())
        self.assertEqual(frame.getSequenceNum(), 42)
        self.assertTrue(np.all(np.diff(processor.lut.astype(int)) >= 0))


class ExposureTests(unittest.TestCase):
    def simulate(self, processor, light, steps=40, start=0):
        # The sensor honors exposure but ignores requested ISO, as the tested
        # raw-only hardware does. Each sample arrives after the control settles.
        controls = []
        for step in range(steps):
            pixel = round(np.clip(64 + light * processor.exposure_us, 0, 1023))
            raw = raw_frame(
                np.full((32, 32), pixel),
                exposure_us=processor.exposure_us,
                timestamp=(start + step) * 0.5,
            )
            _, control = processor.convert(raw, target_luma=96)
            controls.append(control)
        return controls

    def test_converges_using_real_exposure_before_gain(self):
        processor = RawImageProcessor(20)
        controls = self.simulate(processor, 0.005)
        self.assertLess(abs(processor.luma - 96), 3)
        self.assertGreater(processor.exposure_us, 10000)
        self.assertEqual(processor.digital_gain, 1)
        self.assertTrue(all(control is None for control in controls[-5:]))

    def test_low_light_uses_bounded_gain_then_locks(self):
        processor = RawImageProcessor(20, iso=800)
        self.simulate(processor, 0.0006)
        self.assertLess(abs(processor.luma - 96), 3)
        self.assertEqual(processor.exposure_us, 33000)
        self.assertGreater(processor.digital_gain, 1)
        self.assertLessEqual(processor.digital_gain, 8)
        self.assertTrue(processor.locked)
        settings = processor.exposure_us, processor.digital_gain
        lut = processor.lut.copy()
        self.assertTrue(
            all(control is None for control in self.simulate(processor, 0.05, start=40))
        )
        self.assertEqual((processor.exposure_us, processor.digital_gain), settings)
        np.testing.assert_array_equal(processor.lut, lut)

    def test_lock_deadline_is_relative_to_first_frame_and_ignores_later_targets(self):
        processor = RawImageProcessor(20, settle_seconds=2)
        raw = raw_frame(np.full((32, 32), 80), timestamp=100)
        _, control = processor.convert(raw)
        self.assertIsNotNone(control)
        self.assertFalse(processor.locked)
        settings = processor.exposure_us, processor.digital_gain
        raw.getTimestampDevice.return_value = timedelta(seconds=102)
        _, control = processor.convert(raw, target_luma=192)
        self.assertIsNone(control)
        self.assertTrue(processor.locked)
        raw.getTimestampDevice.return_value = timedelta(seconds=110)
        _, control = processor.convert(raw, target_luma=48)
        self.assertIsNone(control)
        self.assertEqual((processor.exposure_us, processor.digital_gain), settings)

    def test_total_darkness_stays_bounded(self):
        processor = RawImageProcessor(20)
        self.simulate(processor, 0)
        self.assertEqual(processor.exposure_us, 33000)
        self.assertEqual(processor.digital_gain, 8)
        self.assertEqual(processor.luma, 16)

    def test_manual_mode_preserves_exposure_and_gain(self):
        processor = RawImageProcessor(20, exposure_us=5000, auto_exposure=False)
        self.assertTrue(
            all(control is None for control in self.simulate(processor, 0.0001))
        )
        self.assertEqual(processor.exposure_us, 5000)
        self.assertEqual(processor.digital_gain, 1)

    def test_control_rate_uses_capture_time(self):
        processor = RawImageProcessor(20)
        raw = raw_frame(np.full((32, 32), 80), timestamp=1)
        _, control = processor.convert(raw)
        self.assertIsNotNone(control)
        raw.getTimestampDevice.return_value = timedelta(seconds=1.1)
        _, control = processor.convert(raw)
        self.assertIsNone(control)
        raw.getTimestampDevice.return_value = timedelta(seconds=1.5)
        raw.getExposureTime.return_value = timedelta(microseconds=processor.exposure_us)
        _, control = processor.convert(raw)
        self.assertIsNotNone(control)

    def test_highlights_limit_exposure_in_dark_scene(self):
        pixels = np.full((32, 32), 64)
        pixels[:8] = 1023
        processor = RawImageProcessor(20)
        _, control = processor.convert(raw_frame(pixels), target_luma=120)
        self.assertIsNotNone(control)
        self.assertLess(processor.exposure_us, 10000)

    def test_exposure_does_not_exceed_frame_period(self):
        processor = RawImageProcessor(120, exposure_us=33000)
        self.assertLessEqual(processor.exposure_us, 1_000_000 / 120)
        self.simulate(processor, 0)
        self.assertLessEqual(processor.exposure_us, 1_000_000 / 120)


class ReferenceTests(unittest.TestCase):
    def preview(self, value):
        frame = Mock(spec=dai.ImgFrame)
        frame.getWidth.return_value = 4
        frame.getHeight.return_value = 2
        frame.getStride.return_value = 6
        frame.getData.return_value = np.array(
            [value] * 4 + [255] * 2 + [value] * 4 + [255] * 2 + [128] * 6,
            dtype=np.uint8,
        )
        return frame

    def test_median_smoothing_and_stale_samples(self):
        reference = BrightnessReference()
        for socket, value in [("A", 100), ("B", 90), ("C", 250)]:
            reference.observe(socket, self.preview(value), now=0)
        self.assertAlmostEqual(reference.update(0), 96.8)
        self.assertAlmostEqual(
            reference.update(3), 96.8
        )  # Hold target if previews stop.
        reference.observe("B", self.preview(60), now=3)
        self.assertAlmostEqual(reference.update(3), 89.44)


if __name__ == "__main__":
    unittest.main()
