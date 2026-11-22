import { Streams, useDaiConnection } from '@luxonis/depthai-viewer-common';
import { useEffect, useRef, useState } from 'react';
import { Chart, type Series } from './Chart.tsx';
import {
	type Action,
	type CalibrationResult,
	type ImuState,
	type Sample,
	type StoredCalibration,
	type Vec3,
	applyCalibration,
	callService,
	meanVec,
} from './api.ts';
import {
	DevicePanel,
	GuidePanel,
	type LiveCheck,
	LiveCheckTable,
	ResultsPanel,
} from './panels.tsx';

const WINDOW = 250; // graph samples (10 s at 25 Hz), matches the backend buffer
const CHECK_SAMPLES = 25; // 1 s
const POLL_MS = 100;

type Calibration = StoredCalibration | CalibrationResult;

function calibrated(rows: Sample[], cal: Calibration) {
	return {
		accel: rows.map((r) =>
			applyCalibration(cal.rotation, cal.accelerometer, r.accel),
		),
		gyro: rows.map((r) =>
			applyCalibration(cal.rotation, cal.gyroscope, r.gyro),
		),
	};
}

function liveCheck(c: { accel: Vec3[]; gyro: Vec3[] }): LiveCheck {
	return {
		gravity: meanVec(c.accel.slice(-CHECK_SAMPLES)),
		gyro: meanVec(c.gyro.slice(-CHECK_SAMPLES)),
	};
}

function App() {
	const { connected, daiConnection } = useDaiConnection();
	const [state, setState] = useState<ImuState | null>(null);
	const [rows, setRows] = useState<Sample[]>([]);
	const [showStored, setShowStored] = useState(true);
	const [showNew, setShowNew] = useState(true);
	const since = useRef(0);
	const session = useRef<number | null>(null);

	useEffect(() => {
		if (!connected) return;
		const id = window.setInterval(() => {
			callService<ImuState>(
				daiConnection,
				'IMU State',
				{ since: since.current },
				(s) => {
					const restarted = s.session !== session.current;
					session.current = s.session;
					since.current = restarted ? 0 : Math.max(since.current, s.seq);
					// Replies can arrive out of order, so keep only samples newer than the buffer.
					setRows((prev) => {
						const kept = restarted ? [] : prev;
						const last = kept.at(-1)?.seq ?? 0;
						return [...kept, ...s.samples.filter((r) => r.seq > last)].slice(
							-WINDOW,
						);
					});
					setState(s);
				},
			);
		}, POLL_MS);
		return () => window.clearInterval(id);
	}, [connected, daiConnection]);

	const act = (action: Action) =>
		callService(daiConnection, 'IMU Action', { action });

	if (!state) {
		return (
			<main className="flex h-screen items-center justify-center text-gray-500">
				{connected ? 'Waiting for the device...' : 'Connecting...'}
			</main>
		);
	}

	const stored = calibrated(rows, state.device.calibration);
	const preview = state.result ? calibrated(rows, state.result) : null;
	const series = (key: 'accel' | 'gyro'): Series[] => [
		...(showStored || !preview
			? [{ values: stored[key], dashed: preview !== null }]
			: []),
		...(preview && showNew ? [{ values: preview[key] }] : []),
	];
	const magnetometer = rows.map((r) => r.mag);

	return (
		<main className="grid h-screen grid-cols-[340px_1fr_300px] gap-3 bg-gray-50 p-3 text-gray-900">
			<aside className="flex flex-col gap-3 overflow-y-auto rounded-md bg-white p-3">
				{state.phase === 'results' ? (
					<ResultsPanel state={state} act={act} />
				) : (
					<GuidePanel state={state} act={act} />
				)}
				<LiveCheckTable
					stored={liveCheck(stored)}
					preview={preview && liveCheck(preview)}
					flashed={state.result?.flashed ?? false}
				/>
			</aside>

			<section className="flex min-h-0 flex-col gap-3">
				<div className="h-[38%] min-h-0 overflow-hidden rounded-md bg-black">
					<Streams
						defaultTopics={['Camera']}
						allowedTopics={['Camera']}
						hideToolbar
					/>
				</div>
				{preview && (
					<div className="flex gap-4 text-sm">
						<label className="flex items-center gap-1">
							<input
								type="checkbox"
								checked={showStored}
								onChange={(e) => setShowStored(e.target.checked)}
							/>
							Stored calibration (dashed)
						</label>
						<label className="flex items-center gap-1">
							<input
								type="checkbox"
								checked={showNew}
								onChange={(e) => setShowNew(e.target.checked)}
							/>
							New calibration (solid)
						</label>
					</div>
				)}
				<Chart
					title="Accelerometer"
					unit="m/s²"
					series={series('accel')}
					window={WINDOW}
					minSpan={1}
				/>
				<Chart
					title="Gyroscope"
					unit="rad/s"
					series={series('gyro')}
					window={WINDOW}
					minSpan={0.05}
				/>
				<Chart
					title="Magnetometer (raw)"
					unit="µT"
					series={[{ values: magnetometer }]}
					window={WINDOW}
					minSpan={5}
					placeholder={
						state.device.magnetometer
							? undefined
							: 'No magnetometer on this IMU'
					}
				/>
			</section>

			<aside className="flex flex-col gap-3 overflow-y-auto rounded-md bg-white p-3">
				<DevicePanel device={state.device} />
			</aside>
		</main>
	);
}

export default App;
