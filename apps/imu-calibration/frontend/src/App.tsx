import { Streams, useDaiConnection } from '@luxonis/depthai-viewer-common';
import { Switch } from '@luxonis/ui-components';
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
	DeviceSidebar,
	type LiveCheck,
	LiveCheckSection,
	PoseSection,
	ResultsSection,
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

	return state ? (
		<Dashboard state={state} rows={rows} act={act} connected={connected} />
	) : (
		<main className="flex h-screen w-screen items-center justify-center text-sm text-muted-foreground">
			{connected ? 'Waiting for the device...' : 'Connecting...'}
		</main>
	);
}

function Dashboard({
	state,
	rows,
	act,
	connected,
}: {
	state: ImuState;
	rows: Sample[];
	act: (action: Action) => void;
	connected: boolean;
}) {
	const [showStored, setShowStored] = useState(true);
	const [showNew, setShowNew] = useState(true);
	const stored = calibrated(rows, state.device.calibration);
	const preview = state.result ? calibrated(rows, state.result) : null;

	const series = (key: 'accel' | 'gyro'): Series[] => {
		const out: Series[] = [];
		if (showStored || !preview) {
			out.push({ values: stored[key], dashed: preview !== null });
		}
		if (preview && showNew) out.push({ values: preview[key] });
		return out;
	};

	return (
		<main className="flex h-screen w-screen flex-row gap-6 p-6">
			<aside className="flex max-h-full w-[280px] shrink-0 flex-col gap-5 overflow-y-auto pr-2 text-left">
				<DeviceSidebar device={state.device} />
			</aside>

			<div className="w-0.5 shrink-0 bg-border" />

			<div className="flex min-w-0 flex-1 flex-col gap-4">
				<div className="relative min-h-0 flex-[3] overflow-hidden">
					<Streams defaultTopics={['Camera']} allowedTopics={['Camera']} />
				</div>
				{preview && (
					<div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
						<span className="flex items-center gap-2 whitespace-nowrap">
							Stored calibration (dashed)
							<Switch
								value={showStored}
								onChange={setShowStored}
								showActiveLabelOnly
							/>
						</span>
						<span className="flex items-center gap-2 whitespace-nowrap">
							New calibration (solid)
							<Switch
								value={showNew}
								onChange={setShowNew}
								showActiveLabelOnly
							/>
						</span>
					</div>
				)}
				<div className="grid min-h-0 flex-[2] auto-rows-[minmax(150px,1fr)] grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-4 overflow-y-auto">
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
						title="Magnetometer"
						unit="µT"
						series={[{ values: rows.map((r) => r.mag) }]}
						window={WINDOW}
						minSpan={5}
						placeholder={
							state.device.magnetometer
								? undefined
								: 'No magnetometer on this IMU'
						}
					/>
				</div>
			</div>

			<div className="w-0.5 shrink-0 bg-border" />

			<aside className="flex max-h-full w-[380px] shrink-0 flex-col gap-5 overflow-y-auto pr-2 text-left">
				<h1 className="text-2xl font-bold">IMU Calibration</h1>
				<p className="text-sm text-muted-foreground">
					Place the device in six poses to compute the IMU rotation,
					accelerometer scale and bias, and gyroscope bias. Nothing is written
					to the device until you press Flash.
				</p>

				{state.result ? (
					<ResultsSection
						result={state.result}
						device={state.device}
						message={state.message}
						messageOk={state.messageOk}
						act={act}
					/>
				) : (
					<PoseSection state={state} act={act} />
				)}

				<LiveCheckSection
					stored={liveCheck(stored)}
					preview={preview && liveCheck(preview)}
					flashed={state.result?.flashed ?? false}
				/>

				<div
					className={`mt-auto flex items-center gap-2 border-t border-border pt-4 text-sm ${
						connected ? 'text-success' : 'text-destructive'
					}`}
				>
					<div
						className={`h-3 w-3 rounded-full ${
							connected ? 'bg-success' : 'bg-destructive'
						}`}
					/>
					<span>{connected ? 'Connected to device' : 'Disconnected'}</span>
				</div>
			</aside>
		</main>
	);
}

export default App;
