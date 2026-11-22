import { Button } from '@luxonis/ui-components';
import type { ReactNode } from 'react';
import {
	type Action,
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
		<section className="flex flex-col gap-1">
			<h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
				{title}
			</h3>
			{children}
		</section>
	);
}

function MatrixView({ matrix }: { matrix: Matrix }) {
	return (
		<pre className="rounded bg-gray-100 p-2 text-xs leading-5">
			{matrix.map((row) => row.map((v) => fmt(v)).join('  ')).join('\n')}
		</pre>
	);
}

function Message({ text, ok }: { text: string; ok: boolean }) {
	if (!text) return null;
	return (
		<p className={`text-sm ${ok ? 'text-green-700' : 'text-red-600'}`}>
			{text}
		</p>
	);
}

export function GuidePanel({
	state,
	act,
}: { state: ImuState; act: (action: Action) => void }) {
	const { pose, phase } = state;
	const capturing = phase === 'capturing';
	return (
		<>
			<h2 className="text-lg font-semibold">
				Pose {pose.index} of {pose.count}
			</h2>
			<img
				src={`poses/${pose.index}.jpg`}
				alt={`Pose ${pose.index}`}
				className="w-full rounded-md"
			/>
			<p>{pose.instruction}</p>
			{capturing ? (
				<div className="flex flex-col gap-1">
					<span className="text-sm text-green-700">
						Capturing {Math.round(state.progress * 100)}%. Hold still.
					</span>
					<div className="h-2 rounded bg-gray-200">
						<div
							className="h-2 rounded bg-pink-500"
							style={{ width: `${state.progress * 100}%` }}
						/>
					</div>
				</div>
			) : !state.imuReady ? (
				<span className="text-sm text-gray-500">Waiting for IMU data...</span>
			) : (
				<ul className="text-sm">
					<li className={state.still ? 'text-green-700' : 'text-red-600'}>
						{state.still ? 'Device is still.' : 'Device is moving.'}
					</li>
					{pose.index > 1 && (
						<li
							className={
								state.orientationError ? 'text-amber-600' : 'text-green-700'
							}
						>
							{state.orientationError ?? 'Orientation looks right.'}
						</li>
					)}
				</ul>
			)}
			<div className="flex gap-2">
				<Button
					onClick={() => act('capture')}
					disabled={capturing || !state.imuReady}
				>
					Capture
				</Button>
				<Button
					variant="outline"
					onClick={() => act('back')}
					disabled={capturing || pose.index === 1}
				>
					Back
				</Button>
			</div>
			<Message text={state.message} ok={false} />
		</>
	);
}

export function ResultsPanel({
	state,
	act,
}: { state: ImuState; act: (action: Action) => void }) {
	const result = state.result;
	if (!result) return null;
	const { device } = state;
	const flash = () => {
		if (window.confirm(`Flash the new IMU calibration to ${device.name}?`)) {
			act('flash');
		}
	};
	return (
		<>
			<h2 className="text-lg font-semibold">Results</h2>
			<p className="text-sm">
				Worst pose error: {Math.max(...result.poseErrors).toFixed(3)} m/s²
			</p>
			<Section title={`IMU → ${device.socket} rotation`}>
				<MatrixView matrix={result.rotation} />
				{result.specMatch !== null && (
					<span
						className={`text-xs ${result.specMatch ? 'text-green-700' : 'text-amber-600'}`}
					>
						{result.specMatch
							? 'Matches the depthai-boards design.'
							: 'Differs from the depthai-boards design.'}
					</span>
				)}
			</Section>
			<Section title="Accelerometer [Q|b] (b in m/s²)">
				<MatrixView matrix={result.accelerometer} />
			</Section>
			<Section title="Gyroscope bias b, added to readings (rad/s)">
				<MatrixView matrix={[result.gyroscope.map((row) => row[3])]} />
			</Section>
			{result.problems.length ? (
				result.problems.map((p) => (
					<p key={p} className="text-sm text-red-600">
						{p}
					</p>
				))
			) : (
				<p className="text-sm text-green-700">All checks passed.</p>
			)}
			<div className="flex gap-2">
				<Button
					onClick={flash}
					disabled={result.flashed || result.problems.length > 0}
				>
					{result.flashed ? 'Flashed' : 'Flash to device'}
				</Button>
				<Button variant="outline" onClick={() => act('redo')}>
					Redo
				</Button>
			</div>
			<Message text={state.message} ok={state.messageOk} />
		</>
	);
}

