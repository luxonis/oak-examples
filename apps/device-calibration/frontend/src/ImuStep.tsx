import { Streams } from '@luxonis/depthai-viewer-common';
import { Button, Switch } from '@luxonis/ui-components';
import { useState } from 'react';
import { Chart, type Series } from './Chart.tsx';
import {
	type Act,
	type DeviceInfo,
	type ImuMounting,
	type ImuResult,
	type ImuState,
	type Sample,
	type StepProps,
	type StoredCalibration,
	type Vec3,
	applyCalibration,
	meanVec,
	norm,
} from './api.ts';
import { MatrixView, Section, Status, fmt } from './ui.tsx';
import { WINDOW } from './useCalibration.ts';

const GRAVITY = 9.80665;
const CHECK_SAMPLES = 25; // 1 s

interface LiveCheck {
	gravity: Vec3 | null;
	gyro: Vec3 | null;
}

function calibrated(rows: Sample[], cal: StoredCalibration | ImuResult) {
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

/** Camera stream plus live IMU charts; after the six poses, stored (dashed) vs new (solid). */
export function Main({ state, rows }: StepProps) {
	const [showStored, setShowStored] = useState(true);
	const [showNew, setShowNew] = useState(true);
	const stored = calibrated(rows, state.device.calibration);
	const result = state.imu?.result;
	const preview = result ? calibrated(rows, result) : null;

	const series = (key: 'accel' | 'gyro'): Series[] => {
		const out: Series[] = [];
		if (showStored || !preview) {
			out.push({ values: stored[key], dashed: preview !== null });
		}
		if (preview && showNew) out.push({ values: preview[key] });
		return out;
	};

	return (
		<>
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
						<Switch value={showNew} onChange={setShowNew} showActiveLabelOnly />
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
		</>
	);
}

/** Six-pose guide or IMU results, plus the live |g| / gyro check. */
export function Side({ state, rows, act }: StepProps) {
	const imu = state.imu;
	if (!imu) {
		return (
			<p className="text-sm text-muted-foreground">This device has no IMU.</p>
		);
	}
	const stored = calibrated(rows, state.device.calibration);
	const preview = imu.result ? calibrated(rows, imu.result) : null;
	return (
		<>
			{imu.result ? (
				<>
					<ResultsSection result={imu.result} device={state.device} />
					<Button onClick={() => act('accept')}>Continue to review</Button>
					<Button variant="outline" onClick={() => act('imu_redo')}>
						Redo
					</Button>
				</>
			) : (
				<>
					<PoseSection imu={imu} act={act} />
					<Button variant="outline" onClick={() => act('skip_imu')}>
						Skip IMU
					</Button>
				</>
			)}
			{imu.message && (
				<p
					className={`break-all text-sm ${imu.messageOk ? 'text-success' : 'text-destructive'}`}
				>
					{imu.message}
				</p>
			)}
			<LiveCheckSection
				stored={liveCheck(stored)}
				preview={preview && liveCheck(preview)}
				flashed={state.flashed}
			/>
		</>
	);
}

/** Camera and IMU summary, what will be written, and the single Flash button. */
export function ReviewSide({ state, rows, act }: StepProps) {
	const { cameraResult: cams, imu, imuMounting } = state;
	const worst = cams?.cameras.reduce((a, c) => (c.rmsNew > a.rmsNew ? c : a));
	const stored = calibrated(rows, state.device.calibration);
	const preview = imu?.result ? calibrated(rows, imu.result) : null;
	const written = [
		cams && 'Camera intrinsics and extrinsics',
		imu?.result && 'IMU accelerometer, gyroscope and mounting rotation',
	].filter(Boolean);
	return (
		<>
			<Section title="Cameras">
				{worst ? (
					<p className="text-sm">
						Worst camera: {worst.name}, {worst.rmsNew.toFixed(2)} px (stored{' '}
						{worst.rmsOld?.toFixed(2) ?? 'n/a'} px).
					</p>
				) : (
					<p className="text-sm text-muted-foreground">
						Skipped: the stored camera calibration stays.
					</p>
				)}
			</Section>
			{imu?.result ? (
				imuMounting && <MountingSection mounting={imuMounting} />
			) : (
				<Section title="IMU">
					<p className="text-sm text-muted-foreground">
						Skipped: the stored IMU calibration stays.
					</p>
				</Section>
			)}
			<Section title="Will be written">
				{written.map((w) => (
					<p key={String(w)} className="text-sm">
						{w}
					</p>
				))}
				{state.dryRun && (
					<p className="text-sm text-muted-foreground">
						Dry run: nothing is written to the device.
					</p>
				)}
			</Section>
			{state.problems.map((p) => (
				<p key={p} className="text-sm text-destructive">
					{p}
				</p>
			))}
			{state.flashed ? (
				<>
					<p className="break-all text-sm text-success">
						{state.dryRun ? 'Dry run done, nothing flashed' : 'Flashed'}.
						Backup: {state.backupPath}
					</p>
					<Button onClick={() => act('restart')}>Start over</Button>
				</>
			) : (
				<Button
					onClick={() => act('flash')}
					disabled={state.problems.length > 0 || !written.length}
				>
					Flash to device
				</Button>
			)}
			{state.message && (
				<p
					className={`break-all text-sm ${state.messageOk ? 'text-success' : 'text-destructive'}`}
				>
					{state.message}
				</p>
			)}
			{imu?.result && (
				<ResultsSection result={imu.result} device={state.device} />
			)}
			{preview && (
				<LiveCheckSection
					stored={liveCheck(stored)}
					preview={liveCheck(preview)}
					flashed={state.flashed}
				/>
			)}
		</>
	);
}

/** Where the IMU -> camera rotation came from and how far it is from the depthai-boards spec. */
export function MountingSection({ mounting }: { mounting: ImuMounting }) {
	const rpy = mounting.specErrorRpyDeg;
	return (
		<Section title="IMU mounting">
			<p className="text-sm">
				{mounting.source === 'board'
					? `Rotation refined from ${mounting.sets} board views, residual ${mounting.residualDeg?.toFixed(2)} deg.`
					: `Six-pose mapping used: ${mounting.reason}`}
			</p>
			{rpy && mounting.specErrorDeg !== null && (
				<Status ok={mounting.specErrorDeg <= 5}>
					Mounting vs spec: roll {rpy[0].toFixed(1)}, pitch {rpy[1].toFixed(1)},
					yaw {rpy[2].toFixed(1)} deg.
					{mounting.specErrorDeg > 5 &&
						` Differs from the depthai-boards spec by ${mounting.specErrorDeg.toFixed(1)} deg.`}
				</Status>
			)}
		</Section>
	);
}

export function PoseSection({ imu, act }: { imu: ImuState; act: Act }) {
	const { pose, phase } = imu;
	const capturing = phase === 'capturing';
	return (
		<Section title={`Pose ${pose.index} of ${pose.count}`}>
			<div className="h-1 rounded-full bg-muted">
				<div
					className="h-1 rounded-full bg-primary"
					style={{ width: `${((pose.index - 1) / pose.count) * 100}%` }}
				/>
			</div>
			<img
				src={`poses/${pose.index}.jpg`}
				alt={`Pose ${pose.index}`}
				className="w-full rounded-md border border-border"
			/>
			<p className="text-sm">{pose.instruction}</p>
			{capturing ? (
				<div className="flex flex-col gap-1">
					<Status ok>
						Capturing {Math.round(imu.progress * 100)}%, hold still.
					</Status>
					<div className="h-1 rounded-full bg-muted">
						<div
							className="h-1 rounded-full bg-success"
							style={{ width: `${imu.progress * 100}%` }}
						/>
					</div>
				</div>
			) : !imu.imuReady ? (
				<span className="text-sm text-muted-foreground">
					Waiting for IMU data...
				</span>
			) : (
				<div className="flex flex-col">
					<Status ok={imu.still}>
						{imu.still ? 'Device is still.' : 'Device is moving.'}
					</Status>
					{pose.index > 1 && (
						<Status ok={!imu.orientationError}>
							{imu.orientationError ?? 'Orientation matches the guide.'}
						</Status>
					)}
				</div>
			)}
			<div className="flex gap-2">
				<Button
					className="flex-1"
					onClick={() => act('imu_capture')}
					disabled={capturing || !imu.imuReady}
				>
					Capture
				</Button>
				<Button
					className="flex-1"
					variant="outline"
					onClick={() => act('imu_back')}
					disabled={capturing || pose.index === 1}
				>
					Back
				</Button>
			</div>
			{imu.message && <p className="text-sm text-destructive">{imu.message}</p>}
		</Section>
	);
}

export function ResultsSection({
	result,
	device,
}: { result: ImuResult; device: DeviceInfo }) {
	return (
		<Section title="IMU results">
			{result.problems.length ? (
				result.problems.map((p) => (
					<p key={p} className="text-sm text-destructive">
						{p}
					</p>
				))
			) : (
				<p className="text-sm text-success">
					All checks passed. Tilt the device to any angle: the new |g| should
					stay at {GRAVITY.toFixed(2)} m/s².
				</p>
			)}
			<MatrixView
				label={`IMU → ${device.socket} rotation${
					result.specMatch === null
						? ''
						: result.specMatch
							? ' (matches depthai-boards)'
							: ' (differs from depthai-boards)'
				}`}
				matrix={result.rotation}
			/>
			<MatrixView
				label="Accelerometer [Q|b], b in m/s²"
				matrix={result.accelerometer}
			/>
			<MatrixView
				label="Gyroscope bias b, rad/s"
				matrix={[result.gyroscope.map((row) => row[3])]}
			/>
			<span className="text-sm text-muted-foreground">
				Pose tilt vs guide:{' '}
				{result.poseTilts.map((t) => `${t.toFixed(1)}°`).join(', ')}
			</span>
		</Section>
	);
}

export function LiveCheckSection({
	stored,
	preview,
	flashed,
}: { stored: LiveCheck; preview: LiveCheck | null; flashed: boolean }) {
	const columns: [string, LiveCheck][] = [['Stored', stored]];
	if (preview) columns.push([flashed ? 'New (flashed)' : 'New', preview]);
	const rows: [string, string, (c: LiveCheck) => string][] = [
		[
			'|g|',
			GRAVITY.toFixed(2),
			(c) => (c.gravity ? norm(c.gravity).toFixed(3) : '-'),
		],
		...(['x', 'y', 'z'] as const).map(
			(axis, i): [string, string, (c: LiveCheck) => string] => [
				`Gyro ${axis}`,
				'0',
				(c) => (c.gyro ? fmt(c.gyro[i]) : '-'),
			],
		),
	];
	return (
		<Section title="Live check">
			<p className="text-sm text-muted-foreground">
				Mean of the last second. Keep the device still.
			</p>
			<table className="w-full text-sm">
				<thead>
					<tr className="text-left text-muted-foreground">
						<th className="font-normal" />
						<th className="font-normal">Target</th>
						{columns.map(([name]) => (
							<th key={name} className="font-normal">
								{name}
							</th>
						))}
					</tr>
				</thead>
				<tbody>
					{rows.map(([label, target, value]) => (
						<tr key={label}>
							<td>{label}</td>
							<td className="font-mono text-muted-foreground">{target}</td>
							{columns.map(([name, check]) => (
								<td key={name} className="font-mono">
									{value(check)}
								</td>
							))}
						</tr>
					))}
				</tbody>
			</table>
		</Section>
	);
}
