import type { ReactNode } from 'react';
import type { CalibrationStatus, DeviceInfo, Matrix, Phase } from './api.ts';

export const fmt = (v: number, digits = 4) =>
	(v >= 0 ? '+' : '') + v.toFixed(digits);

export function Section({
	title,
	children,
}: { title: string; children: ReactNode }) {
	return (
		<section className="flex flex-col gap-2">
			<h3 className="font-semibold">{title}</h3>
			{children}
		</section>
	);
}

export function MatrixView({
	label,
	matrix,
}: { label: string; matrix: Matrix }) {
	return (
		<div className="flex flex-col gap-1">
			<span className="text-sm text-muted-foreground">{label}</span>
			<pre className="rounded-md bg-muted px-3 py-2 font-mono text-xs leading-5">
				{matrix.map((row) => row.map((v) => fmt(v)).join('  ')).join('\n')}
			</pre>
		</div>
	);
}

/** One status line: green when ok, amber otherwise. */
export function Status({ ok, children }: { ok: boolean; children: ReactNode }) {
	return (
		<span className={`text-sm ${ok ? 'text-success' : 'text-warning'}`}>
			{children}
		</span>
	);
}

/** Label + input stacked, as in the other apps' sidebars. */
export function Field({
	label,
	children,
}: { label: string; children: ReactNode }) {
	return (
		// biome-ignore lint/a11y/noLabelWithoutControl: the input is passed as children
		<label className="flex flex-col gap-1 text-sm">
			<span className="text-muted-foreground">{label}</span>
			{children}
		</label>
	);
}

const STATUS: Record<CalibrationStatus | 'flashed', [string, string]> = {
	flashed: ['In EEPROM', 'text-success'],
	calibrated: ['Calibrated', 'text-success'],
	default: ['Default (uncalibrated)', 'text-warning'],
	missing: ['Missing', 'text-destructive'],
};

export function StatusText({
	status,
}: { status: CalibrationStatus | 'flashed' }) {
	const [label, color] = STATUS[status];
	return <span className={color}>{label}</span>;
}

const STEPS: [string, Phase[]][] = [
	['Setup', ['setup']],
	['Capture', ['capture', 'processing']],
	['Results', ['results']],
	['IMU', ['imu']],
	['Review', ['review']],
];

export function StepList({ phase }: { phase: Phase }) {
	const current = STEPS.findIndex(([, phases]) => phases.includes(phase));
	return (
		<Section title="Steps">
			<ol className="flex flex-col gap-1 text-sm">
				{STEPS.map(([label], i) => (
					<li
						key={label}
						className={
							i === current
								? 'font-semibold'
								: i < current
									? 'text-success'
									: 'text-muted-foreground'
						}
					>
						{i + 1}. {label}
					</li>
				))}
			</ol>
		</Section>
	);
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