export function LiveCheckTable({
	stored,
	preview,
	flashed,
}: { stored: LiveCheck; preview: LiveCheck | null; flashed: boolean }) {
	const columns: [string, LiveCheck][] = [['Stored on device', stored]];
	if (preview) {
		columns.push([flashed ? 'New (flashed)' : 'New (preview)', preview]);
	}
	const rows: [string, (c: LiveCheck) => string][] = [
		[
			`|g| (${GRAVITY.toFixed(2)})`,
			(c) => (c.gravity ? norm(c.gravity).toFixed(3) : '-'),
		],
		...(['x', 'y', 'z'] as const).map(
			(axis, i): [string, (c: LiveCheck) => string] => [
				`gyro ${axis} (0)`,
				(c) => (c.gyro ? fmt(c.gyro[i]) : '-'),
			],
		),
	];
	return (
		<Section title="Live check: mean of last 1 s vs target (keep still)">
			<table className="text-xs">
				<thead>
					<tr className="text-left text-gray-500">
						<th />
						{columns.map(([name]) => (
							<th key={name} className="pl-2">
								{name}
							</th>
						))}
					</tr>
				</thead>
				<tbody>
					{rows.map(([label, value]) => (
						<tr key={label}>
							<td>{label}</td>
							{columns.map(([name, check]) => (
								<td key={name} className="pl-2 font-mono">
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

const STATUS_STYLE: Record<CalibrationStatus | 'flashed', string> = {
	flashed: 'bg-green-100 text-green-800',
	calibrated: 'bg-green-100 text-green-800',
	default: 'bg-amber-100 text-amber-800',
	missing: 'bg-red-100 text-red-800',
};

const STATUS_LABEL: Record<CalibrationStatus | 'flashed', string> = {
	flashed: 'in EEPROM',
	calibrated: 'calibrated',
	default: 'default (uncalibrated)',
	missing: 'missing',
};

function Badge({ status }: { status: CalibrationStatus | 'flashed' }) {
	return (
		<span className={`rounded px-2 text-xs ${STATUS_STYLE[status]}`}>
			{STATUS_LABEL[status]}
		</span>
	);
}

export function DevicePanel({ device }: { device: DeviceInfo }) {
	const rows: [string, ReactNode][] = [
		['Device', device.name],
		['Device ID', device.id],
		['Platform', device.platform],
		['Product', device.productName],
		['Board', `${device.boardName} ${device.boardRev}`],
		['IMU', `${device.imu} (fw ${device.imuFirmware})`],
		['Magnetometer', device.magnetometer ? 'yes' : 'no'],
		['IMU extrinsics', <Badge key="e" status={device.extrinsics} />],
		['Accelerometer cal.', <Badge key="a" status={device.accelerometer} />],
		['Gyroscope cal.', <Badge key="g" status={device.gyroscope} />],
		['Extrinsics to', device.socket],
		[
			'Translation (cm)',
			device.translationCm.map((v) => v.toFixed(2)).join(', '),
		],
	];
	return (
		<>
			<h2 className="text-lg font-semibold">Device</h2>
			<dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
				{rows.map(([label, value]) => (
					<div key={label} className="contents">
						<dt className="text-gray-500">{label}</dt>
						<dd className="break-all">{value}</dd>
					</div>
				))}
			</dl>
			<p className="text-xs text-gray-500">
				Translation source: {device.mountingSource}
			</p>
			{device.calibration.rotation && (
				<Section title="Stored IMU rotation">
					<MatrixView matrix={device.calibration.rotation} />
				</Section>
			)}
		</>
	);
}
