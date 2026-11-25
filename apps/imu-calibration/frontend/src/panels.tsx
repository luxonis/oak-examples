import { Button } from '@luxonis/ui-components';
import type { ReactNode } from 'react';
import {
	type Action,
	type CalibrationResult,
	type CalibrationStatus,
	type DeviceInfo,
	type ImuState,
	type Matrix,
	type Vec3,
	norm,
} from './api.ts';

const GRAVITY = 9.80665;

export interface LiveCheck {
	gravity: Vec3 | null;
	gyro: Vec3 | null;
}

const fmt = (v: number, digits = 4) => (v >= 0 ? '+' : '') + v.toFixed(digits);

function Section({ title, children }: { title: string; children: ReactNode }) {
	return (
		<div className="flex flex-col gap-2">
			<h3 className="font-semibold">{title}</h3>
			{children}
		</div>
	);
}

function MatrixView({ label, matrix }: { label: string; matrix: Matrix }) {
	return (
		<div className="flex flex-col gap-1">
			<span className="text-sm text-muted-foreground">{label}</span>
			<pre className="rounded-md bg-muted px-3 py-2 font-mono text-xs leading-5">
				{matrix.map((row) => row.map((v) => fmt(v)).join('  ')).join('\n')}
			</pre>
		</div>
	);
}

function Status({ ok, children }: { ok: boolean; children: ReactNode }) {
	return (
		<span className={`text-sm ${ok ? 'text-success' : 'text-warning'}`}>
			{children}
		</span>
	);
}

export function PoseSection({
	state,
	act,
}: { state: ImuState; act: (action: Action) => void }) {
	const { pose, phase } = state;
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
						Capturing {Math.round(state.progress * 100)}%, hold still.
					</Status>
					<div className="h-1 rounded-full bg-muted">
						<div
							className="h-1 rounded-full bg-success"
							style={{ width: `${state.progress * 100}%` }}
						/>
					</div>
				</div>
			) : !state.imuReady ? (
				<span className="text-sm text-muted-foreground">
					Waiting for IMU data...
				</span>
			) : (
				<div className="flex flex-col">
					<Status ok={state.still}>
						{state.still ? 'Device is still.' : 'Device is moving.'}
					</Status>
					{pose.index > 1 && (
						<Status ok={!state.orientationError}>
							{state.orientationError ?? 'Orientation matches the guide.'}
						</Status>
					)}
				</div>
			)}
			<div className="flex gap-2">
				<Button
					className="flex-1"
					onClick={() => act('capture')}
					disabled={capturing || !state.imuReady}
				>
					Capture
				</Button>
				<Button
					className="flex-1"
					variant="outline"
					onClick={() => act('back')}
					disabled={capturing || pose.index === 1}
				>
					Back
				</Button>
			</div>
			{state.message && (
				<p className="text-sm text-destructive">{state.message}</p>
			)}
		</Section>
	);
}

export function ResultsSection({
	result,
	device,
	message,
	messageOk,
	act,
}: {
	result: CalibrationResult;
	device: DeviceInfo;
	message: string;
	messageOk: boolean;
	act: (action: Action) => void;
}) {
	const flash = () => {
		if (window.confirm(`Flash the new IMU calibration to ${device.name}?`)) {
			act('flash');
		}
	};
	return (
		<Section title="Results">
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
			<div className="flex gap-2">
				<Button
					className="flex-1"
					onClick={flash}
					disabled={result.flashed || result.problems.length > 0}
				>
					{result.flashed ? 'Flashed' : 'Flash to device'}
				</Button>
				<Button
					className="flex-1"
					variant="outline"
					onClick={() => act('redo')}
				>
					Redo
				</Button>
			</div>
			{message && (
				<p
					className={`break-all text-sm ${messageOk ? 'text-success' : 'text-destructive'}`}
				>
					{message}
				</p>
			)}
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

const STATUS: Record<CalibrationStatus | 'flashed', [string, string]> = {
	flashed: ['In EEPROM', 'text-success'],
	calibrated: ['Calibrated', 'text-success'],
	default: ['Default (uncalibrated)', 'text-warning'],
	missing: ['Missing', 'text-destructive'],
};

function StatusText({ status }: { status: CalibrationStatus | 'flashed' }) {
	const [label, color] = STATUS[status];
	return <span className={color}>{label}</span>;
}

export function DeviceSidebar({ device }: { device: DeviceInfo }) {
	const rows: [string, ReactNode][] = [
		['Device', device.name],
		['Device ID', device.id],
		['Platform', device.platform],
		['Product', device.productName],
		['Board', `${device.boardName} ${device.boardRev}`],
		['IMU', device.imu],
		['IMU firmware', device.imuFirmware],
		['Magnetometer', device.magnetometer ? 'Yes' : 'No'],
	];
	const calibration: [string, ReactNode][] = [
		['IMU extrinsics', <StatusText key="e" status={device.extrinsics} />],
		['Accelerometer', <StatusText key="a" status={device.accelerometer} />],
		['Gyroscope', <StatusText key="g" status={device.gyroscope} />],
		['Extrinsics to', device.socket],
		[
			'Translation (cm)',
			device.translationCm.map((v) => v.toFixed(2)).join(', '),
		],
	];
	const list = (items: [string, ReactNode][]) => (
		<dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
			{items.map(([label, value]) => (
				<div key={label} className="contents">
					<dt className="text-muted-foreground">{label}</dt>
					<dd className="break-all">{value}</dd>
				</div>
			))}
		</dl>
	);
	return (
		<>
			<h2 className="text-xl font-bold">Device</h2>
			{list(rows)}
			<Section title="Stored IMU calibration">
				{list(calibration)}
				<p className="text-xs text-muted-foreground">
					Translation source: {device.mountingSource}
				</p>
				{device.calibration.rotation && (
					<MatrixView
						label="IMU rotation"
						matrix={device.calibration.rotation}
					/>
				)}
			</Section>
		</>
	);
}
